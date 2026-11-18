"""Atomic omission, legacy preservation and resumable verified cleanup."""
import json
import unittest
from unittest.mock import patch
from test_ema_distance_reads import EMADistanceReads,live
from Section_1_Global_Core.memory_storage.Storage import features_store as s
from Section_1_Global_Core.memory_storage.Storage import ema_distance_retirement as policy
import retire_ema_distance_storage as job


class Retirement(EMADistanceReads):
    def raw(self,stamp):
        return tuple(self.conn.execute('SELECT '+','.join(policy.FIELDS)+
            ' FROM features WHERE open_time=?',(stamp,)).fetchone())

    def ready(self):
        for stamp in (100,101,102):
            s.insert_rows(self.conn,[dict(symbol='BTCUSDT',interval='1m',open_time=stamp,
                formula_version=3,**self.row(),**live(self.row()))])

    def test_writer_omits_only_version_three_and_preserves_formula_reads(self):
        for version in (1,2,3):
            outputs=live(self.row()) if version==3 else dict.fromkeys(policy.FIELDS,777.)
            s.insert_rows(self.conn,[dict(symbol='BTCUSDT',interval='1m',open_time=version,
                formula_version=version,**self.row(),**outputs)])
            self.assertEqual(self.raw(version),(None,)*10 if version==3 else (777.,)*10)
            self.assertEqual(self.projected(version),outputs)

    def test_writer_mismatch_rolls_back_entire_insert(self):
        with self.assertRaisesRegex(ValueError,'formula mismatch'):
            s.insert_rows(self.conn,[dict(symbol='BTCUSDT',interval='1m',open_time=0,
                formula_version=3,**self.row(),**dict.fromkeys(policy.FIELDS,999.))])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM features').fetchone()[0],0)

    def test_dry_run_and_legacy_preservation(self):
        self.insert(self.row());self.insert(self.row(),1,1,dict.fromkeys(policy.FIELDS,777.))
        rows=self.conn.execute('SELECT '+policy.projection()+' FROM features f').fetchall()
        report=policy.clear_rows(self.conn,rows,apply=False)
        self.assertEqual(report['values_cleared'],10)
        self.assertEqual(report['values_retained'],10)
        self.assertNotEqual(self.raw(0),(None,)*10)
        with self.conn:
            self.conn.execute('BEGIN IMMEDIATE')
            policy.clear_rows(self.conn,rows,apply=True)
        self.assertEqual(self.raw(0),(None,)*10)
        self.assertEqual(self.raw(1),(777.,)*10)

    def test_resume_and_checkpoint_failure_are_atomic(self):
        self.insert(self.row(),0);self.insert(self.row(),1);self.ready()
        state=job.start(self.conn)
        self.assertFalse(state['complete'])
        with self.conn:
            self.conn.execute("CREATE TRIGGER reject_progress BEFORE UPDATE ON feature_storage_retirements BEGIN SELECT RAISE(ABORT,'checkpoint failure'); END")
        with self.assertRaisesRegex(Exception,'checkpoint failure'):job.advance(self.conn,1)
        self.assertEqual(job.load_state(self.conn)['last_rowid'],0)
        self.assertNotEqual(self.raw(0),(None,)*10)
        with self.conn:self.conn.execute('DROP TRIGGER reject_progress')
        while not state['complete']:state=job.advance(self.conn,1)
        self.assertEqual(state['values_cleared'],20)
        self.assertEqual(self.raw(0),(None,)*10)
        self.assertEqual(job.start(self.conn),state)

    def test_source_guard_and_readiness(self):
        self.insert(self.row())
        with self.assertRaises(job.WriterNotReady):job.start(self.conn)
        self.ready();job.start(self.conn)
        with patch.object(job,'sources',return_value={}):
            with self.assertRaisesRegex(RuntimeError,'Source database changed'):job.advance(self.conn)
        self.assertNotEqual(self.raw(0),(None,)*10)

    def test_cli_dry_run_status_and_post_cleanup_reader(self):
        from contextlib import redirect_stdout
        import io
        import check_ema_distance_readers as check
        self.insert(self.row(),0)
        output=io.StringIO()
        with patch('sys.argv',['retire_ema_distance_storage.py']),redirect_stdout(output):job.main()
        self.assertIn('"would_clear_values": 10',output.getvalue())
        self.assertNotEqual(self.raw(0),(None,)*10)
        self.ready();state=job.start(self.conn)
        with self.conn:
            self.conn.execute('INSERT INTO feature_storage_retirements VALUES (?,?)',('atr_slopes_v1','{}'))
        while not state['complete']:state=job.advance(self.conn)
        self.assertEqual(self.conn.execute("SELECT state FROM feature_storage_retirements WHERE name='atr_slopes_v1'").fetchone()[0],'{}')
        output=io.StringIO()
        with patch('sys.argv',['retire_ema_distance_storage.py','--status']),redirect_stdout(output):job.main()
        self.assertTrue(json.loads(output.getvalue())['sources_match'])
        output=io.StringIO()
        with patch('sys.argv',['check_ema_distance_readers.py']),redirect_stdout(output):check.main()
        report=json.loads(next(line[7:] for line in output.getvalue().splitlines() if line.startswith('FINAL: ')))
        self.assertEqual(report['omitted_values_reconstructed'],40)
        self.assertEqual(report['stored_formula_mismatches'],0)

    def test_batch_mismatch_never_clears_earlier_valid_row(self):
        self.insert(self.row(),0);self.insert(self.row(),1,outputs=dict.fromkeys(policy.FIELDS,999.));self.ready()
        job.start(self.conn)
        with self.assertRaisesRegex(ValueError,'formula mismatch'):job.advance(self.conn)
        self.assertNotEqual(self.raw(0),(None,)*10)
        self.assertEqual(job.load_state(self.conn)['last_rowid'],0)


if __name__=='__main__':unittest.main()
