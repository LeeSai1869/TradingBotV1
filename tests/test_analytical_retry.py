"""Busy market-data locks retry next turn rather than losing a universe rotation."""
import contextlib
from collections import OrderedDict
import io
import unittest
from unittest.mock import patch
from Section_1_Global_Core import analytical_processor as worker

class AnalyticalRetry(unittest.TestCase):
    def test_busy_scope_retried_then_rotation_continues(self):
        with patch.object(worker,'_cursor',0),patch.object(worker,'_status',OrderedDict()),patch.object(worker.regime_research,'catch_up',side_effect=[TimeoutError('busy'),dict(processed=0,status='waiting')]) as catch,contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(worker.maintenance(['BTC'],['5m'],time_budget=10,max_pairs=1),0)
            self.assertEqual(worker._cursor,0)
            worker.maintenance(['BTC'],['5m'],time_budget=10,max_pairs=1)
            self.assertEqual(worker._cursor,1)
            self.assertEqual([call.kwargs['engine_name'] for call in catch.call_args_list],['REGIME','REGIME'])
            self.assertNotIn('Traceback',output.getvalue())

    def test_repeated_contention_is_not_repeated_log_spam(self):
        from collections import OrderedDict
        with patch.object(worker,'_cursor',0),patch.object(worker,'_status',OrderedDict()),patch.object(worker.regime_research,'catch_up',side_effect=TimeoutError('busy')),contextlib.redirect_stdout(io.StringIO()) as output:
            for _ in range(4):worker.maintenance(['BTC'],['5m'],time_budget=10)
            self.assertEqual(worker._cursor,0)
            self.assertEqual(output.getvalue().count('retry next turn'),1)
