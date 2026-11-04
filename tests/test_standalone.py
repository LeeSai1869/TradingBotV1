"""Portable profiles are isolated, relocatable, locked and preserve existing memory."""
from pathlib import Path
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import portable_app as app

ROOT=Path(__file__).parents[1]

class StandaloneTests(unittest.TestCase):
    def test_profiles_do_not_overwrite_user_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            profile=app.initialize(Path(temp)/'Profile with spaces')
            target=profile/'config/runtime_policy.json';target.write_text('{"custom":"preserved"}')
            app.initialize(profile)
            self.assertEqual(json.loads(target.read_text()),dict(custom='preserved'))
            self.assertFalse((profile/'storage/klines.db').exists())

    def test_profile_smoke_and_relocation_in_fresh_processes(self):
        with tempfile.TemporaryDirectory() as temp:
            first=Path(temp)/'Original';moved=Path(temp)/'Moved memory'
            for profile in (first,moved):
                if first.exists() and not moved.exists() and profile==moved:first.rename(moved)
                result=subprocess.run([sys.executable,str(ROOT/'portable_app.py'),'--data-dir',str(profile),'--self-test'],capture_output=True,text=True,check=True)
                self.assertEqual(json.loads(result.stdout)['status'],'PASS')
            self.assertFalse(first.exists())

    def test_legacy_import_includes_wal_and_refuses_active_profile_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source';storage=source/'Section_1_Global_Core/memory_storage/Storage';storage.mkdir(parents=True)
            db=sqlite3.connect(storage/'klines.db');self.addCleanup(db.close)
            db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE test(value)');db.execute('INSERT INTO test VALUES (42)');db.commit()
            target=Path(temp)/'target';app.import_legacy(source,target)
            copy=sqlite3.connect(target/'storage/klines.db')
            try:self.assertEqual(copy.execute('SELECT value FROM test').fetchone()[0],42)
            finally:copy.close()
            app.initialize(target)
            with self.assertRaises(ValueError):app.import_legacy(source,target)

    def test_duplicate_profile_instance_is_rejected(self):
        from Section_1_Global_Core import data_policy
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'locks').mkdir()
            with data_policy._file_lock(root/'locks/application.lock',data_policy.fcntl.LOCK_EX,0):
                result=subprocess.run([sys.executable,str(ROOT/'portable_app.py'),'--data-dir',str(root),'--self-test'],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0);self.assertIn('busy',result.stderr.lower())

    def test_import_requires_explicit_stopped_source(self):
        with tempfile.TemporaryDirectory() as temp:
            result=subprocess.run([sys.executable,str(ROOT/'portable_app.py'),'--data-dir',str(Path(temp)/'data'),'--import-legacy',temp,'--self-test'],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('source-stopped',result.stderr)

    def test_mismatched_formula_memory_is_rejected_without_writing(self):
        from unittest.mock import patch
        from Section_1_Global_Core import data_policy
        from Section_4_Features.execution.components import current_signature
        with tempfile.TemporaryDirectory() as temp:
            profile=app.initialize(temp);path=profile/'storage/features.db'
            conn=sqlite3.connect(path)
            conn.executescript("CREATE TABLE features(value); INSERT INTO features VALUES (1); CREATE TABLE feature_calculation_versions(symbol,interval,signature); CREATE TABLE feature_replay_jobs(symbol,interval,signature); CREATE TABLE feature_engine_state(symbol,interval); INSERT INTO feature_engine_state VALUES ('BTCUSDT','5m');")
            conn.execute('INSERT INTO feature_calculation_versions VALUES (?,?,?)',('BTCUSDT','5m','wrong'));conn.commit()
            with patch.object(data_policy,'enabled',return_value=True):
                with self.assertRaisesRegex(ValueError,'formula mismatch'):app.check_compatibility(profile)
                self.assertEqual(conn.execute('SELECT signature FROM feature_calculation_versions').fetchone()[0],'wrong')
                conn.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?)',('BTCUSDT','5m',current_signature()));conn.commit()
                app.check_compatibility(profile) # Existing explicit matching replay resumes.
            conn.close()

    def test_explicit_account_import_excludes_sessions_and_push_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'private';source.mkdir();target=Path(temp)/'memory'
            (source/'users.json').write_text('{"test":"account"}')
            (source/'mobile_push.json').write_text('{"private":"do not transfer"}')
            with sqlite3.connect(source/'alerts.sqlite3') as conn:conn.execute('CREATE TABLE events(value)')
            app.import_accounts(source,target)
            self.assertTrue((target/'accounts/users.json').exists());self.assertTrue((target/'accounts/alerts.sqlite3').exists())
            self.assertFalse((target/'accounts/mobile_push.json').exists())
            with self.assertRaises(ValueError):app.import_accounts(source,target)
