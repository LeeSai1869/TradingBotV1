"""User-specified two-candle DI recovery rule and closed-memory integration."""
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from Section_8_Decision_Engine.rules import di_spread_recovery as rule
from Section_8_Decision_Engine import processor
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import db,klines_store,features_store,adcn_store
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader


def di(plus,minus,spread=None):
    return dict(di_plus=plus,di_minus=minus,di_spread=abs(plus-minus) if spread is None else spread)

SETUP=[di(10,30),di(11,30)]


class DiRuleTests(unittest.TestCase):
    def test_two_setup_bars_and_closed_rise_fall_give_buy(self):
        self.assertEqual(rule.evaluate(SETUP,di(15,27))['signal_type'],'BUY')
        self.assertEqual(rule.evaluate(SETUP,di(14,28))['signal_type'],'BUY')  # +DI == spread

    def test_both_preceding_candles_must_qualify_strictly(self):
        for prior in ([di(15,30),SETUP[1]],[SETUP[0],di(16,30)],[di(0,30),SETUP[1]],[di(31,30),SETUP[1]]):
            self.assertIsNone(rule.evaluate(prior,di(15,27))['signal_type'])

    def test_spread_shrink_without_positive_di_rise_does_not_buy(self):
        self.assertIsNone(rule.evaluate(SETUP,di(11,20))['signal_type'])
        self.assertIsNone(rule.evaluate(SETUP,di(10,19))['signal_type'])

    def test_negative_di_must_fall_and_positive_di_must_cross_spread(self):
        for current in (di(16,30),di(17,31),di(12,29)):
            self.assertIsNone(rule.evaluate(SETUP,current)['signal_type'])

    def test_missing_invalid_or_short_history_is_warmup(self):
        for prior,current in ((SETUP[:1],di(15,27)),(SETUP,di(None,27,12)),
                              (SETUP,di(float('nan'),27,12)),(SETUP,di(15,float('inf'),12)),
                              ([di(-1,30),SETUP[1]],di(15,27))):
            self.assertEqual(rule.evaluate(prior,current)['decision_state'],'WARMUP')

    def test_buy_does_not_repeat_without_new_two_bar_setup(self):
        self.assertIsNone(rule.evaluate([SETUP[1],di(15,27)],di(16,26))['signal_type'])


class DiMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.stack=ExitStack();self.addCleanup(self.stack.close)
        for module,attr,value in ((klines_store,'DB_PATH',self.root/'klines.db'),(features_store,'DB_PATH',self.root/'features.db'),(adcn_store,'DB_PATH',self.root/'ADCN.db'),(downloader,'DB_PATH',self.root/'klines.db'),(data_policy,'LOCK_FILE',self.root/'policy.lock'),(data_policy,'POLICY_FILE',self.root/'policy.json')):
            self.stack.enter_context(patch.object(module,attr,value))
        self.stack.enter_context(patch.object(data_policy,'enabled',return_value=True))
        processor._CACHE.clear();processor._cursor=0
        downloader.open_db().close()

    def seed(self,values=(*SETUP,di(15,27)),symbol='ETHUSDT',interval='1m',times=None,cap=None):
        times=times or [i*60000 for i in range(len(values))]
        db.write_klines([dict(symbol=symbol,interval=interval,open_time=t,close_time=t+59999,open=100.,high=102.,low=98.,close=101.,volume=5.) for t in times])
        db.write_features([dict(symbol=symbol,interval=interval,open_time=t,formula_version=3,**value) for t,value in zip(times,values)])
        conn=features_store.open_db()
        conn.execute('INSERT OR REPLACE INTO feature_engine_state VALUES (?,?,?,?)',(symbol,interval,times[-1] if cap is None else cap,'{}'));conn.commit();conn.close()
        return times

    def test_latest_window_seeds_without_a_historical_replay_and_reaches_gateway(self):
        self.seed()
        self.assertEqual(processor.maintenance(['ETHUSDT'],['1m'],time_budget=2),1)
        row=db.read_adcn('ETHUSDT','1m',120000)
        self.assertEqual(row['signal_type'],'BUY');self.assertIsNone(row['final_score'])
        self.assertEqual(row['trigger'],rule.RULE_ID)
        page=db.read_state_page('ETHUSDT','1m')
        self.assertEqual(page['bars'][-1]['adcn']['signal_type'],'BUY')
        with sqlite3.connect(adcn_store.DB_PATH) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],1)
        processor._CACHE.clear()
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.seed([*SETUP,di(15,27),di(16,26)])
        self.assertTrue(processor.process_bar(SimpleNamespace(symbol='ETHUSDT',timeframe='1m',open_time=180000)))
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',180000)['signal_type'])

    def test_waits_for_feature_checkpoint_and_forming_candle_close(self):
        self.seed(cap=60000)
        processor.catch_up('ETHUSDT','1m')
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',120000))
        self.seed()
        with patch.object(processor.time,'time',return_value=179.999):
            self.assertFalse(processor.process_bar(SimpleNamespace(symbol='ETHUSDT',timeframe='1m',open_time=120000)))
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',120000))
        self.assertTrue(processor.process_bar(SimpleNamespace(symbol='ETHUSDT',timeframe='1m',open_time=120000)))
        self.assertEqual(db.read_adcn('ETHUSDT','1m',120000)['signal_type'],'BUY')

    def test_seed_gap_and_later_gap_require_two_new_setup_bars(self):
        self.seed(times=[0,120000,180000])
        processor.catch_up('ETHUSDT','1m')
        self.assertEqual(db.read_adcn('ETHUSDT','1m',180000)['decision_state'],'WARMUP')
        self.seed([*SETUP,di(15,27)],symbol='BTCUSDT')
        processor.catch_up('BTCUSDT','1m')
        self.seed([di(10,30),di(11,30),di(15,27)],symbol='BTCUSDT',times=[300000,360000,420000])
        processor.catch_up('BTCUSDT','1m')
        self.assertEqual(db.read_adcn('BTCUSDT','1m',300000)['decision_state'],'WARMUP')
        self.assertEqual(db.read_adcn('BTCUSDT','1m',420000)['signal_type'],'BUY')

    def test_failed_commit_does_not_advance_checkpoint_or_cached_history(self):
        self.seed()
        conn=adcn_store.open_db()
        conn.execute('CREATE TRIGGER reject_di BEFORE INSERT ON decisions BEGIN SELECT RAISE(ABORT,"injected decision failure"); END');conn.commit();conn.close()
        with self.assertRaises(sqlite3.IntegrityError):processor.catch_up('ETHUSDT','1m')
        conn=adcn_store.open_db()
        self.assertIsNone(adcn_store.read_rule_state(conn,'ETHUSDT','1m'))
        conn.execute('DROP TRIGGER reject_di');conn.commit();conn.close()
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),1)
        self.assertEqual(db.read_adcn('ETHUSDT','1m',120000)['signal_type'],'BUY')

    def test_disabled_pairs_wait_and_policy_epoch_change_prevents_commit(self):
        self.seed()
        with patch.object(data_policy,'enabled',return_value=False):self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        original=db.read_decision_inputs
        def changed(*args):
            result=original(*args)
            self.root.joinpath('policy.json').write_text(json.dumps({'epochs':{'symbol:ETHUSDT':1},'paused_coins':[],'timeframes':{}}))
            return result
        with patch.object(db,'read_decision_inputs',side_effect=changed):self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',120000))
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),1)

    def test_rule_updates_signal_without_erasing_other_engine_columns(self):
        self.seed()
        db.write_adcn([dict(symbol='ETHUSDT',interval='1m',open_time=120000,scalp_score=42,signal_type='SELL',final_score=88)])
        processor.catch_up('ETHUSDT','1m')
        row=db.read_adcn('ETHUSDT','1m',120000)
        self.assertEqual(row['signal_type'],'BUY');self.assertEqual(row['scalp_score'],42)
        self.assertIsNone(row['final_score'])

    def test_checkpoint_failure_rolls_back_decision_rows_too(self):
        self.seed()
        conn=adcn_store.open_db()
        conn.execute('CREATE TRIGGER reject_state BEFORE INSERT ON decision_rule_state BEGIN SELECT RAISE(ABORT,"injected checkpoint failure"); END');conn.commit();conn.close()
        with self.assertRaises(sqlite3.IntegrityError):processor.catch_up('ETHUSDT','1m')
        with sqlite3.connect(adcn_store.DB_PATH) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM decision_rule_state').fetchone()[0],0)

    def test_symbol_and_timeframe_history_is_isolated(self):
        self.seed();self.seed([di(10,30),di(11,30),di(12,29)],symbol='BTCUSDT')
        self.seed([di(10,30),di(11,30),di(12,29)],interval='5m')
        processor.maintenance(['ETHUSDT','BTCUSDT'],['1m','5m'],time_budget=3)
        self.assertEqual(db.read_adcn('ETHUSDT','1m',120000)['signal_type'],'BUY')
        self.assertIsNone(db.read_adcn('BTCUSDT','1m',120000)['signal_type'])
        self.assertIsNone(db.read_adcn('ETHUSDT','5m',120000)['signal_type'])
