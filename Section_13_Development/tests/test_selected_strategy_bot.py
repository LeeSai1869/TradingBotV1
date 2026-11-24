"""Optional selected-instance adapter integration; current strategy tests are independent."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from Section_13_Development.tests import test_strategy_lifecycle as lifecycle
from Section_13_Development.tests.test_paper_bot import config,quote
from Section_15_Execution_Bot import source
from Section_15_Execution_Bot.engine import Ledger


class SourceIntegration(unittest.TestCase):
    setUp=lifecycle.StrategyLifecycle.setUp
    seed=lifecycle.StrategyLifecycle.seed
    prepare=lifecycle.StrategyLifecycle.prepare
    enable=lifecycle.StrategyLifecycle.enable
    def test_feed_is_readonly_current_selected_confirmed_and_pair_scoped(self):
        from Section_8_Decision_Engine import processor
        from Section_1_Global_Core import strategy_management as manager
        self.prepare();self.seed();identity=self.enable();processor.catch_up('ETHUSDT','1m')
        cfg=config(symbol='ETHUSDT',interval='1m',instance_id=identity)
        result=source.snapshot(cfg,-1);self.assertEqual(result['events'][0]['side'],'BUY')
        ledger=Ledger(Path(self.enterContext(tempfile.TemporaryDirectory()))/'bot.db')
        ledger.create(cfg,0);ledger.enabled('ena',True,0)
        now=result['events'][0]['close_time']+1
        self.assertEqual(ledger.step('ena',quote(now=now,symbol='ETHUSDT'),result,now)[0]['side'],'BUY')
        self.assertEqual(ledger.step('ena',quote(now=now,symbol='ETHUSDT'),result,now),[])
        self.assertEqual(source.snapshot(cfg,-1,armed_at=100000000)['events'],[])
        with self.assertRaises(ValueError):source.snapshot(replace(cfg,symbol='BTCUSDT'),-1)
        manager.change('deactivate',{'instance_id':identity})
        with self.assertRaises(ValueError):source.snapshot(cfg,-1)

    def test_current_mode_uses_selected_instance_and_never_falls_back_after_deactivation(self):
        from Section_8_Decision_Engine import processor
        from Section_1_Global_Core import strategy_management as manager
        self.prepare();self.seed();processor.catch_up('ETHUSDT','1m')
        cfg=source.bind_current(config(symbol='ETHUSDT',interval='1m',instance_id='current',strategy_source='current'))
        legacy=source.snapshot(cfg,-1)
        identity=self.enable();processor.catch_up('ETHUSDT','1m')
        managed=source.snapshot(cfg,-1)
        self.assertNotEqual(legacy['epoch'],managed['epoch'])
        self.assertEqual(managed['events'][0]['side'],'BUY')
        manager.change('deactivate',{'instance_id':identity})
        with self.assertRaisesRegex(ValueError,'enabled strategy'):source.snapshot(cfg,-1)
