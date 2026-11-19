"""Offline compaction preserves sparse rowids, legacy cells and all checkpoints."""
from contextlib import nullcontext,redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import compact_feature_storage as job


class Compaction(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()));self.path=self.root/'features.db'
        self.enterContext(patch.object(job,'assert_idle'))
        self.enterContext(patch.object(job.data_policy,'locked',side_effect=lambda **_:nullcontext()))
        self.enterContext(patch.object(job.data_policy,'snapshot_guard',side_effect=lambda **_:nullcontext()))
        with sqlite3.connect(self.path) as c:
            c.executescript('''CREATE TABLE features(symbol TEXT,interval TEXT,open_time INTEGER,formula_version INTEGER,value REAL,old_slope REAL,alias REAL GENERATED ALWAYS AS(value) VIRTUAL,PRIMARY KEY(symbol,interval,open_time));
                CREATE TABLE feature_engine_state(symbol TEXT PRIMARY KEY,state TEXT);
                CREATE TABLE configs(name TEXT PRIMARY KEY,spec BLOB) WITHOUT ROWID;
                CREATE INDEX values_by_time ON features(open_time);
                CREATE VIEW feature_view AS SELECT symbol,value FROM features;
                PRAGMA user_version=17;''')
            c.executemany('INSERT INTO features(rowid,symbol,interval,open_time,formula_version,value,old_slope) VALUES (?,?,?,?,?,?,?)',
                [(5,'BTCUSDT','5m',0,1,12.,777.),(29,'BTCUSDT','5m',300000,3,13.,None)])
            c.execute("INSERT INTO feature_engine_state VALUES ('BTCUSDT','exact checkpoint')")
            c.execute('INSERT INTO configs VALUES (?,?)',('custom',b'\x00\x01'))
        with sqlite3.connect(self.path) as c:
            c.execute('CREATE TABLE discarded(payload BLOB)')
            c.execute('INSERT INTO discarded VALUES (zeroblob(1048576))');c.commit()
            c.execute('DROP TABLE discarded')
        self.before=self.path.read_bytes()

    def run_job(self,**kwargs):
        with redirect_stdout(io.StringIO()):return job.compact(self.path,batch=1,**kwargs)

    def test_full_parity_virtual_columns_sparse_rowids_and_original_backup(self):
        state=self.run_job()
        self.assertTrue(state['complete']);self.assertEqual(state['rows_verified'],2)
        self.assertEqual(Path(state['backup']).read_bytes(),self.before)
        with sqlite3.connect(self.path) as c:
            self.assertEqual(c.execute('SELECT rowid,value,old_slope,alias FROM features ORDER BY rowid').fetchall(),[(5,12.,777.,12.),(29,13.,None,13.)])
            self.assertEqual(c.execute('SELECT state FROM feature_engine_state').fetchone()[0],'exact checkpoint')
            self.assertEqual(c.execute('SELECT spec FROM configs').fetchone()[0],b'\x00\x01')
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],17)
            self.assertEqual(c.execute('PRAGMA quick_check').fetchone()[0],'ok')
            self.assertFalse(c.execute('SELECT 1 FROM sqlite_master WHERE name=?',(job.WORK,)).fetchone())
        with self.assertRaisesRegex(RuntimeError,'backup already exists'):self.run_job()

    def test_copy_interruption_resumes_without_recopy_or_source_changes(self):
        original=job.write_report
        def fail_report(path,state):
            if state['stage']=='verified':raise RuntimeError('interrupted before switch')
            return original(path,state)
        with patch.object(job,'write_report',side_effect=fail_report),self.assertRaisesRegex(RuntimeError,'interrupted'):
            self.run_job()
        self.assertEqual(self.path.read_bytes(),self.before)
        state=self.run_job();self.assertEqual(state['rows_copied'],2);self.assertEqual(state['rows_verified'],2)

    def test_source_change_refuses_stale_resume(self):
        with patch.object(job,'write_report',side_effect=RuntimeError('stopped')),self.assertRaises(RuntimeError):self.run_job()
        # Start a recognizable partial job and interrupt verification.
        original=job.write_report
        def stop(path,state):
            if state['stage']=='verified':raise RuntimeError('stopped')
            original(path,state)
        with patch.object(job,'write_report',side_effect=stop),self.assertRaises(RuntimeError):self.run_job()
        with sqlite3.connect(self.path) as c:c.execute("UPDATE features SET value=99 WHERE rowid=5")
        with self.assertRaisesRegex(RuntimeError,'Source changed'):self.run_job()
        self.assertFalse(Path(str(self.path)+'.before-compaction').exists())

    def test_busy_process_blocks_before_copy(self):
        with patch.object(job,'assert_idle',side_effect=RuntimeError('Database is still open')),self.assertRaisesRegex(RuntimeError,'still open'):
            self.run_job()
        self.assertFalse(Path(str(self.path)+'.compact-building').exists())
        self.assertEqual(self.path.read_bytes(),self.before)

    def test_preflight_does_not_create_files(self):
        before=set(self.root.iterdir());result=job.preflight(self.path)
        self.assertEqual(result['mode'],'check');self.assertEqual(result['columns_removed'],0)
        self.assertEqual(set(self.root.iterdir()),before)

    def test_wide_real_feature_schema_and_generated_aliases_are_preserved(self):
        from Section_1_Global_Core.memory_storage.Storage import features_store as store,klines_store
        path=self.root/'wide.db'
        with patch.object(store,'DB_PATH',path),patch.object(klines_store,'DB_PATH',self.root/'absent-raw.db'):
            c=store.open_db()
            with c:c.execute("INSERT INTO features(rowid,symbol,interval,open_time,formula_version,ema50,nearest_buy_ema) VALUES (900,'BTCUSDT','5m',0,1,99,777)")
            info=c.execute('PRAGMA table_xinfo(features)').fetchall()
            with c:
                c.execute('CREATE TABLE discarded(payload BLOB)');c.execute('INSERT INTO discarded VALUES (zeroblob(1048576))')
            with c:c.execute('DROP TABLE discarded')
            c.close()
            with redirect_stdout(io.StringIO()):state=job.compact(path,batch=1)
            with sqlite3.connect(path) as c:
                self.assertEqual(c.execute('PRAGMA table_xinfo(features)').fetchall(),info)
                self.assertEqual(c.execute('SELECT rowid,ema50,nearest_buy_ema FROM features').fetchone(),(900,99.,777.))
            self.assertEqual(state['rows_verified'],1)

    def test_corrupt_partial_output_never_replaces_original(self):
        original=job.write_report
        def stop(path,state):
            if state['stage']=='verified':raise RuntimeError('stopped')
            original(path,state)
        with patch.object(job,'write_report',side_effect=stop),self.assertRaises(RuntimeError):self.run_job()
        target=Path(str(self.path)+'.compact-building')
        with sqlite3.connect(target) as c:c.execute('UPDATE features SET value=999 WHERE rowid=5')
        with self.assertRaisesRegex(RuntimeError,'value/rowid mismatch'):self.run_job()
        self.assertEqual(self.path.read_bytes(),self.before)

    def test_services_restart_when_offline_operation_fails(self):
        from types import SimpleNamespace
        import plistlib
        root=Path(job.__file__).resolve().parent
        agents=self.root/'Library'/'LaunchAgents';agents.mkdir(parents=True)
        for label,module in [('chart','Section_11_UI_UX.server.ui_server'),('liverunner','Section_1_Global_Core.memory_storage.Runner.live_runner')]:
            (agents/f'com.tradingindicator.{label}.plist').write_bytes(plistlib.dumps(dict(WorkingDirectory=str(root),ProgramArguments=['python3','-m',module])))
        calls=[]
        def run(args,**kwargs):calls.append(args);return SimpleNamespace(returncode=0,stderr='')
        with patch.object(job.sys,'platform','darwin'),patch.object(Path,'home',return_value=self.root), \
             patch.object(job.subprocess,'run',side_effect=run),self.assertRaisesRegex(RuntimeError,'injected'):
            with job.stopped_services():raise RuntimeError('injected')
        actions=[call[1] for call in calls]
        self.assertEqual(actions.count('bootout'),2);self.assertEqual(actions.count('bootstrap'),2)

    def test_interrupted_switch_after_verification_can_resume(self):
        with patch.object(job.os,'link',side_effect=RuntimeError('before switch')),self.assertRaisesRegex(RuntimeError,'before switch'):
            self.run_job()
        self.assertEqual(self.path.read_bytes(),self.before)
        state=self.run_job();self.assertTrue(state['complete']);self.assertEqual(state['rows_verified'],2)

    def test_user_triggers_are_restored_without_running_during_copy(self):
        with sqlite3.connect(self.path) as c:
            c.executescript('CREATE TABLE audit(stamp INTEGER); CREATE TRIGGER track_insert AFTER INSERT ON features BEGIN INSERT INTO audit VALUES (new.open_time); END;')
        self.run_job()
        with sqlite3.connect(self.path) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM audit').fetchone()[0],0)
            c.execute("INSERT INTO features(symbol,interval,open_time) VALUES ('ETHUSDT','5m',999)")
            self.assertEqual(c.execute('SELECT stamp FROM audit').fetchone()[0],999)

    def test_copy_without_space_savings_keeps_the_original(self):
        path=self.root/'small.db'
        with sqlite3.connect(path) as c:
            c.execute('CREATE TABLE features(value REAL)');c.execute('INSERT INTO features VALUES (3)')
        before=path.read_bytes()
        with redirect_stdout(io.StringIO()):state=job.compact(path,batch=1)
        self.assertEqual(state['stage'],'no_savings');self.assertFalse(state['complete'])
        self.assertEqual(path.read_bytes(),before)
        self.assertFalse(Path(str(path)+'.before-compaction').exists())

    def test_exact_installed_chart_shell_launcher_is_recognized(self):
        root=Path(job.__file__).resolve().parent
        launcher=root/'Section_11_UI_UX/binance_chart/run_chart.sh'
        config=dict(WorkingDirectory=str(launcher.parent),ProgramArguments=['/bin/bash',str(launcher)])
        self.assertTrue(job.service_belongs_to_checkout(config,'com.tradingindicator.chart','Section_11_UI_UX.server.ui_server',root))
        for altered in (
            dict(config,WorkingDirectory=str(root)),
            dict(config,ProgramArguments=['/bin/bash',str(self.root/'run_chart.sh')]),
            dict(config,ProgramArguments=['/bin/bash','-c','echo Section_11_UI_UX.server.ui_server']),
        ):
            self.assertFalse(job.service_belongs_to_checkout(altered,'com.tradingindicator.chart','Section_11_UI_UX.server.ui_server',root))
        self.assertFalse(job.service_belongs_to_checkout(config,'com.tradingindicator.liverunner','Section_1_Global_Core.memory_storage.Runner.live_runner',root))

    def test_shell_chart_and_module_runner_stop_and_restart_together(self):
        from types import SimpleNamespace
        import plistlib
        root=Path(job.__file__).resolve().parent
        launcher=root/'Section_11_UI_UX/binance_chart/run_chart.sh'
        agents=self.root/'Library/LaunchAgents';agents.mkdir(parents=True)
        configs={
            'chart':dict(WorkingDirectory=str(launcher.parent),ProgramArguments=['/bin/bash',str(launcher)]),
            'liverunner':dict(WorkingDirectory=str(root),ProgramArguments=['python3','-u','-m','Section_1_Global_Core.memory_storage.Runner.live_runner'])}
        for label,config in configs.items():
            (agents/f'com.tradingindicator.{label}.plist').write_bytes(plistlib.dumps(config))
        calls=[]
        def run(args,**kwargs):calls.append(args);return SimpleNamespace(returncode=0,stderr='')
        with patch.object(job.sys,'platform','darwin'),patch.object(Path,'home',return_value=self.root),patch.object(job.subprocess,'run',side_effect=run):
            with job.stopped_services():pass
        self.assertEqual([call[1] for call in calls],['print','print','bootout','bootout','bootstrap','bootstrap'])
