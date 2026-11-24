"""Connect the unchanged, existing rule's committed ADCN signals to paper execution."""
from contextlib import redirect_stdout
from decimal import Decimal
import io
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from Section_13_Development.tests import test_di_decisions as fixtures
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import adcn_store,features_store,klines_store
from Section_8_Decision_Engine import processor
from Section_15_Execution_Bot import source
from Section_15_Execution_Bot.config import Config
from Section_15_Execution_Bot.engine import Ledger
from Section_15_Execution_Bot.quotes import Quote
from Section_15_Execution_Bot.__main__ import main


class CurrentStrategyBot(unittest.TestCase):
    setUp=fixtures.DiMemoryTests.setUp
    seed=fixtures.DiMemoryTests.seed

    def config(self,**kwargs):
        return source.bind_current(Config(**dict(dict(name='ena',symbol='ENAUSDT',interval='5m',instance_id='current',
            initial_capital='100',capital_cap='200',stop_loss_pct='10',take_profit_pct='50',
            fee_bps='0',slippage_bps='0',strategy_source='current'),**kwargs)))

    def prepare(self):
        self.seed(symbol='ENAUSDT',interval='5m',times=[0,300000,600000])
        with sqlite3.connect(klines_store.DB_PATH) as conn:conn.execute("UPDATE klines SET close_time=open_time+299999 WHERE symbol='ENAUSDT' AND interval='5m'")
        processor.catch_up('ENAUSDT','5m')
        return self.config()

    def test_existing_strategy_drives_buy_and_sell_without_new_selection_or_recalculation(self):
        cfg=self.prepare();ledger=Ledger(self.root/'bot.db');ledger.create(cfg,0);ledger.enabled('ena',True,0)
        before={p:p.read_bytes() for p in (adcn_store.DB_PATH,features_store.DB_PATH,klines_store.DB_PATH)}
        with patch.object(fixtures.rule,'evaluate',side_effect=AssertionError('Bot must not recalculate the strategy')):
            feed=source.snapshot(cfg,-1)
        self.assertEqual(feed['events'],[dict(open_time=600000,close_time=899999,side='BUY')])
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        self.assertEqual(ledger.step('ena',Quote('ENAUSDT','1','1',900000),feed,900000)[0]['reason'],'STRATEGY_BUY')
        self.assertEqual(ledger.step('ena',Quote('ENAUSDT','1','1',900000),feed,900000),[])
        values=[*fixtures.SETUP,fixtures.di(15,27),fixtures.di(30,10,adx=23,close=103),
            fixtures.di(35,11,adx=24,close=102),fixtures.di(27,15,adx=25,close=101)]
        self.seed(values,symbol='ENAUSDT',interval='5m',times=[i*300000 for i in range(len(values))])
        with sqlite3.connect(klines_store.DB_PATH) as conn:conn.execute("UPDATE klines SET close_time=open_time+299999 WHERE symbol='ENAUSDT' AND interval='5m'")
        processor.catch_up('ENAUSDT','5m')
        feed=source.snapshot(cfg,600000)
        self.assertEqual(feed['events'][-1]['side'],'SELL')
        self.assertEqual(ledger.step('ena',Quote('ENAUSDT','1.1','1.1',1800000),feed,1800000)[0]['reason'],'STRATEGY_SELL')
        self.assertEqual(Decimal(ledger.report()[0]['state']['cash']),110)

    def test_no_new_strategy_tables_are_required(self):
        cfg=self.prepare()
        with sqlite3.connect(adcn_store.DB_PATH) as conn:
            for table in ('strategy_events','strategy_checkpoints','strategy_instances','strategy_pairs','strategy_versions'):
                conn.execute('DROP TABLE IF EXISTS '+table)
        self.assertEqual(source.snapshot(cfg,-1)['events'][0]['side'],'BUY')
        with sqlite3.connect(adcn_store.DB_PATH) as conn:
            self.assertFalse(conn.execute("SELECT 1 FROM sqlite_master WHERE name='strategy_pairs'").fetchone())

    def test_policy_pair_age_and_current_checkpoint_bound_the_feed(self):
        cfg=self.prepare()
        self.assertEqual(source.snapshot(cfg,-1,armed_at=10000000)['events'],[])
        other=self.config(symbol='BTCUSDT')
        with self.assertRaisesRegex(ValueError,'checkpoint'):source.snapshot(other,-1)
        with patch.object(data_policy,'enabled',return_value=False):
            with self.assertRaisesRegex(ValueError,'inactive'):source.snapshot(cfg,-1)
        with patch.object(features_store,'decision_generation',return_value=1):
            with self.assertRaisesRegex(ValueError,'generation'):source.snapshot(cfg,-1)

    def test_rule_changes_block_new_orders_instead_of_silently_following_different_code(self):
        cfg=self.prepare();changed=self.root/'modified_rule.py';changed.write_text('# another strategy version')
        module=SimpleNamespace(__file__=str(changed),VERSION=fixtures.rule.VERSION,RULE_ID=fixtures.rule.RULE_ID)
        with patch.object(source,'_current_rule',return_value=module):
            with self.assertRaisesRegex(ValueError,'code changed'):source.snapshot(cfg,-1)

    def test_cli_defaults_to_the_existing_strategy_without_an_instance_id(self):
        from Section_15_Execution_Bot import __main__ as cli
        path=self.root/'cli-bot.db'
        argv=['bot','--db',str(path),'create','--name','ena','--symbol','ENAUSDT','--interval','5m',
            '--capital','100','--capital-cap','200','--stop-loss-pct','2','--take-profit-pct','4']
        with patch('sys.argv',argv),patch.object(cli.source,'snapshot',return_value={'events':[],'epoch':'test'}),redirect_stdout(io.StringIO()):main()
        row=Ledger(path).report()[0]
        self.assertEqual(row['config']['strategy_source'],'current')
        self.assertEqual(row['config']['instance_id'],'current')
        self.assertEqual(len(row['config']['strategy_fingerprint']),64)
        self.assertFalse(row['state']['enabled'])
