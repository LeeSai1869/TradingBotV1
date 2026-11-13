from contextlib import ExitStack,nullcontext
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core import work_priority
from Section_1_Global_Core.memory_storage.Storage import klines_store,features_store
from Section_4_Features import processor


class FairService(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.raw=Path(self.temp.name)/'k.db';self.features=Path(self.temp.name)/'f.db'
        with sqlite3.connect(self.raw) as c:
            c.execute('CREATE TABLE klines(symbol,interval,open_time,PRIMARY KEY(symbol,interval,open_time))')
            c.execute('CREATE TABLE history_progress(symbol,interval,next_open_time)')
            for s in ('BTC','ENA','SUI'):
                c.executemany('INSERT INTO klines VALUES (?,?,?)',[(s,'1m',i) for i in range(5)])
                c.execute('INSERT INTO history_progress VALUES (?,?,?)',(s,'1m',5))
        with sqlite3.connect(self.features) as c:
            c.execute('CREATE TABLE feature_engine_state(symbol,interval,last_open_time)')
            c.executemany('INSERT INTO feature_engine_state VALUES (?,?,?)',[(s,'1m',0) for s in ('BTC','ENA','SUI')])
        self.stack.enter_context(patch.object(klines_store,'DB_PATH',self.raw));self.stack.enter_context(patch.object(features_store,'DB_PATH',self.features))
        work_priority._service_cursors.clear()

    def test_nonowners_download_and_calculate_even_when_bulk_owner_never_finishes(self):
        for kind in ('downloads','features'):
            turns=[work_priority.service_pair(['BTC','ENA','SUI'],['1m'],'BTC',kind) for _ in range(6)]
            self.assertEqual(turns,[('ENA','1m'),('SUI','1m')]*3)
        self.assertEqual(work_priority.work_symbol(['BTC','ENA','SUI'],['1m']),'BTC')

    def test_features_wait_for_actual_raw_prefix_without_skipping_a_gap(self):
        with sqlite3.connect(self.raw) as c:c.execute("UPDATE history_progress SET next_open_time=1 WHERE symbol='ENA'")
        turns=[work_priority.service_pair(['BTC','ENA','SUI'],['1m'],'BTC','features') for _ in range(3)]
        self.assertEqual(turns,[('SUI','1m')]*3)
        with sqlite3.connect(self.raw) as c:c.execute("UPDATE history_progress SET next_open_time=5 WHERE symbol='ENA'")
        self.assertIn(('ENA','1m'),[work_priority.service_pair(['BTC','ENA','SUI'],['1m'],'BTC','features') for _ in range(2)])

    def test_maintenance_reserves_a_turn_but_keeps_bulk_owner_working(self):
        calls=[]
        def advance(s,t,*args):calls.append(s);return 10
        with patch.object(processor,'_recover_runtime_format_job'),patch.object(processor,'_advance',side_effect=advance),patch.object(processor,'_repair_daily'),patch.object(work_priority,'work_symbol',return_value='BTC'):
            processor.maintenance(['BTC','ENA','SUI'],['1m'],time_budget=10)
            processor.maintenance(['BTC','ENA','SUI'],['1m'],time_budget=10)
        self.assertEqual(calls,['ENA','BTC','SUI','BTC'])

    def test_resource_handles_close_on_each_early_return(self):
        original=sqlite3.connect;opened=[]
        def track(*a,**k):c=original(*a,**k);opened.append(c);return c
        with patch.object(work_priority.sqlite3,'connect',side_effect=track):
            for _ in range(100):work_priority.service_pair(['BTC','ENA','SUI'],['1m'],'BTC','features')
        for conn in opened:
            with self.assertRaises(sqlite3.ProgrammingError):conn.execute('SELECT 1')

    def test_downloader_services_ena_and_sui_before_resuming_bulk_btc(self):
        from unittest.mock import MagicMock
        from Section_1_Global_Core.memory_storage.market_data import update_klines as updater
        with patch.object(updater,'DB_PATH',self.raw),patch.object(updater,'_HISTORY_PHASE',0),patch.object(updater,'_open_db',return_value=MagicMock()),patch.object(updater,'_audit_runner',None),patch.object(updater.data_policy,'active_symbols',return_value=['BTC','ENA','SUI']),patch.object(updater.data_policy,'active_intervals',return_value=['1m']),patch.object(updater,'update_one',return_value=1) as update:
            self.assertEqual(updater.update_all(time_budget=10),5)
            self.assertEqual(updater.update_all(time_budget=10),5)
        historical=[call.args[:2] for call in update.call_args_list if not call.kwargs.get('latest_only')]
        self.assertEqual(historical,[('ENA','1m'),('BTC','1m'),('BTC','1m'),('SUI','1m')])

    def test_fast_targeted_service_does_not_consume_the_bulk_owners_row_quota(self):
        calls=[]
        def advance(s,t,*args):calls.append((s,args[0]));return 250 if s=='ENA' else 10
        with patch.object(processor,'_recover_runtime_format_job'),patch.object(processor,'_advance',side_effect=advance),patch.object(processor,'_repair_daily'),patch.object(work_priority,'work_symbol',return_value='BTC'):
            count=processor.maintenance(['BTC','ENA','SUI'],['1m'],max_bars=200,time_budget=10)
        self.assertEqual(calls,[('ENA',50),('BTC',150)]);self.assertEqual(count,260)

    def test_slow_history_requests_cannot_starve_bulk_or_background(self):
        from unittest.mock import MagicMock
        from Section_1_Global_Core.memory_storage.market_data import update_klines as updater
        clock=[0.];history=[]
        def update(s,t,conn,*,latest_only=False):
            if not latest_only:history.append(s);clock[0]+=2
            return 1
        with patch.object(updater,'DB_PATH',self.raw),patch.object(updater,'_HISTORY_PHASE',0),patch.object(updater,'_open_db',return_value=MagicMock()),patch.object(updater,'_audit_runner',None),patch.object(updater.data_policy,'active_symbols',return_value=['BTC','ENA']),patch.object(updater.data_policy,'active_intervals',return_value=['1m']),patch.object(updater,'update_one',side_effect=update),patch.object(updater.time,'monotonic',side_effect=lambda:clock[0]):
            for _ in range(4):updater.update_all(time_budget=1)
        self.assertEqual(history,['ENA','BTC','ENA','BTC'])

    def test_normal_maintenance_can_consume_a_full_download_page(self):
        def advance(symbol,interval,cap,deadline):return min(1000,cap)
        with patch.object(processor,'_recover_runtime_format_job'),patch.object(processor,'_advance',side_effect=advance) as work,patch.object(processor,'_repair_daily'),patch.object(work_priority,'work_symbol',return_value='BTC'):
            count=processor.maintenance(['BTC'],['1m'],time_budget=10)
        self.assertEqual(count,1000)
        self.assertEqual(work.call_count,1)

    def test_near_current_turns_alternate_with_targeted_background_repair(self):
        from Section_4_Features.execution.components import current_signature
        with sqlite3.connect(self.features) as c:
            c.execute('CREATE TABLE feature_calculation_versions(symbol,interval,signature)')
            c.executemany('INSERT INTO feature_calculation_versions VALUES (?,?,?)',[(s,'1m',current_signature()) for s in ('BTC','ENA','SUI')])
            c.execute('CREATE TABLE feature_replay_jobs(symbol,interval)')
            c.execute("INSERT INTO feature_replay_jobs VALUES ('ENA','1m')")
        work_priority._live_cursors.clear();work_priority._service_phases.clear()
        turns=[work_priority.service_pair(['BTC','ENA','SUI'],['1m'],'BTC','features') for _ in range(4)]
        self.assertEqual(turns,[('SUI','1m'),('ENA','1m'),('SUI','1m'),('SUI','1m')])
        # Near-current ENA cannot skip its pending repair to enter the live lane.
        self.assertEqual(turns[0],('SUI','1m'))
        with sqlite3.connect(self.raw) as c:
            c.executemany('INSERT INTO klines VALUES (?,?,?)',[('SUI','1m',i) for i in range(5,20)])
        work_priority._service_cursors.clear();work_priority._service_phases.clear()
        self.assertEqual(work_priority.service_pair(['BTC','ENA','SUI'],['1m'],'BTC','features'),('ENA','1m'))

    def test_priority_pair_keeps_same_coin_other_frames_in_background(self):
        with sqlite3.connect(self.raw) as c:c.execute("INSERT INTO klines VALUES ('BTC','5m',0)")
        turn=work_priority.service_pair(['BTC'],['1m','5m'],'BTC','features',owner_interval='1m')
        self.assertEqual(turn,('BTC','5m'))

    def test_pending_priority_releases_only_after_checkpoint_and_generation_match(self):
        from Section_4_Features.execution.components import current_signature
        self.assertTrue(work_priority.pending_feature_pair('BTC','1m'))
        with sqlite3.connect(self.features) as c:
            c.execute("UPDATE feature_engine_state SET last_open_time=4 WHERE symbol='BTC'")
            c.execute('CREATE TABLE feature_calculation_versions(symbol,interval,signature)')
            c.execute('INSERT INTO feature_calculation_versions VALUES (?,?,?)',('BTC','1m',current_signature()))
            c.execute('CREATE TABLE feature_replay_jobs(symbol,interval)')
        self.assertFalse(work_priority.pending_feature_pair('BTC','1m'))
        with sqlite3.connect(self.features) as c:c.execute("INSERT INTO feature_replay_jobs VALUES ('BTC','1m')")
        self.assertTrue(work_priority.pending_feature_pair('BTC','1m'))
        self.assertFalse(work_priority.pending_feature_pair('MISSING','1m'))

    def _current_versions(self):
        from Section_4_Features.execution.components import current_signature
        with sqlite3.connect(self.features) as c:
            c.execute('CREATE TABLE feature_calculation_versions(symbol,interval,signature)')
            c.executemany('INSERT INTO feature_calculation_versions VALUES (?,?,?)',[(s,'1m',current_signature()) for s in ('BTC','ENA','SUI')])
            c.execute('CREATE TABLE feature_replay_jobs(symbol,interval)')
        work_priority._live_cursors.clear();work_priority._service_phases.clear()

    def test_recent_feature_burst_finishes_multiple_small_updates_before_bulk(self):
        self._current_versions();calls=[]
        def advance(s,t,cap,deadline):
            calls.append((s,cap))
            if s!='BTC':
                with sqlite3.connect(self.features) as c:c.execute('UPDATE feature_engine_state SET last_open_time=4 WHERE symbol=?',(s,))
                return 1
            return 10
        with patch.object(processor,'_recover_runtime_format_job'),patch.object(processor,'_advance',side_effect=advance),patch.object(processor,'_repair_daily'),patch.object(work_priority,'work_symbol',return_value='BTC'):
            count=processor.maintenance(['BTC','ENA','SUI'],['1m'],max_bars=200,time_budget=10)
        self.assertEqual([s for s,_ in calls],['ENA','SUI','BTC'])
        self.assertEqual(count,12);self.assertEqual(calls[-1][1],198)

    def test_recent_lane_cannot_admit_repairs_long_backlogs_or_excluded_pairs(self):
        self._current_versions()
        with sqlite3.connect(self.features) as c:c.execute("INSERT INTO feature_replay_jobs VALUES ('ENA','1m')")
        with sqlite3.connect(self.raw) as c:c.executemany('INSERT INTO klines VALUES (?,?,?)',[('SUI','1m',i) for i in range(5,20)])
        self.assertIsNone(work_priority.service_pair(['BTC','ENA','SUI'],['1m'],'BTC','features',live_only=True))
        with sqlite3.connect(self.raw) as c:c.execute("DELETE FROM klines WHERE symbol='SUI' AND open_time>=5")
        self.assertEqual(work_priority.service_pair(['BTC','ENA','SUI'],['1m'],'BTC','features',live_only=True),('SUI','1m'))
        self.assertIsNone(work_priority.service_pair(['BTC','ENA','SUI'],['1m'],'BTC','features',live_only=True,exclude={('SUI','1m')}))

    def test_slow_first_service_keeps_burst_inside_existing_time_slice(self):
        self._current_versions();clock=[0.];calls=[]
        def advance(s,t,*args):calls.append(s);clock[0]+=.3;return 1
        with patch.object(processor,'_recover_runtime_format_job'),patch.object(processor,'_advance',side_effect=advance),patch.object(processor,'_repair_daily'),patch.object(work_priority,'work_symbol',return_value='BTC'),patch.object(processor.time,'monotonic',side_effect=lambda:clock[0]):
            processor.maintenance(['BTC','ENA','SUI'],['1m'],max_bars=200,time_budget=1)
        self.assertEqual(calls,['ENA','BTC'])

    def test_dedicated_recent_turn_includes_owner_and_excludes_selective_repairs(self):
        self._current_versions()
        with sqlite3.connect(self.features) as c:c.execute("INSERT INTO feature_replay_jobs VALUES ('ENA','1m')")
        with patch.object(processor,'_advance',return_value=4) as advance:
            self.assertEqual(processor.maintain_recent(['BTC','ENA','SUI'],['1m'],time_budget=10),8)
        self.assertEqual({c.args[:2] for c in advance.call_args_list},{('BTC','1m'),('SUI','1m')})
        self.assertTrue(all(c.args[2]<=12 for c in advance.call_args_list))

    def test_dedicated_recent_turn_retains_raw_prefix_and_time_budget(self):
        self._current_versions()
        with sqlite3.connect(self.raw) as c:c.execute("UPDATE history_progress SET next_open_time=1")
        with patch.object(processor,'_advance') as advance:
            self.assertEqual(processor.maintain_recent(['BTC','ENA','SUI'],['1m'],time_budget=10),0)
            advance.assert_not_called()
        with sqlite3.connect(self.raw) as c:c.execute("UPDATE history_progress SET next_open_time=5")
        clock=[0.]
        def slow(*a):clock[0]+=1;return 1
        with patch.object(processor.time,'monotonic',side_effect=lambda:clock[0]),patch.object(processor,'_advance',side_effect=slow) as advance:
            self.assertEqual(processor.maintain_recent(['BTC','ENA','SUI'],['1m'],time_budget=.5),1)
            self.assertEqual(advance.call_count,1)
