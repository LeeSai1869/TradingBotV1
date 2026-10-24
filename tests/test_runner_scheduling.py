"""Large coin lists must yield between downloads and feature-event work."""
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock,patch
from Section_1_Global_Core.memory_storage.market_data import update_klines as updater
from Section_1_Global_Core import orchestrator


class DownloadSchedulingTests(TestCase):
    def test_current_refreshes_rotate_before_sticky_symbol_history(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'klines.db';path.touch()
            with patch.object(updater,'DB_PATH',path),patch.object(updater,'_DOWNLOAD_CURSOR',0),patch.object(updater,'_open_db',return_value=MagicMock()),patch.object(updater,'_audit_runner',None),patch('Section_1_Global_Core.work_priority.service_pair',return_value=None),patch.object(updater.data_policy,'active_symbols',return_value=['A','B','C']),patch.object(updater.data_policy,'active_intervals',return_value=['5m']),patch.object(updater,'update_one',return_value=1) as update:
                self.assertEqual(updater.update_all(max_pairs=2,time_budget=10),3)
                self.assertEqual(updater.update_all(max_pairs=2,time_budget=10),3)
                self.assertEqual(updater.update_all(max_pairs=2,time_budget=10),3)
                self.assertEqual([call.kwargs.get('latest_only',False) for call in update.call_args_list],[True,True,False]*3)
                self.assertEqual([call.args[:2] for call in update.call_args_list],[('A','5m'),('B','5m'),('A','5m'),('C','5m'),('A','5m'),('A','5m'),('B','5m'),('C','5m'),('A','5m')])

    def test_slow_request_yields_before_next_pair(self):
        clock=[0.]
        def download(*args,**kwargs):clock[0]+=3;return 1000
        with TemporaryDirectory() as directory:
            path=Path(directory)/'klines.db';path.touch()
            with patch.object(updater,'DB_PATH',path),patch.object(updater,'_DOWNLOAD_CURSOR',0),patch.object(updater,'_open_db',return_value=MagicMock()),patch.object(updater,'_audit_runner',None),patch.object(updater.data_policy,'active_symbols',return_value=['A','B']),patch.object(updater.data_policy,'active_intervals',return_value=['5m']),patch.object(updater.time,'monotonic',side_effect=lambda:clock[0]),patch.object(updater,'update_one',side_effect=download) as update:
                self.assertEqual(updater.update_all(time_budget=1),1000)
                self.assertEqual(update.call_count,1)
                self.assertEqual(updater.update_all(time_budget=1),1000)
                self.assertEqual(update.call_args.args[:2],('B','5m'))


class EventSchedulingTests(TestCase):
    def test_event_deadline_retains_cursor_and_next_pair_gets_a_turn(self):
        clock=[0.];received=[]
        def process(ev):received.append((ev.symbol,ev.open_time));clock[0]+=3
        def rows(symbol,interval,since):
            return [(t,t+59999,10,12,9,11,5) for t in (60000,120000) if t>since]
        with patch.object(orchestrator,'_load_state',return_value={'A|5m':0,'B|5m':0}),patch.object(orchestrator,'_load_processors',return_value=[('ad_hoc.processor',process)]),patch.object(orchestrator,'update_klines_all',return_value=0),patch.object(orchestrator,'_save_state'),patch.object(orchestrator,'_fetch_bars_since',side_effect=rows),patch.object(orchestrator.data_policy,'active_symbols',return_value=['A','B']),patch.object(orchestrator.data_policy,'active_intervals',return_value=['5m']),patch.object(orchestrator.data_policy,'enabled',return_value=True),patch.object(orchestrator.data_policy,'read',return_value={'epochs':{}}),patch.object(orchestrator.data_policy,'locked',side_effect=nullcontext),patch.object(orchestrator.time,'monotonic',side_effect=lambda:clock[0]):
            runner=orchestrator.GlobalCoreOrchestrator();runner.event_time_budget=1
            runner.cycle()
            self.assertEqual(received,[('A',60000)])
            self.assertEqual(runner._state['A|5m'],60000)
            runner.cycle()
            self.assertEqual(received,[('A',60000),('B',60000)])
            runner.cycle()
            self.assertEqual(received[-1],('A',120000))
            self.assertEqual(runner._state['B|5m'],60000)
