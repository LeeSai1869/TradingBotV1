"""Real SQLite history replay, live isolation, dependency lineage and coverage."""
import contextlib
import hashlib
import io
import json
import unittest
from unittest.mock import patch
import test_regime_history as fixtures
from Section_1_Global_Core import analytical_history as history,analytical_processor as live
from Section_1_Global_Core import aggregation_processor,intelligence_audit,data_policy,pivot_context_audit
from Section_1_Global_Core.memory_storage.Storage import engine_store,features_store,klines_store


class HistoryReplay(unittest.TestCase):
    setUp=fixtures.RegimeHistory.setUp

    def test_restart_advances_old_history_without_replacing_live_publications(self):
        from Section_1_Global_Core import regime_research
        recent=regime_research.catch_up('BTCUSDT','1m',since=None,now_ms=10**9)
        aggregation_processor.observe('BTCUSDT','1m','REGIME',recent,now_ms=10**9+1)
        hashes=lambda:tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in (features_store.DB_PATH,klines_store.DB_PATH))
        before=hashes()
        first=history.advance('BTCUSDT','1m','REGIME',limit=20,now_ms=10**9+2)
        second=history.advance('BTCUSDT','1m','REGIME',limit=20,now_ms=10**9+3)
        self.assertEqual(first['processed'],20);self.assertEqual(second['processed'],20)
        self.assertEqual(first['run_id'],second['run_id']);self.assertNotEqual(first['run_id'],recent['run_id'])
        policy=data_policy.read();generation=aggregation_processor.generation('REGIME')
        with intelligence_audit.reader() as conn:
            current,_=intelligence_audit.select_run(conn,'BTCUSDT','1m','REGIME',policy,generation,at=10**9+3)
            self.assertEqual(current['run_id'],recent['run_id'])
            progress=history.progress(conn,None,'BTCUSDT','1m','REGIME',policy,generation,at=10**9+3)
            self.assertEqual(progress['status'],'SOURCE_UNAVAILABLE')
            self.assertEqual(pivot_context_audit.select_history_run(conn,'BTCUSDT','1m','REGIME',policy,generation,at=10**9+3)[0]['run_id'],recent['run_id'])
        third=history.advance('BTCUSDT','1m','REGIME',limit=100,now_ms=10**9+4)
        self.assertEqual(third['processed'],25)
        from Section_1_Global_Core import regime_inputs
        source=regime_inputs.open_sources()
        try:
            with intelligence_audit.reader() as conn:
                progress=history.progress(conn,source,'BTCUSDT','1m','REGIME',policy,generation,at=10**9+4)
                self.assertEqual(progress['classified_candles'],65);self.assertEqual(progress['first_ms'],0)
                self.assertEqual(progress['pending_candles'],0);self.assertEqual(progress['status'],'CAUGHT_UP')
                chosen,status=pivot_context_audit.select_history_run(conn,'BTCUSDT','1m','REGIME',policy,generation,at=10**9+4)
                self.assertEqual(chosen['run_id'],first['run_id']);self.assertIn('HISTORICAL_LANE',status)
        finally:source.close()
        self.assertEqual(before,hashes())

    def test_all_ten_engines_join_historical_dependencies_without_live_bindings(self):
        for turn in range(3):
            for engine in history.ENGINES:history.advance('BTCUSDT','1m',engine,limit=200,now_ms=10**9+turn)
        conn=engine_store.open_db()
        try:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM mtf_bindings').fetchone()[0],0)
            rows=conn.execute('SELECT engine,run_id FROM engine_history_bindings').fetchall()
            self.assertEqual(len(rows),10)
            for engine,run_id in rows:
                self.assertIsNotNone(run_id,engine)
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM engine_results WHERE run_id=?',(run_id,)).fetchone()[0],65,engine)
            bias_run=dict(rows)['BIAS'];bundle=engine_store.input_bundle(conn,bias_run,0)
            for name,ref in bundle['dependency_refs'].items():self.assertTrue(ref.startswith(dict(rows)[name]+':'))
        finally:conn.close()

    def test_paused_and_stale_generations_never_report_complete(self):
        with patch.object(data_policy,'enabled',return_value=False):
            self.assertEqual(history.advance('BTCUSDT','1m','REGIME')['status'],'paused')
        history.advance('BTCUSDT','1m','REGIME',now_ms=10**9)
        with intelligence_audit.reader() as conn:
            run,status=history.select(conn,'BTCUSDT','1m','REGIME',data_policy.read(),'changed',at=10**9)
            self.assertIsNone(run);self.assertEqual(status,'OUTDATED_PRODUCER')

    def test_status_cli_separates_live_readiness_from_historical_row_counts(self):
        import intelligence_status
        history.advance('BTCUSDT','1m','REGIME',limit=100)
        output=io.StringIO();path=self.root/'readiness.json'
        with patch('sys.argv',['intelligence_status.py','--symbols','BTCUSDT','--intervals','1m','--summary','--output',str(path)]),contextlib.redirect_stdout(output):intelligence_status.main()
        self.assertIn('Selected symbols: BTCUSDT',output.getvalue())
        self.assertIn('classified=65 pending=0',output.getvalue())
        result=json.loads(path.read_text())
        self.assertEqual(result['pairs'][0]['engines']['REGIME']['history']['status'],'CAUGHT_UP')
        self.assertEqual(result['pairs'][0]['engines']['REGIME']['status'],'PUBLICATION_INDEX_UNAVAILABLE')

    def test_pending_feature_repair_and_new_uncomputed_close_are_explicit(self):
        from Section_1_Global_Core import regime_inputs
        from Section_1_Global_Core.memory_storage.Storage import db
        history.advance('BTCUSDT','1m','REGIME',limit=100,now_ms=10**9)
        db.write_klines([dict(self.clients[-1],open_time=65*60000,close_time=66*60000-1)])
        source=regime_inputs.open_sources()
        try:
            with intelligence_audit.reader() as conn:
                result=history.progress(conn,source,'BTCUSDT','1m','REGIME',data_policy.read(),aggregation_processor.generation('REGIME'),at=10**9)
                self.assertEqual(result['status'],'WAITING_FOR_FEATURE_CHECKPOINT');self.assertEqual(result['pending_candles'],1)
        finally:source.close()
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('BTCUSDT','1m','next',64*60000,-1,'[]',None,'[]'))
        conn.close();source=regime_inputs.open_sources()
        try:
            with intelligence_audit.reader() as conn:
                result=history.progress(conn,source,'BTCUSDT','1m','REGIME',data_policy.read(),aggregation_processor.generation('REGIME'),at=10**9)
                self.assertEqual(result['status'],'FEATURE_REPLAY_PENDING')
        finally:source.close()


class Scheduling(unittest.TestCase):
    def test_history_has_fair_bounded_turns_and_independent_live_budget(self):
        seen=[]
        def step(s,t,e,**kwargs):
            seen.append((s,t,e));return dict(processed=kwargs['limit'],status='processed')
        with patch.object(history,'_cursor',0),patch.object(history,'_messages',{}),patch.object(history,'advance',side_effect=step),contextlib.redirect_stdout(io.StringIO()):
            for _ in range(12):self.assertLessEqual(history.maintenance(['BTC','ETH'],['1h'],max_bars=100,time_budget=10),100)
        self.assertIn(('ETH','1h','REGIME'),seen)
        with patch.object(live.regime_research,'catch_up',return_value=dict(processed=0,status='waiting')),patch.object(history,'maintenance',return_value=7) as replay:
            self.assertEqual(live.maintenance(['BTC'],['1h'],max_pairs=1),7)
            replay.assert_called_once()

    def test_empty_scope_and_busy_scope_do_not_spin(self):
        with patch.object(history,'advance',side_effect=TimeoutError('busy')) as step,patch.object(history,'_cursor',0):
            self.assertEqual(history.maintenance([],['1h']),0);step.assert_not_called()
            self.assertEqual(history.maintenance(['BTC'],['1h'],time_budget=10),0)
            self.assertEqual(step.call_count,1);self.assertEqual(history._cursor,1)

class HierarchicalReplay(unittest.TestCase):
    setUp=fixtures.RegimeHistory.setUp

    def test_real_engine_replay_and_decisions_use_the_same_ready_pair(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from Section_1_Global_Core import pipeline_scheduler as pipeline
        runner=object.__new__(pipeline.PipelineScheduler)
        runner.state={'__pipeline_existing__':['BTCUSDT']}
        decisions=Mock(return_value=0)
        runner.modules={pipeline.FEATURES:SimpleNamespace(maintenance=Mock(return_value=0),maintain_recent=Mock(return_value=0)),
            pipeline.ANALYTICS:live,pipeline.DECISIONS:SimpleNamespace(maintenance=decisions)}
        runner.existing=[];runner.new=[];runner.ready_pairs=set();runner.stage=None;runner.frontiers={}
        hashes=lambda:tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in (features_store.DB_PATH,klines_store.DB_PATH))
        before=hashes()
        with patch.object(data_policy,'active_symbols',return_value=['BTCUSDT']),patch.object(data_policy,'active_intervals',return_value=['1m']),patch.object(pipeline.time,'time',return_value=3910),patch.object(pipeline.update_klines,'update_all',return_value=0):
            for _ in range(20):
                runner.maintain()
                if decisions.called:break
            self.assertTrue(decisions.called)
            self.assertEqual(decisions.call_args.kwargs['pairs'],[('BTCUSDT','1m')])
            self.assertTrue(runner.allow_event(pipeline.DECISIONS+'.process_bar','BTCUSDT','1m'))
            # Same source prefix keeps completion; a repaired feature generation
            # invalidates it even when no new candle has arrived.
            key=('BTCUSDT','1m','REGIME')
            self.assertIn(key,live._status)
            self.assertEqual(hashes(),before)
            conn=features_store.open_db()
            with conn:conn.execute('UPDATE feature_calculation_versions SET generation=generation+1')
            conn.close()
            runner.invalidate_frontiers(['BTCUSDT'],['1m'],live)
            self.assertNotIn(key,live._status)
        # The only source mutation above was our explicit generation change.
        self.assertEqual(hashlib.sha256(klines_store.DB_PATH.read_bytes()).hexdigest(),before[1])

    def test_readiness_uses_checkpoints_repairs_history_and_freshness(self):
        from Section_1_Global_Core import pipeline_scheduler as pipeline
        from Section_1_Global_Core.memory_storage.Storage import klines_store
        with patch.object(pipeline.time,'time',return_value=3910):
            self.assertEqual(pipeline.pending_sources(['BTCUSDT'],['1m']),[])
            conn=features_store.open_db()
            with conn:conn.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('BTCUSDT','1m','next',64*60000,-1,'[]',None,'[]'))
            conn.close()
            self.assertEqual(pipeline.pending_sources(['BTCUSDT'],['1m']),[('BTCUSDT','1m')])
            conn=features_store.open_db()
            with conn:conn.execute('DELETE FROM feature_replay_jobs')
            conn.close()
            conn=klines_store.open_db()
            klines_store.ensure_history_progress(conn)
            with conn:conn.execute('INSERT OR REPLACE INTO history_progress(symbol,interval,next_open_time) VALUES (?,?,?)',('BTCUSDT','1m',60000))
            conn.close()
            self.assertEqual(pipeline.pending_sources(['BTCUSDT'],['1m']),[('BTCUSDT','1m')])
        conn=klines_store.open_db()
        with conn:conn.execute('DELETE FROM history_progress')
        conn.close()
        with patch.object(pipeline.time,'time',return_value=10000):
            self.assertEqual(pipeline.pending_sources(['BTCUSDT'],['1m']),[('BTCUSDT','1m')])
