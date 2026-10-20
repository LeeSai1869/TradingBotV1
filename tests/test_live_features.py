import unittest
from unittest.mock import patch
from dataclasses import asdict
import pandas as pd
from Section_11_UI_UX.server.live_features import calculate
from Section_4_Features.features import ema, rsi
from restart_runner import configuration, ROOT
from pathlib import Path


class LiveFeaturesTests(unittest.TestCase):
    def setUp(self):
        self.rows = [('ETHUSDT','1m',i*60000,100,110,90,100+i%13,5,(i+1)*60000-1) for i in range(499)]
        self.client = dict(symbol='ETHUSDT',interval='1m',open_time=499*60000,
                           open=100,high=120,low=90,close=112,volume=8,close_time=500*60000-1)

    def test_tick_replaces_last_close_and_matches_permanent_formula(self):
        with patch('Section_11_UI_UX.server.live_features.db.read_klines_tail',return_value=self.rows) as read:
            first=calculate('ETHUSDT','1m',self.client)
            self.client['close']=117
            second=calculate('ETHUSDT','1m',self.client)
            again=calculate('ETHUSDT','1m',self.client)
        read.assert_called_with('ETHUSDT','1m',499*60000,499)
        frame=pd.DataFrame({'close':[r[6] for r in self.rows]+[117]})
        expected={**asdict(ema.compute(frame)),**asdict(rsi.compute(frame))}
        self.assertEqual(second,expected)
        self.assertEqual(second,again)
        self.assertNotEqual(first['ema50'],second['ema50'])
        self.assertNotEqual(first['rsi'],second['rsi'])
        self.assertEqual(len(self.rows),499)

    def test_missing_or_gapped_history_waits(self):
        for rows in ([], self.rows[:-1], self.rows[:100]+self.rows[101:]):
            with patch('Section_11_UI_UX.server.live_features.db.read_klines_tail',return_value=rows):
                self.assertIsNone(calculate('ETHUSDT','1m',self.client))

    def test_launchd_uses_checkout_and_selected_interpreter(self):
        config=configuration(Path('/custom/python'),Path('/tmp/logs'))
        self.assertEqual(config['WorkingDirectory'],str(ROOT))
        self.assertEqual(config['ProgramArguments'][0],'/custom/python')
        self.assertTrue(config['RunAtLoad']); self.assertTrue(config['KeepAlive'])

    def test_installer_enables_missing_login_service(self):
        import tempfile
        import subprocess
        import plistlib
        import restart_runner
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(restart_runner.sys, 'platform', 'darwin'), patch.object(Path, 'home', return_value=Path(directory)), patch.object(restart_runner.time, 'sleep'), patch.object(restart_runner.subprocess, 'run', return_value=subprocess.CompletedProcess([],0,stdout='')) as run:
                restart_runner.main()
                commands=[call.args[0] for call in run.call_args_list]
            self.assertTrue(any(command[:2]==['launchctl','enable'] for command in commands))
            self.assertTrue(any(command[:2]==['launchctl','bootstrap'] for command in commands))
            config=plistlib.loads((Path(directory)/'Library/LaunchAgents/com.scalp.liverunner.plist').read_bytes())
            self.assertTrue(config['RunAtLoad'])
