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

    def test_long_history_carries_position_into_small_visual_tail(self):
        from Section_1_Global_Core.memory_storage.Storage import db
        from test_btc_visual_strategy import setup,bar
        rows=setup()+[bar(n,o=100.4,h=100.5,l=100.3,c=100.4) for n in range(4,1105)]
        conn=klines_store.open_db()
        with conn:conn.execute("DELETE FROM klines WHERE symbol='BTCUSDT' AND interval='5m'")
        conn.close()
        db.write_klines([dict(symbol='BTCUSDT',interval='5m',volume=100,**{k:v for k,v in row.items() if k!='features'}) for row in rows])
        conn=features_store.open_db()
        fields=('symbol','interval','open_time','formula_version')+btc_strategy_history.FIELDS
        values=[]
        for row in rows:
            f=dict(measurement_version='shared-v1',measurement_config_id='test',measurement_gap=0,**row['features'])
            values.append(('BTCUSDT','5m',row['open_time'],3)+tuple(f.get(k) for k in btc_strategy_history.FIELDS))
        with conn:
            conn.execute("DELETE FROM features WHERE symbol='BTCUSDT' AND interval='5m'")
            conn.executemany('INSERT INTO features ('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')',values)
            conn.execute("UPDATE feature_engine_state SET last_open_time=? WHERE symbol='BTCUSDT' AND interval='5m'",(rows[-1]['open_time'],))
        conn.close()
        packet=btc_strategy_history.history('BTCUSDT','5m',limit=100,before=rows[-1]['close_time']+1,days=7)
        self.assertEqual(packet['candles'],1105)
        self.assertEqual(packet['display_candles'],100)
        self.assertEqual(len(packet['levels']),100)
        self.assertEqual(packet['trades'][0]['status'],'OPEN')
        self.assertLess(packet['trades'][0]['entry_time'],packet['levels'][0]['time'])
        self.assertEqual(packet['total_trades'],1)
        for days in (0,1,366):
            with self.assertRaises(ValueError):btc_strategy_history.history('BTCUSDT','5m',days=days)
