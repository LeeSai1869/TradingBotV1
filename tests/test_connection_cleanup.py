from contextlib import nullcontext
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core.memory_storage.Storage import db,features_store,adcn_store
from Section_1_Global_Core.memory_storage.Audit import audit_runner
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader

class BrokenInitialization:
    def __init__(self,connection):self.connection=connection
    def executescript(self,*a):raise sqlite3.OperationalError('injected schema failure')
    def execute(self,*a):raise sqlite3.OperationalError('injected schema failure')
    def close(self):self.connection.close()

class ConnectionCleanupTests(unittest.TestCase):
    def test_factories_close_connections_when_schema_setup_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            for owner,fn in [(features_store,features_store.open_db),(adcn_store,adcn_store.open_db),(downloader,downloader.open_db),(audit_runner,audit_runner._open_metadata)]:
                connection=sqlite3.connect(':memory:');broken=BrokenInitialization(connection)
                with patch.object(owner.sqlite3,'connect',return_value=broken):
                    with self.assertRaises(sqlite3.OperationalError):fn()
                # Keep strong references: garbage collection cannot satisfy this.
                with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')

    def test_partial_read_acquisition_closes_previously_opened_handle(self):
        from Section_1_Global_Core import data_policy
        with tempfile.TemporaryDirectory() as folder:
            raw=Path(folder)/'raw.db';features=Path(folder)/'features.db';raw.touch();features.touch()
            for method,args in [(db.read_decision_inputs,('ETHUSDT','1m',0)),(db.read_decision_seed,('ETHUSDT','1m'))]:
                first=sqlite3.connect(':memory:')
                with patch.object(db.klines_store,'DB_PATH',raw),patch.object(db.features_store,'DB_PATH',features),patch.object(data_policy,'snapshot_guard',side_effect=nullcontext),patch.object(db,'_read_connection',side_effect=[first,sqlite3.OperationalError('open failed')]):
                    with self.assertRaises(sqlite3.OperationalError):method(*args)
                with self.assertRaises(sqlite3.ProgrammingError):first.execute('SELECT 1')

    def test_third_store_open_failure_closes_both_previous_stores(self):
        first=sqlite3.connect(':memory:');second=sqlite3.connect(':memory:')
        with patch.object(db.klines_store,'open_db',return_value=first),patch.object(db.features_store,'open_db',return_value=second),patch.object(db.adcn_store,'open_db',side_effect=sqlite3.OperationalError('open failed')):
            with self.assertRaises(sqlite3.OperationalError):db.read_state_range('ETHUSDT','1m',0,60000)
        for c in (first,second):
            with self.assertRaises(sqlite3.ProgrammingError):c.execute('SELECT 1')
