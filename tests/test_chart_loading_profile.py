"""Real disposable stores: profiling preserves data and honors inactive frames."""
from contextlib import redirect_stdout
import io
import json
import subprocess
import unittest
from unittest.mock import patch
import test_chart_gateway as fixtures
import profile_chart_loading as tool
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import features_store,db


class ChartLoadingProfile(unittest.TestCase):
    candle=staticmethod(fixtures.ChartGatewayTests.candle)
    setUp=fixtures.ChartGatewayTests.setUp

    def test_complete_page_reports_components_without_modifying_data(self):
        before=features_store.DB_PATH.read_bytes()
        output=io.StringIO()
        with patch.object(data_policy,'enabled',return_value=True),redirect_stdout(output):
            tool.measure('BTCUSDT','1m',2,profile=True)
        reports=[json.loads(line[8:]) for line in output.getvalue().splitlines() if line.startswith('RESULT: ')]
        self.assertEqual([r['run'] for r in reports],['first','repeat'])
        self.assertTrue(all(r['rows']==2 and r['payload_MiB']>0 for r in reports))
        self.assertIn('features_store',reports[0]['stages'])
        self.assertIn('adcn_store',reports[0]['stages'])
        self.assertEqual(features_store.DB_PATH.read_bytes(),before)
        self.assertIn('PROFILE: ',output.getvalue())

    def test_inactive_frame_does_not_read_or_activate_data(self):
        with patch.object(data_policy,'enabled',return_value=False), \
             patch.object(db,'read_state_page',side_effect=AssertionError('inactive read')), \
             redirect_stdout(io.StringIO()) as output:
            tool.measure('BTCUSDT','1m',2)
        self.assertEqual(json.loads(output.getvalue())['skipped'],'inactive coin/timeframe')

    def test_parent_bounds_worker_lifetime(self):
        with patch('sys.argv',['profile_chart_loading.py','--timeout','1']), \
             patch.object(tool.subprocess,'run',side_effect=subprocess.TimeoutExpired('worker',1)) as run, \
             redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as result:
            tool.main()
        self.assertEqual(result.exception.code,2)
        self.assertEqual(run.call_args.kwargs['timeout'],1)
