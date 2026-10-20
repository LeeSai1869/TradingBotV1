"""Ingest audits must stay bounded and cannot run full-history repair inline."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core.memory_storage.Audit import audit_runner as audit
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader


class FastAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);stack=ExitStack();self.addCleanup(stack.close)
        for name,path in [('KLINES_DB',root/'klines.db'),('METADATA_DB',root/'metadata.db'),('LOG_DIR',root/'logs')]:
            stack.enter_context(patch.object(audit.cfg,name,path))
        stack.enter_context(patch.object(downloader,'DB_PATH',root/'klines.db'))
        stack.enter_context(patch.object(audit.data_policy,'active_symbols',return_value=['ETHUSDT']))
        stack.enter_context(patch.object(audit.data_policy,'active_intervals',return_value=['1m']))
        conn=downloader.open_db()
        conn.executemany('INSERT INTO klines VALUES(?,?,?,?,?,?,?,?,?)',
                         [('ETHUSDT','1m',60000*i,10,12,9,11,5,60000*(i+1)-1) for i in range(2000)])
        conn.commit();conn.close()

    def test_recent_audit_avoids_full_hash_scan_consistency_and_network(self):
        with patch.object(audit,'_file_sha256',side_effect=AssertionError('full hash')),patch.object(audit,'_active_pairs',side_effect=AssertionError('full scan')),patch.object(audit.audit_continuity,'run',side_effect=AssertionError('full repair')),patch.object(audit.audit_consistency,'run',side_effect=AssertionError('full consistency')):
            result=audit.run_fast(sample_rows_per_pair=10)
        self.assertEqual(result['A1']['checked'],10)
        self.assertEqual(result['A2'],[])
        self.assertEqual(result['summary']['source_verification'],'not-run')
        self.assertIsNone(result['summary']['consistency_pass'])
        self.assertEqual(result['summary']['stale_count'],1)
        self.assertTrue(list(audit.cfg.LOG_DIR.glob('*_fast.json')))

    def test_recent_gap_is_reported_without_network_repair(self):
        import sqlite3
        with sqlite3.connect(audit.cfg.KLINES_DB) as conn:conn.execute('DELETE FROM klines WHERE open_time=?',(1995*60000,))
        with patch.object(audit.audit_continuity,'_refetch_range',side_effect=AssertionError('network repair')):
            result=audit.run_fast(sample_rows_per_pair=10)
        self.assertEqual(result['A2'][0]['gap_count'],1)
        self.assertTrue(result['A2'][0]['repair_deferred'])
        self.assertFalse(result['pass'])
