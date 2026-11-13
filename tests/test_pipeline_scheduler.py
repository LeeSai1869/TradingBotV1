"""Pair readiness and recent catch-up must not become universe-wide barriers."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock,patch
from Section_1_Global_Core import pipeline_scheduler as p

class PipelineScheduling(TestCase):
    def setUp(self):
        self.calls=[]
        def module(name):
            def maintenance(*args,**kw):self.calls.append(name);return 0
            return SimpleNamespace(maintenance=Mock(side_effect=maintenance),maintain_recent=Mock(side_effect=maintenance))
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
        self.assertEqual(self.calls,[p.FEATURES,p.ANALYTICS,p.DECISIONS,p.FEATURES,p.FEATURES])
        self.assertEqual(self.mocks[-1].call_args.kwargs['symbols'],['NEW'])
        self.assertEqual(self.state['__pipeline_existing__'],['OLD','NEW'])
        self.assertTrue(self.runner.allow_event(p.DECISIONS+'.process_bar','OLD','5m'))

    def test_pending_pair_still_gets_bulk_service_without_downstream_or_new_initialization(self):
        self.mocks[-2].return_value=[('OLD','5m')]
        self.runner.maintain()
        self.assertEqual(self.calls,[p.FEATURES,p.FEATURES]);self.assertFalse(self.mocks[-1].call_args.kwargs['include_recent'])
        self.assertFalse(self.runner.allow_event(p.DECISIONS+'.process_bar','OLD','5m'))
        self.assertFalse(self.runner.allow_event(p.FEATURES+'.process_bar','NEW','5m'))

    def test_analytical_dependency_wait_does_not_block_feature_ready_decisions(self):
        self.mods[p.ANALYTICS].analytical_history._messages[('OLD','5m','REGIME')]='Waiting for market-data writer'
        self.runner.maintain()
        self.assertIn(p.DECISIONS,self.calls)
        self.assertTrue(self.runner.allow_event(p.DECISIONS+'.process_bar','OLD','5m'))

    def test_decision_backlog_precedes_new_coin(self):
        self.mods[p.DECISIONS].maintenance.side_effect=lambda *a,**k:100
        self.runner.maintain();self.assertEqual(self.mocks[-1].call_args.kwargs['symbols'],['OLD'])
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

    def test_mixed_symbol_and_timeframe_readiness_is_not_a_cartesian_barrier(self):
        self.state['__pipeline_existing__']=['OLD','NEW']
        self.mocks[2].return_value=['5m','1h']
        self.mocks[-2].return_value=[('OLD','1h'),('NEW','5m')]
        self.runner.maintain()
        ready=[('OLD','5m'),('NEW','1h')]
        for name in (p.ANALYTICS,p.DECISIONS):
            self.assertEqual(self.mods[name].maintenance.call_args.kwargs['pairs'],ready)
        self.assertTrue(self.runner.allow_event(p.DECISIONS+'.process_bar','OLD','5m'))
        self.assertFalse(self.runner.allow_event(p.DECISIONS+'.process_bar','OLD','1h'))
        self.assertTrue(self.runner.allow_event(p.DECISIONS+'.process_bar','NEW','1h'))
        self.assertFalse(self.runner.allow_event(p.DECISIONS+'.process_bar','NEW','5m'))

    def test_recent_candles_and_features_precede_bulk_work(self):
        order=[]
        self.mocks[-1].side_effect=lambda **kw:order.append('recent downloads' if kw.get('include_history') is False else 'bulk downloads') or 0
        self.mods[p.FEATURES].maintain_recent.side_effect=lambda *a,**kw:order.append('recent features') or 0
        self.mods[p.FEATURES].maintenance.side_effect=lambda *a,**kw:order.append('bulk features') or 0
        self.mods[p.DECISIONS].maintenance.side_effect=lambda *a,**kw:1
        self.runner.download();self.runner.maintain()
        self.assertEqual(order,['recent downloads','recent features','bulk downloads','bulk features'])

    def test_ready_pair_advances_while_other_pair_remains_blocked_across_turns(self):
        self.state['__pipeline_existing__']=['OLD','NEW']
        self.mocks[-2].return_value=[('NEW','5m')]
        for _ in range(3):self.runner.maintain()
        self.assertEqual(self.mods[p.ANALYTICS].maintenance.call_count,3)
        self.assertEqual(self.mods[p.ANALYTICS].maintenance.call_args.kwargs['pairs'],[('OLD','5m')])
        self.mocks[-2].return_value=[('OLD','5m')]
        self.runner.maintain()
        self.assertEqual(self.mods[p.ANALYTICS].maintenance.call_args.kwargs['pairs'],[('NEW','5m')])
        self.assertFalse(self.runner.allow_event(p.DECISIONS+'.process_bar','OLD','5m'))

    def test_bulk_repair_invalidates_event_readiness_in_the_same_turn(self):
        self.mocks[-2].side_effect=[[],[('OLD','5m')]]
        self.runner.maintain()
        self.assertEqual(self.mods[p.ANALYTICS].maintenance.call_args.kwargs['pairs'],[('OLD','5m')])
        self.assertFalse(self.runner.allow_event(p.DECISIONS+'.process_bar','OLD','5m'))

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

class PairFilters(TestCase):
    def test_live_history_and_decision_workers_use_exact_ready_pairs(self):
        from Section_1_Global_Core import analytical_processor as live,analytical_history as history
        from Section_8_Decision_Engine import processor as decisions
        ready=[('A','1m'),('B','1h')]
        result=dict(processed=0,status='caught up to committed feature prefix')
        with patch.object(live.regime_research,'catch_up',return_value=result) as catch,patch.object(history,'maintenance',return_value=0) as historical,patch.object(live,'_cursor',0),patch.object(live,'_status',{}):
            live.maintenance(['A','B'],['1m','1h'],pairs=ready,time_budget=10,max_pairs=100)
            self.assertEqual({c.args[:2] for c in catch.call_args_list},set(ready))
            self.assertEqual(historical.call_args.kwargs['pairs'],ready)
        with patch.object(history,'advance',return_value=result) as advance,patch.object(history,'_cursor',0),patch.object(history,'_messages',{}):
            history.maintenance(['A','B'],['1m','1h'],pairs=ready,time_budget=10,max_pairs=100)
            self.assertEqual({c.args[:2] for c in advance.call_args_list},set(ready))
        with patch.object(decisions,'_advance',return_value=0) as advance,patch.object(decisions,'_cursor',0),patch('Section_1_Global_Core.global_packet.recover_decision_evidence'):
            decisions.maintenance(['A','B'],['1m','1h'],pairs=ready,time_budget=10)
            self.assertEqual({c.args[:2] for c in advance.call_args_list},set(ready))

    def test_empty_ready_pairs_do_not_fall_back_to_whole_universe(self):
        from Section_1_Global_Core import analytical_processor as live,analytical_history as history
        from Section_8_Decision_Engine import processor as decisions
        with patch.object(live.regime_research,'catch_up') as catch,patch.object(history,'advance') as historical,patch.object(decisions,'_advance') as advance:
            live.maintenance(['A'],['1m'],pairs=[])
            history.maintenance(['A'],['1m'],pairs=[])
            decisions.maintenance(['A'],['1m'],pairs=[])
            catch.assert_not_called();historical.assert_not_called();advance.assert_not_called()
