"""ATR reconstruction, provenance fallback and actual Core/SQL/replay readers."""
from contextlib import closing
import contextlib
import io
import json
import random
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from Section_1_Global_Core.memory_storage.Storage import atr_slope_reads as a
from Section_1_Global_Core.memory_storage.Storage import features_store as s, klines_store as k
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader
from Section_4_Features.features import shared_measurements as m


class ATRSlopeReads(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(s, 'DB_PATH', self.root / 'features.db'))
        self.enterContext(patch.object(k, 'DB_PATH', self.root / 'klines.db'))
        self.enterContext(patch.object(downloader, 'DB_PATH', self.root / 'klines.db'))
        downloader.open_db().close()
        self.raw = self.enterContext(closing(k.open_db()))
        self.features = self.enterContext(closing(s.open_db()))
        self.rows = self.seed()

    def seed(self, config=m.DEFAULTS):
        state = {}
        result = []
        for i in range(15):
            bar = dict(symbol='BTCUSDT', interval='1m', open_time=i*60000,
                       close_time=(i+1)*60000-1, open=100., high=101., low=99.,
                       close=100., volume=10.)
            emas = [100.+i, 200.+2*i, 300.+3*i]
            measured = m.calculate(state, bar, 30., 10., 2., *emas, 10., config)
            row = dict(bar, formula_version=3, atr=2., ema50=emas[0],
                       ema200=emas[1], ema300=emas[2], **measured)
            k.insert_rows(self.raw, [bar])
            s.insert_rows(self.features, [row])
            result.append(row)
        # These reader Section_13_Development/tests model retained history from before retirement.
        # New-write omission itself is covered by the storage-policy tests.
        with self.features:
            for row in result:
                self.features.execute('UPDATE features SET '+','.join(f+'=?' for f in a.FIELDS)+
                    ' WHERE symbol=? AND interval=? AND open_time=?',
                    [row[f] for f in a.FIELDS]+[row['symbol'],row['interval'],row['open_time']])
        return result

    def historical(self,row):
        columns=s.storage_columns(self.features)
        with self.features:
            self.features.execute('INSERT OR REPLACE INTO features ('+','.join(columns)+
                ') VALUES ('+','.join('?' for _ in columns)+')',s.storage_values(row,columns))

    def project(self, conn, timestamp):
        a.install(conn)
        return tuple(conn.execute(
            'SELECT '+','.join(s.read_expression(f) for f in a.FIELDS)+
            ' FROM features f WHERE symbol=? AND interval=? AND open_time=?',
            ('BTCUSDT', '1m', timestamp)
        ).fetchone())

    def poison(self):
        with self.features:
            self.features.execute('UPDATE features SET '+
                                  ','.join(f+'=999' for f in a.FIELDS))

    def test_actual_normal_range_sql_and_replay_reads_ignore_poisoned_storage(self):
        self.poison()
        for original in self.rows:
            timestamp = original['open_time']
            expected = tuple(original[f] for f in a.FIELDS)
            self.assertEqual(self.project(self.features, timestamp), expected)
            normal = s.read_row(self.features, 'BTCUSDT', '1m', timestamp)
            replay = s.read_replay_inputs(self.features, 'BTCUSDT', '1m',
                                          timestamp, timestamp+1, a.FIELDS)[0]
            self.assertEqual(tuple(normal[f] for f in a.FIELDS), expected)
            self.assertEqual(tuple(replay[f] for f in a.FIELDS), expected)
        narrow = s.read_range(self.features, 'BTCUSDT', '1m', 14*60000, 15*60000)
        self.assertEqual(tuple(narrow[0][f] for f in a.FIELDS), (2.5, 5., 7.5))
        # Reader changes do not change write policy or clear history.
        self.assertEqual(self.features.execute(
            'SELECT ema50_slope_atr FROM features LIMIT 1').fetchone()[0], 999)

    def test_unknown_or_missing_metadata_and_legacy_versions_retain_values(self):
        self.poison()
        for changes in ("formula_version=1", "formula_version=2",
                        "measurement_config_id='unknown'", "measurement_config_id=NULL",
                        "measurement_version=NULL", "measurement_contiguous_bars=NULL"):
            with self.subTest(changes=changes):
                with self.features:
                    self.features.execute('UPDATE features SET '+changes+' WHERE open_time=840000')
                self.assertEqual(self.project(self.features, 840000), (999.,)*3)
                self.historical(dict(self.rows[-1], **dict.fromkeys(a.FIELDS, 999.)))

    def test_missing_feature_or_raw_history_uses_stored_fallback(self):
        self.poison()
        with self.features:
            self.features.execute('DELETE FROM features WHERE open_time=720000')
        self.assertEqual(self.project(self.features, 840000), (999.,)*3)
        s.insert_rows(self.features, [self.rows[12]])
        with self.raw:
            self.raw.execute('DELETE FROM klines WHERE open_time=720000')
        self.assertEqual(self.project(self.features, 840000), (999.,)*3)

    def test_inconsistent_counters_or_raw_boundaries_use_stored_fallback(self):
        self.poison()
        with self.features:
            self.features.execute('UPDATE features SET measurement_contiguous_bars=999 WHERE open_time=720000')
        self.assertEqual(self.project(self.features, 840000), (999.,)*3)
        s.insert_rows(self.features, [self.rows[12]])
        with self.raw:
            self.raw.execute('UPDATE klines SET close_time=close_time-1 WHERE open_time=720000')
        self.assertEqual(self.project(self.features, 840000), (999.,)*3)

    def test_readonly_connection_observes_external_commits(self):
        with closing(sqlite3.connect(s.DB_PATH.resolve().as_uri()+'?mode=ro', uri=True)) as c:
            a.install(c)
            query = 'SELECT '+s.read_expression('ema50_slope_atr')+' FROM features f WHERE open_time=840000'
            self.assertEqual(c.execute(query).fetchone()[0], 2.5)
            with self.features:
                self.features.execute('UPDATE features SET ema50=ema50+2 WHERE open_time=840000')
            self.assertEqual(c.execute(query).fetchone()[0], 3.5)
            with self.raw:
                self.raw.execute('UPDATE klines SET close_time=close_time-1 WHERE open_time=720000')
            self.assertEqual(c.execute(query).fetchone()[0], 2.5)  # Stored fallback.

    def test_local_rollback_does_not_reuse_a_stale_reconstruction(self):
        a.install(self.features)
        query = 'SELECT '+s.read_expression('ema50_slope_atr')+' FROM features f WHERE open_time=840000'
        self.features.execute('UPDATE features SET ema50=ema50+2 WHERE open_time=840000')
        self.assertEqual(self.features.execute(query).fetchone()[0], 3.5)
        self.features.rollback()
        self.assertEqual(self.features.execute(query).fetchone()[0], 2.5)

    def test_current_invalid_atr_and_individual_missing_ema(self):
        self.poison()
        with self.features:
            self.features.execute('UPDATE features SET ema200=NULL WHERE open_time=720000')
        self.assertEqual(self.project(self.features, 840000), (2.5, None, 7.5))
        with self.features:
            self.features.execute('UPDATE features SET atr=0 WHERE open_time=840000')
        self.assertEqual(self.project(self.features, 840000), (None,)*3)

    def test_no_raw_store_retains_history(self):
        with closing(s.open_db()) as c, patch.object(k, 'DB_PATH', self.root/'missing.db'):
            a.install(c)
            value=c.execute('SELECT '+s.read_expression('ema50_slope_atr')+
                            ' FROM features f WHERE open_time=840000').fetchone()[0]
            self.assertEqual(value, 2.5)

    def test_nondefault_lookback_uses_exact_known_configuration(self):
        config=dict(m.DEFAULTS,measurementSlopeLength=3)
        self.rows=self.seed(config)
        self.poison()
        with patch.object(a,'known_lengths',return_value={a.fingerprint(config):3}):
            self.assertEqual(self.project(self.features,840000),(1.5,3.,4.5))

    def test_calendar_months_use_actual_close_boundaries(self):
        from datetime import datetime,timezone
        timestamp=lambda month:int(datetime(2026,month,1,tzinfo=timezone.utc).timestamp()*1000)
        rows=[]
        for i,month in enumerate((1,2,3)):
            rows.append(dict(open_time=timestamp(month),close_time=timestamp(month+1)-1,
                close=100.,formula_version=3,measurement_version='shared-v1',
                measurement_config_id='calendar',measurement_contiguous_bars=i+1,
                atr=2.,ema50=100.+i,ema200=200.+2*i,ema300=300.+3*i))
        self.assertEqual(a.reconstruct(rows,{'calendar':2}),
                         dict(zip(a.FIELDS,(1.,2.,3.))))

    def test_local_check_reports_parity_and_unknown_provenance_without_writes(self):
        import Section_13_Development.diagnostics.check_atr_slope_readers as check_atr_slope_readers
        with self.features:
            self.features.execute('UPDATE features SET measurement_config_id=NULL WHERE open_time=840000')
        output=io.StringIO()
        with patch('sys.argv',['Section_13_Development/diagnostics/check_atr_slope_readers.py','--sample','1']),contextlib.redirect_stdout(output):
            check_atr_slope_readers.main()
        report=json.JSONDecoder().raw_decode(output.getvalue())[0]
        self.assertEqual(report['preserved_values'],3)
        self.assertEqual(report['reader_mismatches'],0)
        self.assertEqual(report['stored_formula_mismatches'],0)
        self.assertEqual(self.features.execute('SELECT measurement_config_id FROM features WHERE open_time=840000').fetchone()[0],None)

    def test_full_feature_reads_batch_history_and_keep_borrowed_transactions(self):
        self.poison()
        with patch.object(a,'read_values',side_effect=AssertionError('No per-cell history queries')):
            rows=s.read_range(self.features,'BTCUSDT','1m',0,900000)
        self.assertEqual(tuple(rows[-1][f] for f in a.FIELDS),(2.5,5.,7.5))
        self.assertFalse(self.features.in_transaction)
        self.features.execute('BEGIN')
        s.read_row(self.features,'BTCUSDT','1m',840000)
        self.assertTrue(self.features.in_transaction)
        self.features.rollback()

    def test_batch_prefix_and_feature_values_share_one_snapshot(self):
        self.features.execute('PRAGMA main.journal_mode=WAL')
        original=a.resolve_rows
        def concurrent_commit(conn,rows):
            with closing(sqlite3.connect(s.DB_PATH)) as writer:
                with writer:writer.execute('UPDATE features SET ema50=ema50+2 WHERE open_time=540000')
            return original(conn,rows)
        with patch.object(a,'resolve_rows',side_effect=concurrent_commit):
            self.assertEqual(s.read_row(self.features,'BTCUSDT','1m',840000)['ema50_slope_atr'],2.5)
        self.assertEqual(s.read_row(self.features,'BTCUSDT','1m',840000)['ema50_slope_atr'],1.5)

    def test_randomized_windows_match_live_rules_including_all_resets(self):
        rng = random.Random(42)
        state = {}; history = []; timestamp = 0; lengths = {}
        for i in range(250):
            timestamp += 120000 if i % 41 == 0 else 60000
            config = dict(m.DEFAULTS, measurementSlopeLength=3 if i<125 else 5,
                          measurementBBMultiplier=3. if 50<=i<90 else 2.)
            lengths[a.fingerprint(config)] = config['measurementSlopeLength']
            bar = dict(open_time=timestamp, close_time=timestamp+59999,
                       close=0. if i%37==0 else 100.+rng.random(), volume=10.)
            emas = [100.+rng.random(), 200.+rng.random(), 300.+rng.random()]
            if i%23 == 0: emas[i%3] = None
            atr = 0. if i%17==0 else 2.
            expected = m.calculate(state,bar,30.,10.,atr,*emas,10.,config)
            row = dict(bar,formula_version=3,atr=atr,ema50=emas[0],ema200=emas[1],ema300=emas[2],**expected)
            history.append(row)
            result = a.reconstruct(history[-config['measurementSlopeLength']-1:], lengths)
            self.assertEqual(result, {f:expected[f] for f in a.FIELDS}, i)


if __name__ == '__main__': unittest.main()
