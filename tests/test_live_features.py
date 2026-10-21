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
        import tempfile
        from Section_1_Global_Core.memory_storage.Storage import features_store
        from Section_4_Features.individual.engine import Engine
        from Section_4_Features.individual.checkpoint import dump
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'features.db'
        self.patch=patch.object(features_store,'DB_PATH',self.path);self.patch.start();self.addCleanup(self.patch.stop)
        self.epochs=patch('Section_4_Features.processor._epoch',return_value=(0,0));self.epochs.start();self.addCleanup(self.epochs.stop)
        self.engine=Engine('ETHUSDT','1m')
        for i in range(60):
            self.engine.step(dict(symbol='ETHUSDT',interval='1m',open_time=i*60000,close_time=(i+1)*60000-1,open=100,high=120,low=90,close=100+i%13,volume=5))
        self.client=dict(symbol='ETHUSDT',interval='1m',open_time=60*60000,close_time=61*60000-1,open=100,high=120,low=90,close=112,volume=8)
        self.saved=dump(self.engine,(0,0))
        conn=features_store.open_db()
        conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('ETHUSDT','1m',59*60000,self.saved));conn.commit();conn.close()

    def test_tick_uses_full_closed_state_without_mutation_or_writes(self):
        import copy
        from Section_1_Global_Core.memory_storage.Storage import features_store
        first=calculate('ETHUSDT','1m',self.client)
        self.client['close']=117
        second=calculate('ETHUSDT','1m',self.client)
        self.assertEqual(second,copy.deepcopy(self.engine).step(self.client,is_confirmed=False,is_realtime=True))
        self.assertEqual(second,calculate('ETHUSDT','1m',self.client))
        self.assertNotEqual(first['ema50'],second['ema50']);self.assertNotEqual(first['rsi'],second['rsi'])
        conn=features_store.open_db()
        self.assertEqual(conn.execute('SELECT state FROM feature_engine_state').fetchone()[0],self.saved)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM features').fetchone()[0],0);conn.close()

    def test_missing_checkpoint_or_nonadjacent_candle_waits(self):
        self.assertIsNone(calculate('BTCUSDT','1m',self.client))
        for delta in (-60000,60000):
            self.assertIsNone(calculate('ETHUSDT','1m',{**self.client,'open_time':self.client['open_time']+delta}))

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
            config=plistlib.loads((Path(directory)/'Library/LaunchAgents/com.tradingindicator.liverunner.plist').read_bytes())
            self.assertTrue(config['RunAtLoad'])
