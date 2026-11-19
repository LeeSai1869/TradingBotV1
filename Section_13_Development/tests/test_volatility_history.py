"""Real Core projection/SQLite typing and immutable automatic Volatility history."""
import json
import unittest
import test_regime_history as fixtures
from Section_1_Global_Core import regime_research as research
from Section_1_Global_Core.memory_storage.Storage import engine_store
from Section_5_Market_Regime.engines import volatility

class VolatilityHistory(unittest.TestCase):
    setUp=fixtures.RegimeHistory.setUp

    def test_recent_seed_resume_and_immutable_input_reproduction(self):
        first=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='VOLATILITY',now_ms=10**9)
        self.assertEqual(first['processed'],20);self.assertEqual(first['dependency_processed'],0)
        second=research.catch_up('BTCUSDT','1m',since=None,limit=20,engine_name='VOLATILITY',now_ms=10**9)
        self.assertEqual(first['run_id'],second['run_id']);self.assertEqual(second['processed'],12)
        self.assertEqual(second['latest']['classification']['level'],'UNKNOWN')  # Short percentile baseline is not filled.
        self.assertNotEqual(second['latest']['data_quality'],'INVALID')
        conn=engine_store.open_db();state=None
        try:
            for row in conn.execute('SELECT candle_time,payload FROM engine_results WHERE run_id=? ORDER BY candle_time',(first['run_id'],)):
                snap=engine_store.input_bundle(conn,first['run_id'],row[0]);snap['computed_at']=10**9
                expected,state=volatility.evaluate(snap,previous_state=state);self.assertEqual(expected,json.loads(row[1]))
            self.assertEqual(state,engine_store.load(conn,first['run_id'])[1])
        finally:conn.close()
        diagnostics=research.diagnostics(first['run_id']);self.assertIn('level_counts',diagnostics);self.assertNotIn('direction_counts',diagnostics)
