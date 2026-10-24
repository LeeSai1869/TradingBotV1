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

    def test_single_command_reports_paused_policy_pending_replay_and_logs(self):
        import sqlite3
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);raw=root/'klines.db';features=root/'features.db'
            with sqlite3.connect(raw) as conn:
                conn.execute('CREATE TABLE klines(symbol TEXT,interval TEXT,open_time INTEGER,close REAL,close_time INTEGER)')
                conn.executemany('INSERT INTO klines VALUES (?,?,?,?,?)',[('ETHUSDT','1m',i*60000,100,(i+1)*60000-1) for i in range(3)])
            with sqlite3.connect(features) as conn:
                conn.execute('CREATE TABLE features(symbol TEXT,interval TEXT,open_time INTEGER)')
                conn.execute('INSERT INTO features VALUES (?,?,?)',('ETHUSDT','1m',0))
                conn.execute('CREATE TABLE feature_engine_state(symbol TEXT,interval TEXT,last_open_time INTEGER)')
                conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?)',('ETHUSDT','1m',0))
            logs=root/'Library/Logs/TradingBotV1';logs.mkdir(parents=True)
            (logs/'runner.log').write_text('download phase starting\n')
            (logs/'runner-error.log').write_text('specific pair failure\n')
            for obj,key,value in ((check_coin.sys,'argv',['check_coin.py','ETHUSDT','--logs']),
                    (check_coin.sys,'platform','linux'),(Path,'home',lambda:root),
                    (check_coin.klines_store,'DB_PATH',raw),(check_coin.features_store,'DB_PATH',features),
                    (check_coin.data_policy,'INTERVALS',['1m','5m'])):
                stack.enter_context(patch.object(obj,key,value))
            stack.enter_context(patch.object(check_coin.data_admin,'catalog',return_value={'approved':[{'symbol':'ETHUSDT'}]}))
            stack.enter_context(patch.object(check_coin.data_policy,'active_symbols',return_value=['ETHUSDT']))
            stack.enter_context(patch.object(check_coin.data_policy,'enabled',side_effect=lambda symbol,interval:interval=='5m'))
            output=io.StringIO()
            with contextlib.redirect_stdout(output):check_coin.main()
            text=output.getvalue()
            self.assertIn('pending candles: 2 | PAUSED by policy',text)
            self.assertIn('download phase starting',text)
            self.assertIn('specific pair failure',text)

    def test_missing_symbol_checkpoint_is_explicit(self):
        import sqlite3
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);features=root/'features.db'
            with sqlite3.connect(features) as conn:
                conn.execute('CREATE TABLE features(symbol TEXT,interval TEXT,open_time INTEGER)')
                conn.execute('CREATE TABLE feature_engine_state(symbol TEXT,interval TEXT,last_open_time INTEGER)')
            stack.enter_context(patch.object(check_coin.sys,'argv',['check_coin.py','ETHUSDT']))
            stack.enter_context(patch.object(check_coin.sys,'platform','linux'))
            stack.enter_context(patch.object(check_coin.features_store,'DB_PATH',features))
            stack.enter_context(patch.object(check_coin.klines_store,'DB_PATH',root/'klines.db'))
            stack.enter_context(patch.object(check_coin.data_admin,'catalog',return_value={}))
            stack.enter_context(patch.object(check_coin.data_policy,'active_symbols',return_value=['ETHUSDT']))
            stack.enter_context(patch.object(check_coin.data_policy,'enabled',return_value=True))
            output=io.StringIO()
            with contextlib.redirect_stdout(output):check_coin.main()
            self.assertIn('No formula-v3 checkpoint committed for ETHUSDT yet',output.getvalue())
            with sqlite3.connect(features) as conn:conn.execute('DROP TABLE feature_engine_state')
            output=io.StringIO()
            with contextlib.redirect_stdout(output):check_coin.main()
            self.assertIn('No formula-v3 checkpoint table yet',output.getvalue())


class LogFreshnessTests(unittest.TestCase):
    def test_old_stderr_is_not_reported_as_a_current_runner_failure(self):
        import os
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'runner-error.log';path.write_text('old descriptor failure\n');os.utime(path,(10,10))
            output=io.StringIO()
            with contextlib.redirect_stdout(output):check_coin.print_log_tail(path,60,runner_started=20)
            self.assertIn('No stderr updates since this runner started',output.getvalue());self.assertNotIn('old descriptor failure',output.getvalue())
            os.utime(path,(30,30));output=io.StringIO()
            with contextlib.redirect_stdout(output):check_coin.print_log_tail(path,60,runner_started=20)
            self.assertIn('old descriptor failure',output.getvalue())
