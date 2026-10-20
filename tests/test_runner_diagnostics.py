import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import check_coin


class RunnerDiagnosticTests(unittest.TestCase):
    def test_report_identifies_a_runner_using_another_checkout(self):
        def run(command,**kwargs):
            output='43189 0 com.scalp.liverunner\n' if command[0]=='launchctl' else 'p43189\nn/another/checkout\n'
            return subprocess.CompletedProcess(command,0,stdout=output)
        with tempfile.TemporaryDirectory() as directory:
            output=io.StringIO()
            with patch.object(check_coin.sys,'argv',['check_coin.py','ETHUSDT']),patch.object(check_coin.sys,'platform','darwin'),patch.object(Path,'home',return_value=Path(directory)),patch.object(check_coin.subprocess,'run',side_effect=run),patch.object(check_coin.klines_store,'DB_PATH',Path(directory)/'klines.db'),patch.object(check_coin.features_store,'DB_PATH',Path(directory)/'features.db'),patch.object(check_coin.data_admin,'catalog',return_value={'approved':[{'symbol':'ETHUSDT'}]}),patch.object(check_coin.data_policy,'active_symbols',return_value=['ETHUSDT']),contextlib.redirect_stdout(output):
                check_coin.main()
            text=output.getvalue()
            self.assertIn('Candle database:',text)
            self.assertIn('Runner working folder: /another/checkout',text)
            self.assertIn('DIFFERENT project folder',text)
