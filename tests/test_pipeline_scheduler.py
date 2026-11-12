"""Stage barriers must survive restarts and never be bypassed by bar events."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from Section_1_Global_Core import pipeline_scheduler as p

class PipelineScheduling(TestCase):
    def setUp(self):
        self.calls=[]
        def module(name):
            def maintenance(*args,**kw):self.calls.append(name);return 0
            return SimpleNamespace(maintenance=Mock(side_effect=maintenance))
        self.mods={name:module(name) for name in (p.FEATURES,p.ANALYTICS,p.DECISIONS)}
        self.mods[p.ANALYTICS].analytical_history=SimpleNamespace(ENGINES=('REGIME',),_messages={('OLD','5m','REGIME'):'caught up to committed feature prefix'})
        self.mods[p.ANALYTICS]._status={('OLD','5m','REGIME'):'caught up to committed feature prefix'}
        self.patchers=[patch.object(p.importlib,'import_module',side_effect=lambda name:self.mods[name]),patch.object(p.data_policy,'active_symbols',return_value=['OLD','NEW']),patch.object(p.data_policy,'active_intervals',return_value=['5m']),patch.object(p,'checkpoint_symbols',return_value={'OLD'}),patch.object(p,'pending_sources',return_value=[]),patch.object(p.update_klines,'update_all',return_value=0)]
        self.mocks=[x.start() for x in self.patchers]
        for x in self.patchers:self.addCleanup(x.stop)
        self.state={};self.runner=p.PipelineScheduler(self.state)
        self.runner.invalidate_frontiers=Mock()

    def test_download_features_classifications_decisions_then_new_coin(self):
        self.runner.download();self.assertEqual(self.mocks[-1].call_args.kwargs['symbols'],['OLD'])
        self.runner.maintain()
        self.assertEqual(self.calls,[p.FEATURES,p.ANALYTICS,p.DECISIONS,p.FEATURES])
        self.assertEqual(self.mocks[-1].call_args.kwargs['symbols'],['NEW'])
        self.assertEqual(self.state['__pipeline_existing__'],['OLD','NEW'])
        self.assertTrue(self.runner.allow_event(p.DECISIONS+'.process_bar','OLD'))

    def test_pending_features_block_all_downstream_and_new_initialization(self):
        self.mocks[-2].return_value=[('OLD','5m')]
        self.runner.maintain()
        self.assertEqual(self.calls,[p.FEATURES]);self.mocks[-1].assert_not_called()
        self.assertFalse(self.runner.allow_event(p.DECISIONS+'.process_bar','OLD'))
        self.assertFalse(self.runner.allow_event(p.FEATURES+'.process_bar','NEW'))

    def test_dependency_wait_is_not_idle_capacity(self):
        self.mods[p.ANALYTICS].analytical_history._messages[('OLD','5m','REGIME')]='Waiting for market-data writer'
        self.runner.maintain()
        self.assertEqual(self.calls,[p.FEATURES,p.ANALYTICS]);self.mocks[-1].assert_not_called()
        self.assertFalse(self.runner.events_allowed)

    def test_decision_backlog_precedes_new_coin(self):
        self.mods[p.DECISIONS].maintenance.side_effect=lambda *a,**k:100
        self.runner.maintain();self.mocks[-1].assert_not_called()
        self.assertNotIn('NEW',self.state['__pipeline_existing__'])

    def test_new_coin_with_partial_features_stays_new_after_restart(self):
        self.state['__pipeline_existing__']=['OLD']
        self.mocks[3].return_value={'OLD','NEW'}
        restarted=p.PipelineScheduler(self.state)
        self.assertEqual(restarted.cohorts(),(['OLD'],['NEW']))

    def test_cold_start_initializes_one_coin(self):
        self.mocks[3].return_value=set()
        self.runner.download()
        self.assertEqual(self.mocks[-1].call_args.kwargs['symbols'],['OLD'])
        self.runner.maintain()
        self.assertEqual(self.calls,[p.FEATURES])
        self.assertEqual(self.state['__pipeline_existing__'],['OLD'])

class AnalyticalCapacity(TestCase):
    def test_history_can_use_more_than_the_old_two_hundred_row_cap(self):
        from Section_1_Global_Core import analytical_history as history
        row=dict(processed=100,status='processed',latest={})
        with patch.object(history,'advance',return_value=row) as advance,patch.object(history,'_messages',{}):
            rows=history.maintenance(['BTC'],['1h'],max_bars=1000,time_budget=10,max_pairs=100)
            self.assertEqual(rows,1000)
            self.assertEqual(advance.call_count,10)

    def test_completed_scopes_do_not_spend_writer_turns(self):
        from Section_1_Global_Core import analytical_history as history
        done={(s,'1h',e):'caught up to committed feature prefix' for s in ['BTC'] for e in history.ENGINES}
        with patch.object(history,'advance') as advance,patch.object(history,'_messages',done):
            self.assertEqual(history.maintenance(['BTC'],['1h'],max_bars=100000,time_budget=3,max_pairs=10000,skip_complete=True),0)
            advance.assert_not_called()
