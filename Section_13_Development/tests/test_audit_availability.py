from contextlib import ExitStack,nullcontext
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core import work_priority
from Section_1_Global_Core.memory_storage.Storage import features_store,klines_store
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader,update_klines as updater
from Section_1_Global_Core.memory_storage.Audit import audit_runner as audit,audit_freshness

class AuditAvailabilityTests(unittest.TestCase):
    def setUp(self):
        from datetime import datetime,timezone
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);stack=ExitStack();self.addCleanup(stack.close)
        for mod,key,value in [(updater,'DB_PATH',self.root/'klines.db'),(downloader,'DB_PATH',self.root/'klines.db'),(klines_store,'DB_PATH',self.root/'klines.db'),(features_store,'DB_PATH',self.root/'features.db'),(audit.cfg,'KLINES_DB',self.root/'klines.db'),(audit.cfg,'LOG_DIR',self.root/'logs'),(audit.cfg,'METADATA_DB',self.root/'metadata.db')]:stack.enter_context(patch.object(mod,key,value))
        self.now=int(datetime(2026,10,26,tzinfo=timezone.utc).timestamp()*1000)
        self.open=int(datetime(2026,10,1,tzinfo=timezone.utc).timestamp()*1000)
        self.close=int(datetime(2026,11,1,tzinfo=timezone.utc).timestamp()*1000)-1
        self.row=[self.open,'10','12','9','11','5',self.close]
        self.clock=[self.now];stack.enter_context(patch.object(updater.time,'time',side_effect=lambda:self.clock[0]/1000))
        stack.enter_context(patch.object(updater.data_policy,'read',return_value={'epochs':{}}));stack.enter_context(patch.object(updater.data_policy,'enabled',return_value=True))
        stack.enter_context(patch.object(updater.data_policy,'locked',side_effect=nullcontext))
        stack.enter_context(patch.object(audit.data_policy,'active_symbols',return_value=['NEWUSDT']));stack.enter_context(patch.object(audit.data_policy,'active_intervals',return_value=['1M']))
        updater._LAST_UPDATE_MS.clear();updater._LATEST_UPDATE_MS.clear();self.conn=downloader.open_db();self.addCleanup(self.conn.close)

    def test_forming_only_source_waits_without_repeated_requests_or_fake_candles(self):
        with patch.object(updater,'_fetch',return_value=[self.row]) as fetch:
            updater.update_one('NEWUSDT','1M',self.conn)
            calls=fetch.call_count
            updater.update_one('NEWUSDT','1M',self.conn)
            self.assertEqual(fetch.call_count,calls)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM klines').fetchone()[0],0)
        self.assertIsNone(work_priority.work_symbol(['NEWUSDT'],['1M']))
        self.assertIsNone(work_priority.service_pair(['OWNER','NEWUSDT'],['1M'],'OWNER','features'))
        result=audit.run_fast(persist=False)
        self.assertEqual(result['summary']['missing_count'],0)
        self.assertEqual(result['summary']['awaiting_first_close'][0]['symbol'],'NEWUSDT')
        self.assertFalse(audit.cfg.LOG_DIR.exists());self.assertFalse(audit.cfg.METADATA_DB.exists())
        # Expiry is strict: after the first source close, data is required.
        self.clock[0]=self.close+2
        self.assertEqual(audit_freshness.run([('NEWUSDT','1M')])['missing'],1)
        with patch.object(updater,'_fetch',return_value=[self.row]):updater.update_one('NEWUSDT','1M',self.conn)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM klines').fetchone()[0],1)
        self.assertEqual(klines_store.first_close_waits(self.conn),{})
        self.assertEqual(audit_freshness.run([('NEWUSDT','1M')])['fresh'],1)

    def test_empty_response_remains_missing_and_identifies_pair(self):
        with patch.object(updater,'_fetch',return_value=[]):updater.update_one('NEWUSDT','1M',self.conn)
        result=audit.run_fast(persist=False)
        self.assertFalse(result['summary']['freshness_pass'])
        self.assertEqual(result['summary']['missing_pairs'],[{'symbol':'NEWUSDT','interval':'1M','reason':'no stored closed candles'}])
        self.assertEqual(result['summary']['awaiting_first_close'],[])
        self.assertEqual(result['summary']['history_backfill_pairs'],1)

    def test_freshness_uses_and_closes_one_read_connection(self):
        original=sqlite3.connect;opened=[]
        def connect(*args,**kwargs):
            c=original(*args,**kwargs);opened.append(c);return c
        with patch.object(audit_freshness.sqlite3,'connect',side_effect=connect):audit_freshness.run([('NEWUSDT','1M'),('NEWUSDT','1d')])
        self.assertEqual(len(opened),1)
        with self.assertRaises(sqlite3.ProgrammingError):opened[0].execute('SELECT 1')
