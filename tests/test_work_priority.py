from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from Section_1_Global_Core import work_priority
from Section_1_Global_Core.memory_storage.Storage import klines_store,features_store

class PriorityTests(unittest.TestCase):
    def test_closest_symbol_first_then_next_with_empty_symbols_last(self):
        with TemporaryDirectory() as directory:
            raw=Path(directory)/'k.db';features=Path(directory)/'f.db'
            with sqlite3.connect(raw) as c:
                c.execute('CREATE TABLE klines(symbol TEXT,interval TEXT,open_time INTEGER,PRIMARY KEY(symbol,interval,open_time))')
                c.execute('CREATE TABLE history_progress(symbol TEXT,interval TEXT)')
                c.executemany('INSERT INTO klines VALUES (?,?,?)',[(s,'1m',t) for s in ('FAR','NEAR','MID') for t in (0,600000)])
            with sqlite3.connect(features) as c:
                c.execute('CREATE TABLE feature_engine_state(symbol TEXT,interval TEXT,last_open_time INTEGER)')
                c.executemany('INSERT INTO feature_engine_state VALUES (?,?,?)',[(s,'1m',t) for s,t in [('FAR',0),('MID',300000),('NEAR',540000)]])
            with patch.object(klines_store,'DB_PATH',raw),patch.object(features_store,'DB_PATH',features):
                symbols=['NEW','FAR','MID','NEAR']
                self.assertEqual(work_priority.work_symbol(symbols,['1m']),'NEAR')
                with sqlite3.connect(features) as c:c.execute("UPDATE feature_engine_state SET last_open_time=600000 WHERE symbol='NEAR'")
                self.assertEqual(work_priority.work_symbol(symbols,['1m']),'MID')
                with sqlite3.connect(features) as c:c.execute("UPDATE feature_engine_state SET last_open_time=600000 WHERE symbol='MID'")
                self.assertEqual(work_priority.work_symbol(symbols,['1m']),'FAR')
                with sqlite3.connect(features) as c:c.execute("UPDATE feature_engine_state SET last_open_time=600000 WHERE symbol='FAR'")
                self.assertEqual(work_priority.work_symbol(symbols,['1m']),'NEW')
                self.assertIsNone(work_priority.work_symbol(['FAR','MID','NEAR'],['1m']))
