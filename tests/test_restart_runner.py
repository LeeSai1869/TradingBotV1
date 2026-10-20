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
        output='767 S python -u -m Section_1_Global_Core.memory_storage.Runner.live_runner\n999 S python -c "print(Section_1_Global_Core.memory_storage.Runner.live_runner)"\n'
        def run(command,**kwargs):
            return subprocess.CompletedProcess(command,0,stdout=output if '-axo' in command else '/custom/python3.14\n')
        with patch.object(runner.subprocess,'run',side_effect=run):
            self.assertEqual(runner.runner_processes(),[767])

    def test_zombie_and_shell_launchers_are_not_treated_as_writers(self):
        module=runner.MODULES[0]
        output=f'43186 S /bin/zsh /some/launcher python -u -m {module}\n43189 Z Python -u -m {module}\n555 S /custom/Python -u -m {module}\n'
        def run(command,**kwargs):
            if '-axo' in command: stdout=output
            else: stdout='/bin/zsh\n' if '43186' in command else '/custom/Python\n'
            return subprocess.CompletedProcess(command,0,stdout=stdout)
        with patch.object(runner.subprocess,'run',side_effect=run):
            self.assertEqual(runner.runner_processes(),[555])

    def test_manual_terminal_supervisor_is_not_stopped(self):
        commands=[]
        def run(command,**kwargs):
            commands.append(command)
            stdout='n'+str(runner.ROOT)+'\n' if command[0]=='lsof' else '767 0 application.com.apple.Terminal.123\n'
            return subprocess.CompletedProcess(command,0,stdout=stdout)
        with patch.object(runner,'runner_processes',side_effect=[[767],[767],[]]), patch.object(runner.subprocess,'run',side_effect=run), patch.object(runner.os,'kill'):
            runner.stop_existing('gui/501/com.scalp.liverunner')
        self.assertFalse(any('gui/501/application.com.apple.Terminal.123' in command for command in commands))

    def test_process_exiting_during_inspection_does_not_abort_restart(self):
        def run(command,**kwargs):
            if '-axo' in command:
                return subprocess.CompletedProcess(command,0,stdout=f'767 S python -m {runner.MODULES[0]}\n')
            return subprocess.CompletedProcess(command,1,stdout='')
        with patch.object(runner.subprocess,'run',side_effect=run):
            self.assertEqual(runner.runner_processes(),[])

    def test_real_remaining_writer_reports_process_identity(self):
        def run(command,**kwargs):
            stdout='n'+str(runner.ROOT)+'\n' if command[0]=='lsof' else '767 1 S Python still running\n' if 'pid=,ppid=,stat=,command=' in command else ''
            return subprocess.CompletedProcess(command,0,stdout=stdout)
        with patch.object(runner,'runner_processes',return_value=[767]),patch.object(runner.subprocess,'run',side_effect=run),patch.object(runner.os,'kill'),patch.object(runner.time,'monotonic',side_effect=[0,21]):
            with self.assertRaisesRegex(SystemExit,'767 1 S Python still running'):
                runner.stop_existing('gui/501/com.scalp.liverunner')
