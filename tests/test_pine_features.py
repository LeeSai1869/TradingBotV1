"""Hand-calculated vectors from the supplied Pine operators and expressions."""
import unittest
import math
import pandas as pd
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch
from Section_4_Features.features import momentum, volatility
from Section_4_Features.execution import runtime
from Section_4_Features.execution.engine import Engine


class PineFeatureTests(unittest.TestCase):
    def test_store_migrates_without_removing_legacy_values(self):
        from Section_1_Global_Core.memory_storage.Storage import features_store
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'features.db'
            conn=sqlite3.connect(path)
            conn.executescript(features_store._SCHEMA)
            conn.execute("INSERT INTO features(symbol,interval,open_time,ema50) VALUES ('ETHUSDT','1m',0,123)")
            conn.commit();conn.close()
            with patch.object(features_store,'DB_PATH',path):
                conn=features_store.open_db()
                old=features_store.read_row(conn,'ETHUSDT','1m',0)
                self.assertEqual(old['ema50'],123)
                self.assertEqual(old['formula_version'],1)
                features_store.insert_rows(conn,[dict(symbol='ETHUSDT',interval='1m',open_time=60000,formula_version=2,ema_bull_structure=True,nearest_buy_vwap_type='UPPER_1')])
                new=features_store.read_row(conn,'ETHUSDT','1m',60000)
                self.assertEqual(new['formula_version'],2)
                self.assertEqual(new['ema_bull_structure'],1)
                self.assertEqual(new['nearest_buy_vwap_type'],'UPPER_1')
                conn.close()

    def test_rma_sma_seed_and_recurrence(self):
        state={}
        result = pd.Series([runtime.rma(state,"rma",v,3) for v in [1.,2.,3.,10.]])
        self.assertTrue(math.isnan(result.iloc[1]))
        self.assertEqual(result.iloc[2],2)
        self.assertAlmostEqual(result.iloc[3],14/3)

    def test_rsi_seed_uses_changes_not_first_price(self):
        state={}
        values=pd.Series([momentum.calculate_rsi(state,v,3) for v in [10.,11.,10.,12.,11.]])
        self.assertTrue(math.isnan(values.iloc[2]))
        self.assertAlmostEqual(values.iloc[3],75)
        self.assertAlmostEqual(values.iloc[4],100*6/11)

    def test_atr_and_dmi_have_different_first_true_range(self):
        frame=pd.DataFrame(dict(high=[10.,12.,11.,14.],low=[8.,9.,8.,10.],close=[9.,11.,9.,13.]))
        state={}
        a=pd.Series([volatility.calculate(state,row,2) for row in frame.to_dict("records")])
        self.assertEqual(a.iloc[1],2.5)
        state={}
        plus,minus,adx=(pd.Series(values) for values in zip(*[momentum.calculate_dmi(state,row,2,2) for row in frame.to_dict("records")]))
        self.assertTrue(math.isnan(plus.iloc[1]))
        self.assertAlmostEqual(plus.iloc[2],100/3)
        self.assertAlmostEqual(minus.iloc[2],50/3)
        self.assertTrue(math.isnan(adx.iloc[2]))
        self.assertAlmostEqual(adx.iloc[3],500/9)

    def test_candle_units_wicks_and_zero_range(self):
        engine=Engine('ETHUSDT','1m',{'atrLen':1})
        engine.step(dict(symbol='ETHUSDT',interval='1m',open_time=0,close_time=59999,open=10.,high=13.,low=8.,close=12.,volume=1.))
        result=engine.step(dict(symbol='ETHUSDT',interval='1m',open_time=60000,close_time=119999,open=11.,high=16.,low=9.,close=14.,volume=1.))
        self.assertEqual(result['candle_direction'],3)
        self.assertAlmostEqual(result['wick_ratio'],2/7)
        self.assertAlmostEqual(result['change_percent'],1/6)
        self.assertEqual(result['prev_candle_range'],5)
        self.assertAlmostEqual(result['directional_displacement'],3/7)
        flat=Engine('ETHUSDT','1m',{'atrLen':1}).step(dict(symbol='ETHUSDT',interval='1m',open_time=0,close_time=59999,open=5.,high=5.,low=5.,close=5.,volume=0.))
        self.assertEqual(flat['close_location'],.5)
        self.assertEqual(flat['wick_ratio'],0)

    def test_numbered_trend_structure_and_price_location_share_one_packet(self):
        engine=Engine('ETHUSDT','1m')
        engine.step(dict(symbol='ETHUSDT',interval='1m',open_time=0,close_time=59999,open=10.,high=12.,low=8.,close=10.,volume=1.))
        result=engine.step(dict(symbol='ETHUSDT',interval='1m',open_time=60000,close_time=119999,open=10.,high=11.,low=8.,close=8.,volume=1.))
        self.assertLess(result['vwap_distance'],0)
        self.assertIn('nearest_buy_vwap_type',result)
        self.assertIsNotNone(result['ema50'])
        self.assertIn('ema_bull_structure',result)
        self.assertIn('price_below_ema50',result)


if __name__=='__main__':unittest.main()
