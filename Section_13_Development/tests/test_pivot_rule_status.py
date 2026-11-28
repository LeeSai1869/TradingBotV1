from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('pivot_status',Path(__file__).resolve().parents[1]/'diagnostics/check_pivot_rules.py')
status=importlib.util.module_from_spec(spec);spec.loader.exec_module(status)


class PivotRuleStatus(unittest.TestCase):
    def test_missing_source_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict('os.environ',{},clear=True):
            with self.assertRaises(ValueError):status.status(directory,'ENAUSDT','15m')
            self.assertEqual(list(Path(directory).iterdir()),[])
    def test_readonly_status_and_pending_repair(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict('os.environ',{'TRADINGBOT_DATA_DIR':directory}):
            folder=Path(directory)/'storage';folder.mkdir();path=folder/'features.db'
            with sqlite3.connect(path) as c:
                c.execute('CREATE TABLE features(symbol,interval,open_time,pivot_rules_version,pivot_reference_range)')
                c.execute("INSERT INTO features VALUES ('ENAUSDT','15m',1,'current-move-v2',10000)")
                c.execute('CREATE TABLE feature_replay_jobs(symbol,interval,last_time,target,columns)')
            before=path.read_bytes();self.assertEqual(status.status(directory,'ENAUSDT','15m')['status'],'UPDATED');self.assertEqual(before,path.read_bytes())
            with sqlite3.connect(path) as c:c.execute("INSERT INTO feature_replay_jobs VALUES ('ENAUSDT','15m',0,1,'[\"pivot_reference_range\"]')")
            before=path.read_bytes();self.assertEqual(status.status(directory,'ENAUSDT','15m')['status'],'REPAIR_PENDING');self.assertEqual(before,path.read_bytes())
