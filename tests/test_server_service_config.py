import unittest
from pathlib import Path
import server_service_config as services

class ServerConfiguration(unittest.TestCase):
    def test_system_jobs_use_normal_user_and_home_without_gui_session_requirements(self):
        for label,module in services.SERVICES.items():
            config=services.configuration(label,module,username='trader',home='/Users/trader',python=Path('/opt/python3'))
            self.assertEqual(config['UserName'],'trader')
            self.assertEqual(config['EnvironmentVariables']['HOME'],'/Users/trader')
            self.assertTrue(config['RunAtLoad']);self.assertTrue(config['KeepAlive'])
            self.assertEqual(config['ProgramArguments'][-1],module)
            self.assertNotIn('LimitLoadToSessionType',config)
