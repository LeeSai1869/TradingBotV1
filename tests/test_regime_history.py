"""Actual Core stores: bounded resume, immutable lineage, rollback and policy."""
import json
import unittest
from unittest.mock import patch
import test_data_admin as fixtures
from Section_1_Global_Core import regime_research as research,regime_inputs,data_policy
from Section_1_Global_Core.memory_storage.Storage import engine_store,features_store,db
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import checkpoint
from Section_4_Features.execution.components import current_signature
from Section_5_Market_Regime.engines import regime

class RegimeHistory(unittest.TestCase):
    def setUp(self):
        fixtures.DataAdminTests.setUp(self)
        self.enterContext(patch.object(engine_store,'DB_PATH',self.root/'intelligence.db'))
        from Section_1_Global_Core.memory_storage.Storage import klines_store
        conn=klines_store.open_db()
        with conn:conn.execute("DELETE FROM klines WHERE symbol='BTCUSDT' AND interval='1m'")
        conn.close()
        self.clients=[dict(symbol='BTCUSDT',interval='1m',open_time=i*60000,close_time=(i+1)*60000-1,
            open=100+i*.1,high=102+i*.1,low=99+i*.1,close=101+i*.1,volume=100.) for i in range(65)]
        db.write_klines(self.clients);engine=Engine('BTCUSDT','1m');db.write_features([engine.step(row) for row in self.clients])
        conn=features_store.open_db()
        with conn:
            conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('BTCUSDT','1m',64*60000,checkpoint.dump(engine,(0,0))))
            conn.execute('INSERT INTO feature_calculation_versions(symbol,interval,signature,generation) VALUES (?,?,?,0)',('BTCUSDT','1m',current_signature()))
        conn.close()

    def run_batch(self,**kwargs):return research.catch_up('BTCUSDT','1m',now_ms=10**9,**kwargs)

    def test_bounded_restart_matches_full_prefix_and_keeps_input_bundle(self):
        first=self.run_batch(limit=25);self.assertEqual(first['processed'],25)
        second=self.run_batch(limit=25);self.assertEqual(second['processed'],25);self.assertEqual(first['run_id'],second['run_id'])
        third=self.run_batch(limit=25);self.assertEqual(third['processed'],15)
        done=self.run_batch(limit=25);self.assertEqual(done['processed'],0)
        conn=engine_store.open_db();state=None
        try:
            rows=conn.execute('SELECT candle_time,payload FROM engine_results WHERE run_id=? ORDER BY candle_time',(first['run_id'],)).fetchall()
            self.assertEqual(len(rows),65)
            for row in rows:
                snapshot=engine_store.input_bundle(conn,first['run_id'],row['candle_time']);snapshot['computed_at']=10**9
                expected,state=regime.evaluate(snapshot,previous_state=state)
                self.assertEqual(json.loads(row['payload']),expected)
            self.assertEqual(engine_store.load(conn,first['run_id'])[1],state)
        finally:conn.close()
        self.assertEqual(research.diagnostics(first['run_id'])['candles'],65)
        self.assertEqual(third['latest']['provenance']['mode'],'HISTORICAL_RECONSTRUCTION')

    def test_pending_or_outdated_features_block_and_policy_pause_does_not_work(self):
        conn=features_store.open_db()
        with conn:conn.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('BTCUSDT','1m','next',64*60000,-1,'[]',None,'[]'))
        conn.close()
        self.assertEqual(self.run_batch()['processed'],0)
        conn=features_store.open_db()
        with conn:
            conn.execute('DELETE FROM feature_replay_jobs')
            conn.execute("UPDATE feature_calculation_versions SET signature='old'")
        conn.close();self.assertEqual(self.run_batch()['processed'],0)
        with patch.object(data_policy,'enabled',return_value=False):self.assertEqual(self.run_batch()['status'],'paused')

    def test_missing_middle_feature_stops_instead_of_skipping(self):
        conn=features_store.open_db()
        with conn:conn.execute("DELETE FROM features WHERE symbol='BTCUSDT' AND interval='1m' AND open_time=?",(5*60000,))
        conn.close();row=self.run_batch(limit=20)
        self.assertEqual(row['processed'],5);self.assertIn('Missing feature',row['status'])
        row=self.run_batch(limit=20);self.assertEqual(row['processed'],0)

    def test_batch_failure_is_atomic_and_stale_writer_cannot_advance_cursor(self):
        first=self.run_batch(limit=5);conn=engine_store.open_db()
        with conn:conn.execute('CREATE TRIGGER fail_result BEFORE INSERT ON engine_results BEGIN SELECT RAISE(ABORT,"test rollback"); END')
        conn.close()
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):self.run_batch(limit=5)
        conn=engine_store.open_db()
        try:
            self.assertEqual(engine_store.load(conn,first['run_id'])[0],4*60000)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM engine_input_bundles').fetchone()[0],5)
            metadata=json.loads(conn.execute('SELECT metadata FROM engine_runs WHERE run_id=?',(first['run_id'],)).fetchone()[0])
            with self.assertRaises(RuntimeError):engine_store.commit_batch(conn,metadata,-1,[],None)
            with conn:conn.execute('DROP TRIGGER fail_result')
        finally:conn.close()
        self.assertEqual(self.run_batch(limit=5)['processed'],5)

    def test_new_raw_revision_preserves_old_numerical_evidence_and_seed_identity(self):
        first=self.run_batch(limit=10);conn=engine_store.open_db();before=engine_store.input_bundle(conn,first['run_id'],0);conn.close()
        conn=features_store.open_db()
        with conn:conn.execute("UPDATE features SET adx=99 WHERE symbol='BTCUSDT' AND interval='1m' AND open_time=0")
        conn.close()
        second=self.run_batch(limit=10,revision='corrected-raw-1');self.assertNotEqual(first['run_id'],second['run_id'])
        conn=engine_store.open_db()
        try:
            self.assertEqual(engine_store.input_bundle(conn,first['run_id'],0),before)
            self.assertEqual(engine_store.input_bundle(conn,second['run_id'],0)['features']['adx'],99)
        finally:conn.close()
        seeded=self.run_batch(limit=10,since=5*60000)
        self.assertNotEqual(seeded['latest']['input_signature'],first['latest']['input_signature'])

    def test_store_rejects_same_key_divergence_and_cross_run_state(self):
        first=self.run_batch(limit=1);conn=engine_store.open_db()
        try:
            metadata=json.loads(conn.execute('SELECT metadata FROM engine_runs WHERE run_id=?',(first['run_id'],)).fetchone()[0])
            snapshot=engine_store.input_bundle(conn,first['run_id'],0);snapshot['computed_at']=10**9
            result,state=regime.evaluate(snapshot)
            with conn:conn.execute('UPDATE engine_runs SET cursor=-1,state=NULL WHERE run_id=?',(first['run_id'],))
            result['confidence']=.1234
            with self.assertRaisesRegex(ValueError,'divergence'):engine_store.commit_batch(conn,metadata,-1,[(snapshot,result)],state)
            self.assertEqual(engine_store.load(conn,first['run_id'])[0],-1)
            result,state=regime.evaluate(snapshot);state['identity']={**state['identity'],'market_type':'usdt_perpetual'}
            with self.assertRaisesRegex(ValueError,'binding'):engine_store.commit_batch(conn,metadata,-1,[(snapshot,result)],state)
        finally:conn.close()

    def test_cli_uses_multiple_bounded_transactions_and_reports_diagnostics(self):
        import run_regime,sys,io
        from contextlib import redirect_stdout
        output=io.StringIO()
        with patch.object(sys,'argv',['run_regime.py','--symbols','BTCUSDT','--intervals','1m','--max-bars','1000','--summary','--diagnostics']),redirect_stdout(output):
            run_regime.main()
        self.assertIn('+65',output.getvalue());self.assertIn('primary_counts',output.getvalue())
        self.assertIn('no BUY/SELL',output.getvalue())
