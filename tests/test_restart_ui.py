"""Restart helper only targets known UI processes and respects launchd ownership."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import restart_ui


class RestartUITests(unittest.TestCase):
    def test_unrelated_listener_is_not_stopped(self):
        with patch.object(restart_ui.sys,'platform','linux'),patch.object(restart_ui,'listeners',return_value=['123']),patch.object(restart_ui.subprocess,'run',return_value=SimpleNamespace(stdout='python3 -m unrelated.service')),patch.object(restart_ui.os,'kill') as kill:
            with self.assertRaises(SystemExit): restart_ui.main()
            kill.assert_not_called()

    def test_launchd_service_restarts_without_launching_competing_process(self):
        calls=[]
        def run(args,**kwargs):
            calls.append(args)
            if args==['launchctl','list']: return SimpleNamespace(stdout='123 0 com.example.chart\n')
            if args[0]=='ps': return SimpleNamespace(stdout='python3 -m Section_11_UI_UX.server.ui_server')
            return SimpleNamespace(returncode=0)
        with patch.object(restart_ui.sys,'platform','darwin'),patch.object(restart_ui.os,'getuid',return_value=501),patch.object(restart_ui,'listeners',side_effect=[['123'],[]]),patch.object(restart_ui.subprocess,'run',side_effect=run),patch.object(restart_ui,'ready',return_value=True),patch.object(restart_ui.os,'kill') as kill,patch.object(restart_ui.os,'execv') as start:
            restart_ui.main()
            self.assertIn(['launchctl','kickstart','-k','gui/501/com.example.chart'],calls)
            kill.assert_not_called();start.assert_not_called()

    def test_manual_ui_restarts_in_foreground_after_port_is_free(self):
        with patch.object(restart_ui.sys,'platform','linux'),patch.object(restart_ui,'listeners',side_effect=[['123'],[]]),patch.object(restart_ui.subprocess,'run',return_value=SimpleNamespace(stdout='python3 -m Section_11_UI_UX.server.ui_server')),patch.object(restart_ui.time,'monotonic',side_effect=[0,3]),patch.object(restart_ui.os,'kill') as kill,patch.object(restart_ui.os,'execv') as start:
            restart_ui.main()
            kill.assert_called_once_with(123,restart_ui.signal.SIGTERM)
            self.assertEqual(start.call_args.args[1][-1],'Section_11_UI_UX.server.ui_server')

    def test_launchd_wrapper_is_found_via_listener_parent(self):
        calls=[]
        def run(args,**kwargs):
            calls.append(args)
            if args==['launchctl','list']: return SimpleNamespace(stdout='99 0 com.example.chart\n')
            if args[-1]=='ppid=': return SimpleNamespace(stdout='99')
            if args[0]=='ps': return SimpleNamespace(stdout='python3 -m Section_11_UI_UX.server.ui_server')
            return SimpleNamespace(returncode=0)
        with patch.object(restart_ui.sys,'platform','darwin'),patch.object(restart_ui.os,'getuid',return_value=501),patch.object(restart_ui,'listeners',side_effect=[['123'],[]]),patch.object(restart_ui.subprocess,'run',side_effect=run),patch.object(restart_ui,'ready',return_value=True),patch.object(restart_ui.os,'kill') as kill,patch.object(restart_ui.os,'execv') as start:
            restart_ui.main()
            self.assertIn(['launchctl','kickstart','-k','gui/501/com.example.chart'],calls)
            kill.assert_not_called();start.assert_not_called()
