"""Same-candle indexed joins, immutable history, no redundant dependency replays."""
import json
import unittest
from unittest.mock import patch
import test_regime_history as fixtures
from Section_1_Global_Core import regime_research as research,aggregation_processor,bias_processor
from Section_1_Global_Core.memory_storage.Storage import engine_store
from Section_1_Global_Core.liquidity import store as recorded
from Section_5_Market_Regime.engines import bias


class BiasHistory(unittest.TestCase):
    def setUp(self):
        fixtures.RegimeHistory.setUp(self)
        self.enterContext(patch.object(recorded,'DB_PATH',self.root/'recorded.db'))

    def publish(self):
        self.runs={}
        for name in bias.DEPENDENCIES:
            for _ in range(5):
                row=research.catch_up('BTCUSDT','1m',limit=200,engine_name=name,now_ms=10**9)
                if not row['processed']:break
            self.runs[name]=row
            aggregation_processor.observe('BTCUSDT','1m',name,row,now_ms=10**9+1)

    def test_common_recent_seed_resume_exact_replay_and_minimal_public_inputs(self):
        self.publish()
        with patch.object(research,'catch_up',side_effect=AssertionError('Bias must not replay other engines')):
            first=bias_processor.catch_up('BTCUSDT','1m',since=None,limit=20,now_ms=10**9+1)
            second=bias_processor.catch_up('BTCUSDT','1m',since=None,limit=20,now_ms=10**9+1)
        self.assertEqual(first['processed'],20);self.assertEqual(second['processed'],12);self.assertEqual(first['run_id'],second['run_id']);self.assertEqual(first['dependency_processed'],0)
        conn=engine_store.open_db();state=None
        try:
            rows=conn.execute('SELECT candle_time,payload FROM engine_results WHERE run_id=? ORDER BY candle_time',(first['run_id'],)).fetchall()
            for row in rows:
                snapshot=engine_store.input_bundle(conn,first['run_id'],row[0]);snapshot['computed_at']=10**9+1
                self.assertNotIn('candle',snapshot)
                self.assertEqual(set(snapshot['dependencies']),set(bias.DEPENDENCIES))
                expected,state=bias.evaluate(snapshot,previous_state=state);self.assertEqual(expected,json.loads(row[1]))
                for name,dep in snapshot['dependencies'].items():
                    self.assertEqual(dep['candle_open_time'],row[0]);self.assertEqual(dep['identity'],snapshot['identity'])
                    self.assertTrue(snapshot['dependency_refs'][name].startswith(self.runs[name]['run_id']+':'))
                    if name in ('REGIME','TREND','MOMENTUM','STRUCTURE','PARTICIPATION','PHASE'):self.assertNotIn('measurements',dep)
            self.assertEqual(state,engine_store.load(conn,first['run_id'])[1])
        finally:conn.close()
        self.assertIn('bias_counts',research.diagnostics(first['run_id']))

    def test_no_bindings_or_backlogged_candle_does_not_persist_false_missingness(self):
        empty=research.catch_up('BTCUSDT','1m',since=None,engine_name='BIAS',now_ms=10**9+1)
        self.assertEqual(empty['processed'],0);self.assertIn('Waiting for indexed',empty['status'])
        self.publish();conn=engine_store.open_db()
        try:
            with conn:conn.execute('DELETE FROM engine_results WHERE run_id=? AND candle_time=?',(self.runs['PHASE']['run_id'],33*60000))
        finally:conn.close()
        row=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='BIAS',now_ms=10**9+1)
        self.assertEqual(row['processed'],0);self.assertIn('same-candle PHASE',row['status'])
        conn=engine_store.open_db()
        try:self.assertFalse(any(json.loads(row[0])['engine']=='BIAS' for row in conn.execute('SELECT metadata FROM engine_runs')))
        finally:conn.close()

    def test_producer_changes_and_epoch_changes_wait_for_correct_generation(self):
        self.publish();real=aggregation_processor.generation
        with patch.object(aggregation_processor,'generation',side_effect=lambda name:'changed' if name=='TREND' else real(name)):
            row=bias_processor.catch_up('BTCUSDT','1m',now_ms=10**9+1)
        self.assertEqual(row['processed'],0);self.assertIn('TREND producer',row['status'])
        from Section_1_Global_Core import data_policy
        policy=data_policy.read();policy['epochs']['interval:1m']=1;data_policy.write(policy)
        row=bias_processor.catch_up('BTCUSDT','1m',now_ms=10**9+1)
        self.assertEqual(row['processed'],0);self.assertIn('data generation',row['status'])

    def test_parent_failure_does_not_erase_dependencies_or_leave_partial_checkpoint(self):
        self.publish();conn=engine_store.open_db()
        try:before=conn.execute('SELECT COUNT(*) FROM engine_results').fetchone()[0]
        finally:conn.close()
        with patch.object(bias,'evaluate',side_effect=RuntimeError('injected Bias failure')):
            with self.assertRaises(RuntimeError):bias_processor.catch_up('BTCUSDT','1m',since=None,limit=5,now_ms=10**9+1)
        conn=engine_store.open_db()
        try:self.assertEqual(conn.execute('SELECT COUNT(*) FROM engine_results').fetchone()[0],before)
        finally:conn.close()
        row=bias_processor.catch_up('BTCUSDT','1m',since=None,limit=5,now_ms=10**9+1)
        self.assertEqual(row['processed'],5)
