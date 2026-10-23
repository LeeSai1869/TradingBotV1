import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from Section_1_Global_Core.Symbols import daily_refresh,symbol_proposer


class DailyRefreshTests(unittest.TestCase):
    def test_success_persists_daily_deadline_and_failure_retries_without_registry_change(self):
        with TemporaryDirectory() as directory,patch.object(daily_refresh,'STATE',Path(directory)/'state.json'),patch.object(symbol_proposer,'propose') as propose:
            daily_refresh._run()
            propose.assert_called_once_with(notify=False)
            saved=daily_refresh.STATE.read_text()
            self.assertGreater(daily_refresh._next_attempt,time.time()+86000)
            propose.side_effect=RuntimeError('network offline')
            daily_refresh._run()
            self.assertEqual(daily_refresh.STATE.read_text(),saved)
            self.assertLess(daily_refresh._next_attempt,time.time()+3601)

    def test_tick_does_not_start_worker_before_persisted_deadline(self):
        with TemporaryDirectory() as directory,patch.object(daily_refresh,'STATE',Path(directory)/'state.json'),patch.object(daily_refresh,'_next_attempt',0),patch.object(daily_refresh,'_worker',None),patch.object(daily_refresh.threading,'Thread') as worker:
            import datetime
            daily_refresh.STATE.write_text(json.dumps({'last_success':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
            daily_refresh.tick();worker.assert_not_called()
