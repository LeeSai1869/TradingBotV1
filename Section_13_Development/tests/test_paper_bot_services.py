"""LaunchAgent definitions and lifecycle, without invoking real macOS services."""
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from Section_15_Execution_Bot.services import definitions,manage,LABELS,worker_lock


class PaperServices(unittest.TestCase):
    def setUp(self):
        self.home=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root=self.home/'App With Spaces';self.ledger=self.home/'paper.sqlite3'
        self.python=self.root/'.venv-build/bin/python3'
    def call(self,action):return manage(action,self.ledger,home=self.home,root=self.root,python=self.python)
    def test_definitions_use_argument_arrays_same_ledger_and_only_paper_modules(self):
        configs=definitions(self.root,self.python,self.ledger,self.home)
        self.assertEqual([c['Label'] for c in configs],list(LABELS))
        for cfg in configs:
            self.assertTrue(cfg['RunAtLoad']);self.assertTrue(cfg['KeepAlive'])
            self.assertIn(str(self.ledger),cfg['ProgramArguments'])
            self.assertIn('Section_15_Execution_Bot',cfg['ProgramArguments'])
            self.assertNotIn('shell',str(cfg));self.assertNotIn('live_runner',str(cfg))
            self.assertEqual(plistlib.loads(plistlib.dumps(cfg)),cfg)
    def test_one_worker_per_ledger_and_lock_released_after_exit(self):
        with worker_lock(self.ledger):
            with self.assertRaisesRegex(ValueError,'already running'):
                with worker_lock(self.ledger):pass
        with worker_lock(self.ledger):pass
        self.assertFalse(self.ledger.exists())
    @patch('Section_15_Execution_Bot.services.sys.platform','darwin')
    @patch('Section_15_Execution_Bot.services.subprocess.run')
    def test_install_status_reinstall_uninstall_preserve_ledger_and_app(self,run):
        run.return_value=subprocess.CompletedProcess([],0,stdout='',stderr='')
        self.ledger.write_bytes(b'preserve ledger');self.root.mkdir();(self.root/'user-code').write_text('keep')
        self.call('install');self.call('install')
        self.assertEqual(len(self.call('status')),2)
        shortcut=self.home/'Desktop/Paper Bot Dashboard.webloc'
        self.assertEqual(plistlib.loads(shortcut.read_bytes())['URL'],'http://127.0.0.1:8002/')
        self.call('uninstall')
        self.assertEqual(self.ledger.read_bytes(),b'preserve ledger')
        self.assertEqual((self.root/'user-code').read_text(),'keep')
        self.assertFalse(list((self.home/'Library/LaunchAgents').glob('*.plist')))
        self.assertTrue(shortcut.exists())
        for call in run.call_args_list:self.assertNotIn('com.tradingindicator.liverunner',str(call))
    @patch('Section_15_Execution_Bot.services.sys.platform','darwin')
    @patch('Section_15_Execution_Bot.services.subprocess.run')
    def test_foreign_checkout_service_rejected_before_any_mutation(self,run):
        configs=definitions(self.root,self.python,self.ledger,self.home)
        folder=self.home/'Library/LaunchAgents';folder.mkdir(parents=True)
        cfg=configs[1];cfg['WorkingDirectory']='/another/checkout'
        path=folder/(cfg['Label']+'.plist');path.write_bytes(plistlib.dumps(cfg));before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'another checkout'):self.call('install')
        self.assertEqual(path.read_bytes(),before);run.assert_not_called()
    @patch('Section_15_Execution_Bot.services.sys.platform','linux')
    def test_unsupported_platform_does_not_install(self):
        with self.assertRaisesRegex(ValueError,'macOS'):self.call('install')
        self.assertFalse((self.home/'Library').exists())
    @patch('Section_15_Execution_Bot.services.sys.platform','darwin')
    @patch('Section_15_Execution_Bot.services.subprocess.run')
    def test_start_failure_is_visible(self,run):
        run.return_value=subprocess.CompletedProcess([],5,stdout='',stderr='bootstrap failed')
        with self.assertRaisesRegex(ValueError,'Could not start'):self.call('install')
