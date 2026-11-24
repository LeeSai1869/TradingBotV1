"""Distinguish waiting from stale pipeline/quotes; diagnostics never alter stores."""
import json
import sqlite3
import unittest
from unittest.mock import patch
from Section_13_Development.tests import test_current_strategy_bot as fixture
from Section_1_Global_Core.memory_storage.Storage import adcn_store,features_store,klines_store
from Section_15_Execution_Bot.engine import Ledger
from Section_15_Execution_Bot.quotes import Quote
from Section_15_Execution_Bot.diagnostics import diagnose
from Section_15_Execution_Bot.reporting import Reporter


class BotDiagnostics(unittest.TestCase):
    setUp=fixture.CurrentStrategyBot.setUp
    seed=fixture.CurrentStrategyBot.seed
    config=fixture.CurrentStrategyBot.config
    prepare=fixture.CurrentStrategyBot.prepare

    def ready(self):
        cfg=self.prepare();self.ledger=Ledger(self.root/'bot.db');self.ledger.create(cfg,900000)
        self.ledger.enabled('ena',True,900000)
        self.ledger.step('ena',Quote('ENAUSDT','1','1',900001),None,900001)

    def test_waiting_status_is_verified_against_pipeline_and_quotes_without_writes(self):
        self.ready();paths=[self.ledger.path,adcn_store.DB_PATH,features_store.DB_PATH,klines_store.DB_PATH]
        before={p:p.read_bytes() for p in paths}
        result=diagnose(self.ledger.path,name='ena',now_ms=900002)[0]
        self.assertEqual(result['diagnosis'],'WAITING_FOR_NEW_CONFIRMED_BUY')
        self.assertEqual(result['pipeline']['decision_lag_seconds'],0)
        self.assertEqual(result['pipeline']['latest_signal_last_24h']['side'],'BUY')
        self.assertEqual(before,{p:p.read_bytes() for p in paths})

    def test_behind_decision_checkpoint_is_not_reported_as_no_signal(self):
        self.ready()
        with sqlite3.connect(adcn_store.DB_PATH) as c:
            state=json.loads(c.execute('SELECT state FROM decision_rule_state').fetchone()[0]);state['last']=300000
            c.execute('UPDATE decision_rule_state SET last_open_time=300000,state=?',(json.dumps(state),))
        result=diagnose(self.ledger.path,now_ms=900002)[0]
        self.assertEqual(result['diagnosis'],'DECISION_WORKER_BEHIND')
        self.assertEqual(result['pipeline']['decision_lag_seconds'],300)
        self.assertIsNone(result['pipeline']['latest_signal_last_24h'])

    def test_quote_and_candle_staleness_are_distinct(self):
        self.ready()
        self.assertEqual(diagnose(self.ledger.path,now_ms=920002)[0]['diagnosis'],'QUOTE_UNAVAILABLE_OR_STALE')
        self.assertEqual(diagnose(self.ledger.path,now_ms=1800000)[0]['diagnosis'],'MARKET_DATA_STALE')

    def test_feed_errors_are_explicit_and_missing_ledger_is_not_created(self):
        self.ready()
        with patch('Section_15_Execution_Bot.source.health',side_effect=sqlite3.OperationalError('database is locked')):
            row=diagnose(self.ledger.path,now_ms=900002)[0]
        self.assertEqual(row['diagnosis'],'STRATEGY_FEED_UNAVAILABLE')
        missing=self.root/'missing.db'
        with self.assertRaises(ValueError):diagnose(missing)
        self.assertFalse(missing.exists())


class BotReporting(unittest.TestCase):
    def test_repeated_idle_ticks_are_quiet_but_fills_errors_and_recovery_are_immediate(self):
        r=Reporter(30);idle=[{'account':'ena','paper_fills':[]}]
        self.assertEqual(r.packet(idle,0)['event'],'heartbeat')
        for i in range(1,30):self.assertIsNone(r.packet(idle,i))
        self.assertEqual(r.packet(idle,30)['event'],'heartbeat')
        error=[{'account':'ena','error':'Quote timed out','no_fill':True}]
        self.assertEqual(r.packet(error,31)['event'],'error')
        self.assertIsNone(r.packet(error,32))
        self.assertEqual(r.packet(idle,33)['event'],'recovered')
        fill=[{'account':'ena','paper_fills':[{'side':'BUY'}]}]
        self.assertEqual(r.packet(fill,34)['event'],'fill')
        self.assertIsNone(r.packet(idle,35))

    def test_account_named_error_does_not_create_false_recovery(self):
        r=Reporter(30);idle=[{'account':'error','paper_fills':[]}]
        r.packet(idle,0)
        self.assertEqual(r.packet(idle,30)['event'],'heartbeat')
