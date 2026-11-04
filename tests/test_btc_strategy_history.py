import unittest
from Section_1_Global_Core import btc_strategy_history
from Section_1_Global_Core.memory_storage.Storage import features_store,klines_store
import test_regime_history as fixtures

class BTCStrategyHistory(unittest.TestCase):
    def setUp(self):
        fixtures.RegimeHistory.setUp(self)
        for store,tables in [(klines_store,['klines']),(features_store,['features','feature_engine_state','feature_calculation_versions'])]:
            conn=store.open_db()
            with conn:
                for table in tables:conn.execute('UPDATE '+table+" SET interval='5m' WHERE interval='1m'")
            conn.close()

    def test_read_only_closed_window_and_replay_guard(self):
        conn=features_store.open_db();before=conn.execute('SELECT COUNT(*),MAX(open_time) FROM features').fetchone();conn.close()
        packet=btc_strategy_history.history('BTCUSDT','5m',before=600000)
        self.assertEqual(packet['status'],'READY');self.assertEqual(packet['candles'],10)
        self.assertLess(packet['window_end'],600000)
        conn=features_store.open_db()
        self.assertEqual(before,conn.execute('SELECT COUNT(*),MAX(open_time) FROM features').fetchone())
        with conn:conn.execute("UPDATE feature_calculation_versions SET signature='old'")
        conn.close()
        blocked=btc_strategy_history.history('BTCUSDT','5m')
        self.assertEqual(blocked['status'],'UNAVAILABLE');self.assertFalse(blocked['trades'])
