"""Actual OS locks must permit nested runner commits and exclude other writers."""
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from Section_1_Global_Core import data_policy


class PolicyLockTests(unittest.TestCase):
    def test_nested_orchestrator_and_processor_lock_finishes_in_subprocess(self):
        code='''
from pathlib import Path
from tempfile import TemporaryDirectory
from Section_1_Global_Core import data_policy
with TemporaryDirectory() as directory:
    data_policy.LOCK_FILE=Path(directory)/'writer.lock'
    with data_policy.locked():
        with data_policy.locked():
            print('NESTED_COMMIT_READY',flush=True)
'''
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=5,check=True)
        self.assertIn('NESTED_COMMIT_READY',result.stdout)

    def test_real_event_pass_can_commit_after_bounded_feature_maintenance(self):
        code="""
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import ExitStack
from unittest.mock import patch
from Section_1_Global_Core import data_policy,orchestrator
from Section_1_Global_Core.memory_storage.Storage import db,klines_store,features_store
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader
from Section_4_Features import processor
with TemporaryDirectory() as directory,ExitStack() as stack:
    root=Path(directory)
    for module,attribute,value in [(data_policy,'LOCK_FILE',root/'policy.lock'),(data_policy,'POLICY_FILE',root/'policy.json'),(orchestrator,'STATE_FILE',root/'state.json'),(klines_store,'DB_PATH',root/'klines.db'),(features_store,'DB_PATH',root/'features.db'),(downloader,'DB_PATH',root/'klines.db')]:
        stack.enter_context(patch.object(module,attribute,value))
    stack.enter_context(patch.object(data_policy,'enabled',return_value=True))
    stack.enter_context(patch.object(data_policy,'active_symbols',return_value=['BTCUSDT']))
    stack.enter_context(patch.object(data_policy,'active_intervals',return_value=['5m']))
    stack.enter_context(patch.object(orchestrator,'update_klines_all',return_value=0))
    downloader.open_db().close()
    db.write_klines([dict(symbol='BTCUSDT',interval='5m',open_time=i*300000,close_time=(i+1)*300000-1,open=100.,high=102.,low=98.,close=100.+i%2,volume=5.) for i in range(205)])
    runner=orchestrator.GlobalCoreOrchestrator()
    runner._processors=[('Section_4_Features.processor.process_bar',processor.process_bar)]
    runner._state={'BTCUSDT|5m':199*300000}
    runner.event_time_budget=10
    for _ in range(3):runner.cycle()
    assert db.count_features('BTCUSDT','5m')==205
    assert runner._state['BTCUSDT|5m']==204*300000
    print('EVENT_COMMIT_COMPLETE',flush=True)
"""
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=15,check=True)
        self.assertIn('EVENT_COMMIT_COMPLETE',result.stdout)

    def test_other_process_cannot_write_until_outermost_scope_exits(self):
        code='''
import sys
from pathlib import Path
from Section_1_Global_Core import data_policy
data_policy.LOCK_FILE=Path(sys.argv[1])
try:
    with data_policy.locked(timeout=.1):print('ACQUIRED')
except TimeoutError:print('EXCLUDED')
'''
        with tempfile.TemporaryDirectory() as directory,patch.object(data_policy,'LOCK_FILE',Path(directory)/'writer.lock'):
            def attempt():
                return subprocess.run([sys.executable,'-c',code,str(data_policy.LOCK_FILE)],capture_output=True,text=True,timeout=5,check=True).stdout.strip()
            with data_policy.locked():
                with data_policy.locked():self.assertEqual(attempt(),'EXCLUDED')
                self.assertEqual(attempt(),'EXCLUDED')
            self.assertEqual(attempt(),'ACQUIRED')

    def test_other_thread_respects_timeout_and_exception_releases_lock(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(data_policy,'LOCK_FILE',Path(directory)/'writer.lock'):
            result=[]
            def attempt():
                try:
                    with data_policy.locked(timeout=.03):result.append('ACQUIRED')
                except TimeoutError:result.append('EXCLUDED')
            with self.assertRaises(ValueError):
                with data_policy.locked():
                    with data_policy.locked():
                        thread=threading.Thread(target=attempt);thread.start();thread.join(timeout=1)
                        self.assertFalse(thread.is_alive());self.assertEqual(result,['EXCLUDED'])
                        raise ValueError('release both scopes')
            thread=threading.Thread(target=attempt);thread.start();thread.join(timeout=1)
            self.assertFalse(thread.is_alive());self.assertEqual(result,['EXCLUDED','ACQUIRED'])
