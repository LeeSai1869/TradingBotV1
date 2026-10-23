"""Scheduler connections must close deterministically, independent of Python GC."""
from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import textwrap
import unittest
from unittest.mock import patch
from Section_1_Global_Core import work_priority
from Section_1_Global_Core.memory_storage.Storage import klines_store,features_store


class SchedulerResources(unittest.TestCase):
    def test_connections_close_on_returns_and_sql_errors_even_when_referenced(self):
        with TemporaryDirectory() as directory:
            raw=Path(directory)/'k.db';features=Path(directory)/'f.db'
            with closing(sqlite3.connect(raw)) as c:
                c.execute('CREATE TABLE klines(symbol,interval,open_time)')
                c.execute("INSERT INTO klines VALUES ('BTCUSDT','1m',100)");c.commit()
            with closing(sqlite3.connect(features)) as c:
                c.execute('CREATE TABLE feature_engine_state(symbol,interval,last_open_time)')
            original=sqlite3.connect;opened=[]
            def track(*args,**kwargs):
                conn=original(*args,**kwargs);opened.append(conn);return conn
            def assert_closed():
                for conn in opened:
                    with self.assertRaises(sqlite3.ProgrammingError):conn.execute('SELECT 1')
            with patch.object(klines_store,'DB_PATH',raw),patch.object(features_store,'DB_PATH',features),patch.object(work_priority.sqlite3,'connect',side_effect=track):
                # Both initial selection and early sticky-owner returns.
                for _ in range(50):self.assertEqual(work_priority.work_symbol(['BTCUSDT'],['1m']),'BTCUSDT')
                assert_closed()
                # SQL errors while checking the raw timeline must close both DBs.
                with closing(original(raw)) as c:c.execute('DROP TABLE klines')
                with self.assertRaises(sqlite3.OperationalError):work_priority.work_symbol(['BTCUSDT'],['1m'])
                assert_closed()
                # Failure opening the inner DB must still close the outer DB.
                with patch.object(features_store,'DB_PATH',Path(directory)):
                    with self.assertRaises(sqlite3.OperationalError):work_priority.work_symbol(['BTCUSDT'],['1m'])
                assert_closed()

    @unittest.skipUnless(sys.platform in ('linux','darwin'),'requires Unix descriptor limits')
    def test_1000_checks_with_gc_disabled_under_64_file_limit(self):
        script=textwrap.dedent('''
            import gc,resource,sqlite3,tempfile
            from contextlib import closing
            from pathlib import Path
            from Section_1_Global_Core import work_priority
            from Section_1_Global_Core.memory_storage.Storage import klines_store,features_store
            with tempfile.TemporaryDirectory() as directory:
                klines_store.DB_PATH=Path(directory)/'k.db'
                features_store.DB_PATH=Path(directory)/'f.db'
                with closing(sqlite3.connect(klines_store.DB_PATH)) as c:
                    c.execute('CREATE TABLE klines(symbol,interval,open_time,PRIMARY KEY(symbol,interval,open_time))')
                    c.execute("INSERT INTO klines VALUES ('BTCUSDT','1m',100)");c.commit()
                with closing(sqlite3.connect(features_store.DB_PATH)) as c:
                    c.execute('CREATE TABLE feature_engine_state(symbol,interval,last_open_time)')
                gc.collect();gc.disable()
                soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
                resource.setrlimit(resource.RLIMIT_NOFILE,(min(64,soft),hard))
                for _ in range(1000):
                    assert work_priority.work_symbol(['BTCUSDT'],['1m'])=='BTCUSDT'
                print('1000 scheduler checks completed under 64-file limit, GC disabled')
        ''')
        result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('1000 scheduler checks completed',result.stdout)
