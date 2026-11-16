"""Lossless consolidation, safe resume, rollback and existing ADCN protection."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from Section_1_Global_Core import intelligence_migration as transfer
from Section_1_Global_Core.memory_storage.Storage import engine_store,json_storage,adcn_store


class IntelligenceMigration(unittest.TestCase):
    def sql(self,path):
        conn=sqlite3.connect(path);self.addCleanup(conn.close);return conn

    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.source=self.root/'intelligence.db';self.target=self.root/'ADCN.db'
        conn=sqlite3.connect(self.source)
        conn.executescript('''
            CREATE TABLE engine_runs(run_id TEXT PRIMARY KEY,metadata TEXT NOT NULL,cursor INTEGER NOT NULL,state TEXT);
            CREATE TABLE engine_input_bundles(bundle_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE engine_results(run_id TEXT REFERENCES engine_runs(run_id),candle_time INTEGER,
                bundle_id TEXT REFERENCES engine_input_bundles(bundle_id),deterministic TEXT NOT NULL,payload TEXT NOT NULL,
                PRIMARY KEY(run_id,candle_time));
            CREATE TABLE engine_live_seeds(seed_key TEXT PRIMARY KEY,candle_time INTEGER);
            CREATE TABLE mtf_bindings(id INTEGER PRIMARY KEY,symbol TEXT,timeframe TEXT,engine TEXT,
                known_ms INTEGER,generation TEXT,run_id TEXT,metadata TEXT);
            CREATE INDEX mtf_binding_lookup ON mtf_bindings(symbol,engine,timeframe,known_ms DESC,id DESC);
            CREATE TABLE mtf_sources(ref TEXT PRIMARY KEY,run_id TEXT,candle_time INTEGER,observed_ms INTEGER,payload TEXT,UNIQUE(run_id,candle_time));
            CREATE TABLE mtf_scopes(id TEXT PRIMARY KEY,metadata TEXT);
            CREATE TABLE mtf_input_bundles(id TEXT PRIMARY KEY,payload TEXT);
            CREATE TABLE mtf_results(id TEXT PRIMARY KEY,scope_id TEXT REFERENCES mtf_scopes(id),as_of INTEGER,
                bundle_id TEXT REFERENCES mtf_input_bundles(id),payload TEXT);
            CREATE TABLE mtf_latest(scope_id TEXT PRIMARY KEY,input_signature TEXT,result_id TEXT);
            CREATE TABLE engine_history_bindings(symbol TEXT,timeframe TEXT,engine TEXT,generation TEXT,
                run_id TEXT,metadata TEXT,status TEXT,updated_ms INTEGER,PRIMARY KEY(symbol,timeframe,engine));
        ''')
        self.metadata=dict(input_signature='signature',engine='REGIME',source_archive='engine source\n'*100,
            identity=dict(symbol='BTCUSDT',timeframe='1m'))
        self.run_id=engine_store.digest(self.metadata)
        with conn:
            conn.execute('INSERT INTO engine_runs VALUES (?,?,?,?)',(self.run_id,engine_store.encode(self.metadata),9,engine_store.encode(dict(last_open=9))))
            for candle in range(10):
                snapshot=dict(input_signature='signature',candle_open_time=candle,features=dict(adx=20+candle),
                    identity=self.metadata['identity'],source_versions=dict(archive='shared metadata '*100))
                bundle=engine_store.digest(snapshot)
                result=dict(engine='REGIME',candle_open_time=candle,computed_at=100,available_at=100,
                    confidence=candle/10,classification=dict(primary='TRENDING'),
                    provenance=dict(source_versions=snapshot['source_versions']))
                check=engine_store.encode(engine_store.stable_result(result)) if candle%2==0 else engine_store.result_checksum(result)
                conn.execute('INSERT INTO engine_input_bundles VALUES (?,?)',(bundle,engine_store.encode(snapshot)))
                conn.execute('INSERT INTO engine_results VALUES (?,?,?,?,?)',(self.run_id,candle,bundle,check,engine_store.encode(result)))
            conn.execute('INSERT INTO engine_live_seeds VALUES (?,?)',('seed',0))
            conn.execute('INSERT INTO mtf_bindings VALUES (1,?,?,?,?,?,?,?)',('BTCUSDT','1m','REGIME',100,'generation',self.run_id,'{}'))
            conn.execute('INSERT INTO mtf_sources VALUES (?,?,?,?,?)',('ref',self.run_id,9,100,engine_store.encode(result)))
            conn.execute('INSERT INTO mtf_scopes VALUES (?,?)',('scope','{}'))
            conn.execute('INSERT INTO mtf_input_bundles VALUES (?,?)',('bundle','{"timeframes":[]}'))
            conn.execute('INSERT INTO mtf_results VALUES (?,?,?,?,?)',('result','scope',100,'bundle','{"classification":"TRENDING"}'))
            conn.execute('INSERT INTO mtf_latest VALUES (?,?,?)',('scope','signature','result'))
            conn.execute('INSERT INTO engine_history_bindings VALUES (?,?,?,?,?,?,?,?)',('BTCUSDT','1m','REGIME','generation',self.run_id,'{}','processed',100))
        conn.close()
        with self.sql(self.target) as target:
            target.executescript("CREATE TABLE decisions(id INTEGER PRIMARY KEY,signal TEXT); INSERT INTO decisions VALUES (42,'BUY'); CREATE TABLE decision_evidence(payload TEXT); INSERT INTO decision_evidence VALUES ('preserve evidence');")

    def migrate(self,**kwargs):
        return transfer.run(self.source,self.target,until_complete=True,report=lambda *a,**k:None,**kwargs)

    def test_all_tables_round_trip_and_existing_decisions_stay_intact(self):
        before=self.source.read_bytes()
        result=self.migrate(batch_size=3)
        self.assertTrue(result['complete']);self.assertEqual(result['rows']['engine_results'],10)
        self.assertEqual(self.source.read_bytes(),before)
        src=sqlite3.connect(self.source);self.addCleanup(src.close)
        dst=json_storage.connect(self.target,readonly=True);self.addCleanup(dst.close)
        for table in transfer.JSON_COLUMNS:
            expected=src.execute('SELECT rowid,* FROM '+table+' ORDER BY rowid').fetchall()
            if table=='engine_results':
                expected=[(*row[:4],engine_store.result_checksum(json.loads(row[5])),row[5]) for row in expected]
            self.assertEqual(dst.execute('SELECT rowid,* FROM '+table+' ORDER BY rowid').fetchall(),expected,table)
        self.assertEqual(dst.execute('SELECT * FROM decisions').fetchall(),[(42,'BUY')])
        self.assertEqual(dst.execute('SELECT * FROM decision_evidence').fetchall(),[('preserve evidence',)])
        self.assertEqual(dst.execute('SELECT typeof(payload) FROM engine_results LIMIT 1').fetchone()[0],'blob')
        self.assertEqual(dst.execute('SELECT length(deterministic) FROM engine_results').fetchall(),[(71,)]*10)
        self.assertEqual(dst.execute('PRAGMA foreign_key_check').fetchall(),[])
        with patch.object(engine_store,'DB_PATH',self.target),patch.object(engine_store,'_DEFAULT_PATH',self.target),patch.object(engine_store,'LEGACY_DB_PATH',self.source):
            conn=engine_store.open_db();conn.close() # The retained source cannot block verified cutover.
            with closing(engine_store.open_readonly()) as reader:self.assertEqual(engine_store.latest(reader,self.run_id)['candle_open_time'],9)

    def test_resume_after_committed_batch_keeps_original_rowids_and_counts(self):
        first=transfer.Migration(self.source,self.target)
        try:
            first.step(batch_size=3) # engine_runs
            first.step(batch_size=3) # finish engine_runs
            result=first.step(batch_size=3)
            self.assertEqual((result['table'],result['rows']),('engine_input_bundles',3))
        finally:first.close()
        self.assertTrue(self.migrate(batch_size=2)['complete'])
        self.assertTrue(self.migrate(batch_size=2)['complete'])
        with self.sql(self.target) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM engine_results').fetchone()[0],10)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM engine_input_bundles').fetchone()[0],10)

    def test_failed_batch_rolls_back_then_resumes(self):
        migration=transfer.Migration(self.source,self.target)
        try:
            migration.step();migration.step()
            with migration.dest:migration.dest.execute('CREATE TRIGGER reject_copy BEFORE INSERT ON engine_input_bundles WHEN NEW.rowid=2 BEGIN SELECT RAISE(ABORT,"test rollback"); END')
            with self.assertRaises(sqlite3.IntegrityError):migration.step(batch_size=3)
            self.assertEqual(migration.dest.execute('SELECT COUNT(*) FROM engine_input_bundles').fetchone()[0],0)
            self.assertIsNone(migration.get('table:engine_input_bundles'))
            with migration.dest:migration.dest.execute('DROP TRIGGER reject_copy')
        finally:migration.close()
        self.assertTrue(self.migrate()['complete'])

    def test_changed_source_and_conflicting_destination_are_rejected(self):
        migration=transfer.Migration(self.source,self.target);migration.step();migration.close()
        with self.sql(self.source) as c:c.execute('UPDATE engine_runs SET cursor=10')
        with self.assertRaisesRegex(RuntimeError,'Source changed'):transfer.Migration(self.source,self.target)
        other=self.root/'conflict.db'
        with self.sql(other) as c:c.execute('CREATE TABLE engine_runs(value)')
        with self.assertRaisesRegex(ValueError,'already contains'):transfer.Migration(self.source,other)

    def test_disagreeing_duplicate_or_low_disk_cannot_complete_transfer(self):
        with self.sql(self.source) as c:c.execute("UPDATE engine_results SET deterministic='{}' WHERE candle_time=5")
        with self.assertRaisesRegex(ValueError,'mismatch'):self.migrate()
        with self.sql(self.target) as c:
            self.assertIsNone(c.execute("SELECT value FROM _section5_migration WHERE name='complete'").fetchone())
            self.assertEqual(c.execute('SELECT * FROM decisions').fetchall(),[(42,'BUY')])
        with self.assertRaisesRegex(RuntimeError,'disk space'):self.migrate(reserve_bytes=1<<70)

    def test_migration_guard_prevents_empty_replacement_and_default_is_adcn(self):
        self.assertIn(engine_store.DB_PATH,(adcn_store.DB_PATH,engine_store.LEGACY_DB_PATH))
        with patch.object(engine_store,'DB_PATH',self.target),patch.object(engine_store,'_DEFAULT_PATH',self.target),patch.object(engine_store,'LEGACY_DB_PATH',self.source):
            with self.assertRaisesRegex(RuntimeError,'needs migration'):engine_store.open_db()
        with self.sql(self.target) as c:
            self.assertIsNone(c.execute("SELECT 1 FROM sqlite_master WHERE name='engine_results'").fetchone())


if __name__=='__main__':unittest.main()
