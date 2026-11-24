"""Real SQLite paper ledger; no exchange requests or live orders."""
from dataclasses import replace
from decimal import Decimal as D
import tempfile
import sqlite3
from pathlib import Path
import unittest
from unittest.mock import patch
from Section_15_Execution_Bot.config import Config
from Section_15_Execution_Bot.engine import Ledger
from Section_15_Execution_Bot.quotes import Quote
from Section_15_Execution_Bot.__main__ import turn
from Section_15_Execution_Bot import source


def config(**kwargs):
    return Config(**dict(dict(name='ena',symbol='ENAUSDT',interval='5m',instance_id='test',initial_capital='100',
        capital_cap='110',stop_loss_pct='10',take_profit_pct='20',fee_bps='0',slippage_bps='0'),**kwargs))


def quote(price='10',now=1000000,symbol='ENAUSDT'):return Quote(symbol,price,price,now)
def feed(side='BUY',stamp=900000,close=999999,epoch='v1'):
    return dict(epoch=epoch,events=[dict(side=side,open_time=stamp,close_time=close)])


class PaperLedger(unittest.TestCase):
    def setUp(self):
        self.tmp=self.enterContext(tempfile.TemporaryDirectory());self.ledger=Ledger(Path(self.tmp)/'paper.db')
        self.ledger.create(config(),800000);self.ledger.enabled('ena',True,800000)
    def state(self):return self.ledger.report('ena')[0]['state']
    def step(self,price='10',events=None,now=1000000):return self.ledger.step('ena',quote(price,now),events,now)
    def test_restart_duplicate_poll_and_signal_sell(self):
        self.assertEqual(self.step(events=feed())[0]['side'],'BUY')
        self.ledger=Ledger(self.ledger.path)
        self.assertEqual(self.step(events=feed()),[])
        fills=self.step('11',feed('SELL',stamp=1000000,close=1000999),1001000)
        self.assertEqual(fills[0]['reason'],'STRATEGY_SELL');self.assertEqual(D(self.state()['cash']),110)
        self.assertEqual(D(self.state()['realized_pnl']),10)
    def test_compounds_and_reserves_cash_above_entry_cap(self):
        self.step(events=feed());self.step('11',feed('SELL',1000000,1000999),1001000)
        self.step('10',feed('BUY',1001000,1001999),1002000)
        self.assertEqual(D(self.state()['cost']),110)
        self.step('11',feed('SELL',1002000,1002999),1003000)
        self.step('10',feed('BUY',1003000,1003999),1004000)
        self.assertEqual(D(self.state()['cost']),110);self.assertEqual(D(self.state()['cash']),11)
    def test_stop_and_take_profit_work_without_strategy_and_while_paused(self):
        self.step(events=feed());self.ledger.enabled('ena',False,1000000)
        fills=self.step('8',None,1001000)
        self.assertEqual(fills[0]['reason'],'STOP_LOSS');self.assertEqual(D(self.state()['quantity']),0)
        self.assertEqual(self.step(events=feed('BUY',1001000,1001999),now=1002000),[])
        self.ledger.enabled('ena',True,1002000)
        self.step(events=feed('BUY',1002000,1002999),now=1003000)
        self.assertEqual(self.step('13',None,1004000)[0]['reason'],'TAKE_PROFIT')
    def test_risk_exit_cannot_reenter_same_turn(self):
        self.step(events=feed())
        fills=self.step('8',feed('BUY',1000000,1000999),1001000)
        self.assertEqual(len(fills),1);self.assertEqual(D(self.state()['quantity']),0)
    def test_historical_stale_unclosed_and_wrong_quote_do_not_fill(self):
        self.assertEqual(self.step(events=feed(close=799999)),[])
        self.assertEqual(self.step(events=feed(stamp=950000,close=800001)),[])
        before=self.state()
        with self.assertRaises(ValueError):self.step(events=feed(stamp=999999,close=1000001))
        self.assertEqual(self.state(),before)
        for q in (quote(symbol='BTCUSDT'),quote(now=1),quote(now=1000001),quote('-1')):
            with self.assertRaises(ValueError):self.ledger.step('ena',q,feed(),1000000)
        self.assertEqual(self.state(),before)
    def test_epoch_change_halts_entries_but_preserves_protection(self):
        self.step(events=feed())
        self.step('10',feed('SELL',1000000,1000999,epoch='v2'),1001000)
        self.assertTrue(self.state()['halted']);self.assertGreater(D(self.state()['quantity']),0)
        self.assertEqual(self.step('8',None,1002000)[0]['reason'],'STOP_LOSS')
    def test_fee_and_slippage_reduce_equity_and_are_ledgered(self):
        self.ledger.create(config(name='fees',fee_bps='10',slippage_bps='5'),800000)
        self.ledger.enabled('fees',True,800000)
        self.ledger.step('fees',quote(),feed(),1000000)
        self.ledger.step('fees',quote(now=1001000),feed('SELL',1000000,1000999),1001000)
        state=self.ledger.report('fees')[0]['state']
        self.assertLess(D(state['cash']),100);self.assertLess(D(state['realized_pnl']),0)
        with self.ledger.connect() as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM fills WHERE account='fees'").fetchone()[0],2)
    def test_two_allocations_do_not_share_positions_or_cash(self):
        self.ledger.create(config(name='btc',symbol='BTCUSDT'),800000);self.ledger.enabled('btc',True,800000)
        self.step(events=feed())
        self.assertEqual(D(self.ledger.report('btc')[0]['state']['cash']),100)
        self.assertEqual(D(self.ledger.report('btc')[0]['state']['quantity']),0)
    def test_one_quote_failure_does_not_stop_other_allocations(self):
        self.ledger.create(config(name='btc',symbol='BTCUSDT'),800000);self.ledger.enabled('btc',True,800000)
        def fetch(symbol):
            if symbol=='ENAUSDT':raise OSError('network down')
            return quote(symbol=symbol)
        with patch.object(source,'snapshot',return_value=feed()):results=turn(self.ledger,fetch=fetch,now_ms=1000000)
        self.assertTrue(any('error' in r for r in results));self.assertGreater(D(self.ledger.report('btc')[0]['state']['quantity']),0)
    def test_locked_signal_database_does_not_disable_open_position_protection(self):
        self.step(events=feed())
        with patch.object(source,'snapshot',side_effect=sqlite3.OperationalError('database is locked')):
            results=turn(self.ledger,fetch=lambda symbol:quote('8',1001000),now_ms=1001000)
        self.assertTrue(any('warning' in r for r in results))
        self.assertEqual(D(self.state()['quantity']),0)
        self.assertEqual(self.ledger.history('ena')[0]['reason'],'STOP_LOSS')

    def test_offline_demo_cannot_touch_regular_ledger(self):
        from Section_15_Execution_Bot.demo import demonstrate
        before=self.ledger.path.read_bytes()
        with patch('urllib.request.urlopen',side_effect=AssertionError('No network permitted')):
            report=demonstrate()
        self.assertEqual(report['network_requests'],0)
        self.assertEqual([f['reason'] for f in reversed(report['fills'])],['STRATEGY_BUY','TAKE_PROFIT','STRATEGY_BUY','STOP_LOSS'])
        self.assertEqual(before,self.ledger.path.read_bytes())

    def test_invalid_capital_nan_and_live_mode_rejected(self):
        for values in ({'initial_capital':'NaN'},{'capital_cap':'10'},{'stop_loss_pct':'0'},{'mode':'live'},{'symbol':'BTCUSDT&foo=1'}):
            with self.assertRaises(ValueError):config(**values)
