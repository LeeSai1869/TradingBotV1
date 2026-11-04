"""Launch scripts resolve their own checkout and respect its Python selection."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

class PortableLaunchers(unittest.TestCase):
    def test_launch_from_unrelated_cwd_with_spaces(self):
        root=Path(__file__).parents[1]
        paths=('Section_1_Global_Core/memory_storage/Runner/run_live.sh','Section_11_UI_UX/binance_chart/run_chart.sh')
        modules=('Section_1_Global_Core.memory_storage.Runner.live_runner','Section_11_UI_UX.server.ui_server')
        with tempfile.TemporaryDirectory() as temp:
            checkout=Path(temp)/'Moved Project';checkout.mkdir()
            fake=Path(temp)/'python shim';fake.write_text('#!/bin/bash\npwd\nprintf "%s\\n" "$@"\n');fake.chmod(0o700)
            for script,module in zip(paths,modules):
                target=checkout/script;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/script,target)
                result=subprocess.run(['bash',str(target)],cwd=temp,env={**os.environ,'TRADINGBOT_PYTHON':str(fake)},text=True,capture_output=True,check=True)
                self.assertIn(str(checkout),result.stdout.splitlines());self.assertEqual(result.stdout.splitlines()[-1],module)
