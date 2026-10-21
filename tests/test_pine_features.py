"""Hand-calculated vectors from the supplied Pine operators and expressions."""
import unittest
import math
import pandas as pd
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch
from Section_4_Features.features import pine_math, rsi, atr, di_adx, candle, ema, trend, ema_structure, price_location, vwap


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
        result = pine_math.rma(pd.Series([1.,2.,3.,10.]),3)
        self.assertTrue(math.isnan(result.iloc[1]))
        self.assertEqual(result.iloc[2],2)
        self.assertAlmostEqual(result.iloc[3],14/3)

    def test_rsi_seed_uses_changes_not_first_price(self):
        values=rsi._rsi(pd.Series([10.,11.,10.,12.,11.]),3)
        self.assertTrue(math.isnan(values.iloc[2]))
        self.assertAlmostEqual(values.iloc[3],75)
        self.assertAlmostEqual(values.iloc[4],100*6/11)

    def test_atr_and_dmi_have_different_first_true_range(self):
        frame=pd.DataFrame(dict(high=[10.,12.,11.,14.],low=[8.,9.,8.,10.],close=[9.,11.,9.,13.]))
        a=atr._atr(frame.high,frame.low,frame.close,2)
        self.assertEqual(a.iloc[1],2.5)
        plus,minus,adx=di_adx._dmi(frame.high,frame.low,frame.close,2)
        self.assertTrue(math.isnan(plus.iloc[1]))
        self.assertAlmostEqual(plus.iloc[2],100/3)
        self.assertAlmostEqual(minus.iloc[2],50/3)
        self.assertTrue(math.isnan(adx.iloc[2]))
        self.assertAlmostEqual(adx.iloc[3],500/9)

    def test_candle_units_wicks_and_zero_range(self):
        frame=pd.DataFrame(dict(open=[10.,11.],high=[13.,16.],low=[8.,9.],close=[12.,14.]))
        result=candle.compute(frame,atr=2)
        self.assertEqual(result.candle_direction,3)
        self.assertAlmostEqual(result.wick_ratio,2/7)
        self.assertAlmostEqual(result.change_percent,1/6)
        self.assertEqual(result.prev_candle_range,5)
        self.assertEqual(result.directional_displacement,1.5)
        flat=candle.compute(pd.DataFrame(dict(open=[5.],high=[5.],low=[5.],close=[5.])),atr=0)
        self.assertEqual(flat.close_location,.5)
        self.assertEqual(flat.wick_ratio,0)

    def test_split_ema_contract_and_signed_vwap_distance(self):
        frame=pd.DataFrame(dict(time=[0,60000],open=[10.,10.],high=[12.,11.],low=[8.,8.],close=[10.,8.],volume=[1.,1.]))
        context=vars(trend.compute(frame))
        context.update(vars(ema_structure.compute(frame,context)))
        context.update(vars(price_location.compute(frame,context)))
        self.assertEqual(vars(ema.compute(frame)),context)
        result=vwap.compute(frame)
        self.assertLess(result.vwap_distance,0)
        self.assertEqual(result.nearest_buy_vwap_type,'LOWER_2')


if __name__=='__main__':unittest.main()
