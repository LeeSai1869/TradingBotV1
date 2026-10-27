"""macOS launchctl lifecycle simulated without touching host services."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
import restart_liquidity as restart


def result(code=0,error=''):return subprocess.CompletedProcess([],code,'',error)


class RestartTests(unittest.TestCase):
    def test_waits_for_job_removal_before_bootstrap(self):
        responses=[result(),result(),result(),result(113),result(),result(),result(),result()]
        with patch.object(restart,'launchctl',side_effect=responses) as call,patch.object(restart.time,'sleep') as sleep:
            restart.restart_service('gui/501',Path('/tmp/job.plist'))
        self.assertEqual(sleep.call_count,2)
        self.assertEqual([c.args[0] for c in call.call_args_list],['bootout','print','print','print','enable','bootstrap','kickstart','print'])

    def test_already_unloaded_job_can_start(self):
        with patch.object(restart,'launchctl',side_effect=[result(113),result(113),result(),result(),result(),result()]):
            restart.restart_service('gui/501',Path('/tmp/job.plist'))

    def test_unload_failure_does_not_bootstrap_over_registered_job(self):
        with patch.object(restart,'launchctl',return_value=result()) as call,patch.object(restart.time,'sleep'):
            with self.assertRaisesRegex(SystemExit,'still registered'):
                restart.restart_service('gui/501',Path('/tmp/job.plist'))
        self.assertNotIn('bootstrap',[c.args[0] for c in call.call_args_list])

    def test_bootstrap_error_preserves_diagnostic_without_starting_old_job(self):
        with patch.object(restart,'launchctl',side_effect=[result(),result(113),result(),result(5,'Input/output error')]) as call:
            with self.assertRaisesRegex(SystemExit,'Input/output error'):
                restart.restart_service('gui/501',Path('/tmp/job.plist'))
        self.assertNotIn('kickstart',[c.args[0] for c in call.call_args_list])
