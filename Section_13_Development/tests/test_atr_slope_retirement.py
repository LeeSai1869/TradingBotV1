"""Durable configuration history, transactional writers and resumable clearing."""
from contextlib import closing,redirect_stdout,chdir
import io
import json
import shutil
import sqlite3
import unittest
from unittest.mock import patch

import test_atr_slope_reads as fixtures
import Section_14_Operations.storage.retire_atr_slope_storage as job
from Section_1_Global_Core.memory_storage.Storage import atr_slope_reads as a
from Section_1_Global_Core.memory_storage.Storage import features_store as s,klines_store as k
from Section_4_Features.features import shared_measurements as m


class ATRRetirement(unittest.TestCase):
    setUp=fixtures.ATRSlopeReads.setUp
    seed=fixtures.ATRSlopeReads.seed
    historical=fixtures.ATRSlopeReads.historical

    def next_row(self):
        return dict(self.rows[-1],open_time=900000,close_time=959999,
                    measurement_contiguous_bars=16,ema50=115.,ema200=230.,ema300=345.)

    def raw_values(self,timestamp=840000):
        return tuple(self.features.execute('SELECT '+','.join(a.FIELDS)+
            ' FROM features WHERE open_time=?',(timestamp,)).fetchone())

    def omit_latest(self):
        s.insert_rows(self.features,self.rows[-3:])

    def test_normal_writer_omits_only_verified_values(self):
        row=self.next_row();k.insert_rows(self.raw,[row]);s.insert_rows(self.features,[row])
        self.assertEqual(self.raw_values(900000),(None,)*3)
        got=s.read_row(self.features,'BTCUSDT','1m',900000)
        self.assertEqual(tuple(got[f] for f in a.FIELDS),(2.5,5.,7.5))

    def test_writer_preserves_values_when_retained_history_is_missing(self):
        with self.features:self.features.execute('DELETE FROM features WHERE open_time=720000')
        row=self.next_row();k.insert_rows(self.raw,[row]);s.insert_rows(self.features,[row])
        self.assertEqual(self.raw_values(900000),(2.5,5.,7.5))

    def test_writer_rolls_back_mismatching_row(self):
        row=dict(self.next_row(),ema50_slope_atr=999.)
        k.insert_rows(self.raw,[row])
        with self.assertRaisesRegex(ValueError,'formula mismatch'):
            s.insert_rows(self.features,[row])
        self.assertFalse(s.has_row(self.features,'BTCUSDT','1m',900000))
        self.assertEqual(self.raw_values(),(2.5,5.,7.5))

    def test_saved_configuration_survives_settings_changes_and_process_restart(self):
        config=dict(m.DEFAULTS,measurementSlopeLength=3)
        self.rows=self.seed(config)
        keys=[(r['symbol'],r['interval'],r['open_time']) for r in self.rows]
        with self.features:
            self.features.execute('BEGIN IMMEDIATE')
            a.retire_written(self.features,keys,parameters=config)
        self.assertEqual(self.raw_values(),(None,)*3)
        changed=dict(m.DEFAULTS,measurementSlopeLength=7,measurementBBMultiplier=3.)
        with patch('Section_4_Features.execution.components.desired_parameters',return_value=changed),closing(s.open_db()) as c:
            self.assertEqual(a.known_lengths(c)[a.fingerprint(config)],3)
            got=s.read_row(c,'BTCUSDT','1m',840000)
            self.assertEqual(tuple(got[f] for f in a.FIELDS),(1.5,3.,4.5))

    def test_existing_reader_refreshes_after_new_configuration_is_registered(self):
        config=dict(m.DEFAULTS,measurementSlopeLength=3)
        self.rows=self.seed(config)
        with closing(sqlite3.connect(s.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True)) as c:
            a.install(c)
            query='SELECT '+s.read_expression('ema50_slope_atr')+' FROM features f WHERE open_time=840000'
            self.assertEqual(c.execute(query).fetchone()[0],1.5)
            with self.features:
                self.features.execute('BEGIN IMMEDIATE')
                a.retire_written(self.features,[('BTCUSDT','1m',840000)],parameters=config)
            self.assertEqual(self.raw_values(),(None,)*3)
            self.assertEqual(c.execute(query).fetchone()[0],1.5)

    def test_dry_run_preserves_cells_and_checkpoint(self):
        before=self.raw_values()
        with self.features:
            self.features.execute('BEGIN')
            report=a.clear_verified(self.features,[('BTCUSDT','1m',840000)],
                                    a.known_lengths(self.features),apply=False)
        self.assertEqual(report['values_cleared'],3)
        self.assertEqual(self.raw_values(),before)
        self.assertFalse(self.features.execute("SELECT 1 FROM sqlite_master WHERE name='feature_storage_retirements'").fetchone())

    def test_cleanup_refuses_old_writer_output(self):
        with self.assertRaisesRegex(RuntimeError,'Recent writes still store'):
            job.start(self.features)
        self.assertEqual(self.raw_values(),(2.5,5.,7.5))

    def test_cleanup_resumes_with_atomic_counters_and_preserves_legacy(self):
        self.omit_latest()
        with self.features:
            self.features.execute('UPDATE features SET measurement_config_id=NULL WHERE open_time=360000')
        initial=job.start(self.features)
        self.assertEqual(initial['last_rowid'],0)
        first=job.advance(self.features,batch_size=7)
        self.assertEqual(first['rows_checked'],7)
        with closing(s.open_db()) as c:
            a.install(c)
            state=job.load_state(c)
            self.assertEqual(state,first)
            while not state['complete']:state=job.advance(c,batch_size=4)
            self.assertEqual(state['rows_checked'],15)
            # The null provenance row and the following windows that need its
            # provenance are all preserved, rather than guessed from defaults.
            self.assertGreaterEqual(state['values_retained'],3)
            self.assertEqual(job.advance(c),state)
        self.assertEqual(self.raw_values(360000),(2.5,5.,7.5))
        got=s.read_row(self.features,'BTCUSDT','1m',300000)
        self.assertEqual(tuple(got[f] for f in a.FIELDS),(2.5,5.,7.5))

    def test_batch_mismatch_rolls_back_cells_and_saved_cursor(self):
        self.omit_latest();initial=job.start(self.features)
        with self.features:
            self.features.execute('UPDATE features SET ema50_slope_atr=999 WHERE open_time=480000')
        with self.assertRaisesRegex(ValueError,'formula mismatch'):
            job.advance(self.features)
        self.assertEqual(job.load_state(self.features),initial)
        self.assertEqual(self.raw_values(300000),(2.5,5.,7.5))

    def test_checkpoint_save_failure_rolls_back_already_executed_clears(self):
        self.omit_latest();initial=job.start(self.features)
        with self.features:
            self.features.execute("CREATE TRIGGER fail_checkpoint BEFORE UPDATE ON feature_storage_retirements BEGIN SELECT RAISE(ABORT,'checkpoint failure'); END")
        with self.assertRaisesRegex(sqlite3.IntegrityError,'checkpoint failure'):
            job.advance(self.features)
        self.assertEqual(job.load_state(self.features),initial)
        self.assertEqual(self.raw_values(300000),(2.5,5.,7.5))
        with self.features:self.features.execute('DROP TRIGGER fail_checkpoint')
        self.assertTrue(job.advance(self.features)['complete'])

    def test_cleanup_refuses_replaced_raw_database(self):
        self.omit_latest();initial=job.start(self.features)
        replacement=self.root/'replacement.db'
        shutil.copyfile(k.DB_PATH,replacement);replacement.replace(k.DB_PATH)
        with self.assertRaisesRegex(RuntimeError,'Source database changed'):
            job.advance(self.features)
        self.assertEqual(job.load_state(self.features),initial)

    def test_tampered_registry_cannot_silently_change_lookback(self):
        self.omit_latest();initial=job.start(self.features)
        config=dict(m.DEFAULTS,measurementSlopeLength=99)
        with self.features:
            self.features.execute('UPDATE feature_atr_slope_configs SET spec=? WHERE identity=?',
                                  (json.dumps(config),a.fingerprint(m.DEFAULTS)))
        with self.assertRaisesRegex(ValueError,'fingerprint mismatch'):
            job.advance(self.features)
        self.assertEqual(job.load_state(self.features),initial)

    def test_local_check_accepts_omitted_values_but_still_verifies_formula_reads(self):
        import Section_13_Development.diagnostics.check_atr_slope_readers as check_atr_slope_readers
        self.omit_latest();output=io.StringIO()
        with patch('sys.argv',['Section_13_Development/diagnostics/check_atr_slope_readers.py','--sample','3']),redirect_stdout(output):
            check_atr_slope_readers.main()
        report=json.JSONDecoder().raw_decode(output.getvalue())[0]
        self.assertEqual(report['omitted_values_reconstructed'],9)
        self.assertEqual(report['reader_mismatches'],0)
        self.assertEqual(report['stored_formula_mismatches'],0)

    def test_reader_can_retry_after_a_transient_window_read_failure(self):
        with closing(sqlite3.connect(s.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True)) as c:
            a.install(c)
            query='SELECT '+s.read_expression('ema50_slope_atr')+' FROM features f WHERE open_time=840000'
            with patch.object(a,'read_values',side_effect=[sqlite3.OperationalError('busy'),dict(zip(a.FIELDS,(2.5,5.,7.5)))]):
                with self.assertRaises(sqlite3.OperationalError):c.execute(query).fetchone()
                self.assertEqual(c.execute(query).fetchone()[0],2.5)

    def test_status_reads_checkpoint_without_advancing_it(self):
        self.omit_latest();initial=job.start(self.features);output=io.StringIO()
        with patch('sys.argv',['Section_14_Operations/storage/retire_atr_slope_storage.py','--status']),redirect_stdout(output):
            job.main()
        report=json.loads(output.getvalue())
        self.assertEqual(report['state'],initial)
        self.assertTrue(report['sources_match'])
        self.assertEqual(job.load_state(self.features),initial)

    def test_apply_waits_for_writer_without_bypassing_readiness(self):
        from Section_1_Global_Core import data_policy
        self.omit_latest();job.start(self.features);done=job.advance(self.features)
        output=io.StringIO()
        with patch.object(data_policy,'LOCK_FILE',self.root/'lock'),chdir(self.root),redirect_stdout(output):
            with patch('sys.argv',['Section_14_Operations/storage/retire_atr_slope_storage.py','--apply','--wait-seconds','2']),\
                 patch.object(job,'start',side_effect=[job.WriterNotReady('waiting'),done]) as start,\
                 patch.object(job.time,'sleep'):
                job.main()
        self.assertEqual(start.call_count,2)
        self.assertIn('Waiting for fresh writer output',output.getvalue())
        self.assertEqual(job.load_state(self.features),done)


if __name__=='__main__':unittest.main()
