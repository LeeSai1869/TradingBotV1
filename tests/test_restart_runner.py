import subprocess
import unittest
from unittest.mock import patch
import signal
import restart_runner as runner


class RestartRunnerTests(unittest.TestCase):
    def test_stops_only_verified_project_runner_and_disables_old_supervisor(self):
        commands=[]
        def run(command,**kwargs):
            commands.append(command)
            stdout='n'+str(runner.ROOT)+'\n' if command[0]=='lsof' else '767 0 com.scalp.liverunner\n'
            return subprocess.CompletedProcess(command,0,stdout=stdout)
        with patch.object(runner,'runner_processes',side_effect=[[767],[767],[]]), patch.object(runner.subprocess,'run',side_effect=run), patch.object(runner.os,'kill') as kill:
            runner.stop_existing('gui/501/com.scalp.liverunner')
        kill.assert_called_once_with(767,signal.SIGTERM)
        self.assertIn(['launchctl','disable','gui/501/com.scalp.liverunner'],commands)
        self.assertIn(['launchctl','bootout','gui/501/com.scalp.liverunner'],commands)

    def test_other_checkout_is_left_running(self):
        with patch.object(runner,'runner_processes',return_value=[767]), patch.object(runner.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout='n/other/project\n')) as run, patch.object(runner.os,'kill') as kill:
            with self.assertRaisesRegex(SystemExit,'another/unknown folder'):
                runner.stop_existing('gui/501/com.scalp.liverunner')
        kill.assert_not_called()
        self.assertFalse(any(call.args[0][0]=='launchctl' for call in run.call_args_list))

    def test_process_match_requires_exact_runner_module(self):
        output='767 python -u -m Section_1_Global_Core.memory_storage.Runner.live_runner\n999 python -c "print(Section_1_Global_Core.memory_storage.Runner.live_runner)"\n'
        with patch.object(runner.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout=output)):
            self.assertEqual(runner.runner_processes(),[767])

    def test_manual_terminal_supervisor_is_not_stopped(self):
        commands=[]
        def run(command,**kwargs):
            commands.append(command)
            stdout='n'+str(runner.ROOT)+'\n' if command[0]=='lsof' else '767 0 application.com.apple.Terminal.123\n'
            return subprocess.CompletedProcess(command,0,stdout=stdout)
        with patch.object(runner,'runner_processes',side_effect=[[767],[767],[]]), patch.object(runner.subprocess,'run',side_effect=run), patch.object(runner.os,'kill'):
            runner.stop_existing('gui/501/com.scalp.liverunner')
        self.assertFalse(any('gui/501/application.com.apple.Terminal.123' in command for command in commands))
