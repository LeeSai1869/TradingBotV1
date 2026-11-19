from contextlib import redirect_stdout
import io
from pathlib import Path
import sqlite3
import subprocess
import unittest
from unittest.mock import patch
import test_feature_compaction as fixtures
import Section_14_Operations.storage.remove_compaction_backup as cleanup


class BackupCleanup(unittest.TestCase):
    setUp=fixtures.Compaction.setUp
    run_job=fixtures.Compaction.run_job

    def fresh(self):
        self.state=self.run_job();self.backup=Path(self.state['backup'])
        with sqlite3.connect(self.path) as c:
            c.execute("INSERT INTO features(symbol,interval,open_time,formula_version,value) VALUES ('ETHUSDT','5m',999,3,123)")

    def test_no_new_writes_keeps_backup(self):
        state=self.run_job()
        with self.assertRaisesRegex(RuntimeError,'writer output'):cleanup.remove_backup(self.path,apply=True)
        self.assertTrue(Path(state['backup']).exists())

    def test_dry_run_and_delete_preserve_active_data_and_report(self):
        self.fresh();before=self.path.read_bytes();report=Path(str(self.path)+'.compaction.json').read_bytes()
        with redirect_stdout(io.StringIO()):cleanup.remove_backup(self.path)
        self.assertTrue(self.backup.exists())
        with redirect_stdout(io.StringIO()):cleanup.remove_backup(self.path,apply=True)
        self.assertFalse(self.backup.exists());self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(Path(str(self.path)+'.compaction.json').read_bytes(),report)
        with redirect_stdout(io.StringIO()):cleanup.remove_backup(self.path,apply=True)

    def test_unexpected_backup_and_symlink_never_deleted(self):
        self.fresh();saved=self.root/'original-saved.db';self.backup.rename(saved)
        self.backup.write_bytes(b'unrelated file')
        with self.assertRaisesRegex(RuntimeError,'differs'):cleanup.remove_backup(self.path,apply=True)
        self.assertEqual(self.backup.read_bytes(),b'unrelated file')
        self.backup.unlink();self.backup.symlink_to(self.path)
        with self.assertRaisesRegex(RuntimeError,'Unexpected backup path'):cleanup.remove_backup(self.path,apply=True)
        self.assertTrue(self.path.exists());self.assertTrue(saved.exists())

    def test_reader_failure_prevents_cleanup(self):
        with patch('sys.argv',['Section_14_Operations/storage/remove_compaction_backup.py','--apply']), \
             patch.object(cleanup.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'check')), \
             patch.object(cleanup,'remove_backup') as remove,self.assertRaises(SystemExit) as result:
            cleanup.main()
        self.assertEqual(result.exception.code,1);remove.assert_not_called()
