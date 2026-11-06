"""Actual SQLite export and end-to-end study, without live memory mutation."""
import contextlib
import gzip
import hashlib
import io
import json
import unittest
from unittest.mock import patch
import test_pivot_research as fixtures
from Section_1_Global_Core import pivot_research,btc_hour_sequence_source as source
from Section_1_Global_Core.memory_storage.Storage import klines_store,features_store
import study_btc_hour_sequences as cli

class RowSource(unittest.TestCase):
    def setUp(self):
        fixtures.PivotCohort.setUp(self)
        step=3600000
        conn=klines_store.open_db()
        with conn:conn.execute("UPDATE klines SET interval='1h',open_time=CAST(open_time/60000 AS INTEGER)*?,close_time=(CAST(open_time/60000 AS INTEGER)+1)*?-1 WHERE symbol='BTCUSDT' AND interval='1m'",(step,step))
        conn.close();conn=features_store.open_db()
        with conn:
            conn.execute("UPDATE features SET interval='1h',open_time=CAST(open_time/60000 AS INTEGER)*?,structure_events='[]' WHERE symbol='BTCUSDT' AND interval='1m'",(step,))
            conn.execute("UPDATE feature_engine_state SET interval='1h',last_open_time=CAST(last_open_time/60000 AS INTEGER)*? WHERE symbol='BTCUSDT' AND interval='1m'",(step,))
            conn.execute("UPDATE feature_calculation_versions SET interval='1h' WHERE symbol='BTCUSDT' AND interval='1m'")
            for original in self.pivots:
                event={**original,**{k:original[k]//60000*step for k in ('origin_time','confirmation_time','known_time')}}
                conn.execute("UPDATE features SET structure_events=? WHERE symbol='BTCUSDT' AND interval='1h' AND open_time=?",(json.dumps([event]),event['confirmation_time']))
        conn.close();self.report=pivot_research.scan('BTCUSDT','1h',threshold=1,now_ms=10**12)

    def test_all_closed_rows_and_candidates_export_without_database_writes(self):
        paths=(klines_store.DB_PATH,features_store.DB_PATH)
        digest=lambda:[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        before=digest();packet=source.export(self.report)
        self.assertEqual(len(packet['candles']),65);self.assertEqual(len(packet['pivots']),3)
        self.assertIn('candidate_pivot_low_time',packet['candles'][0]['features'])
        self.assertEqual(len(packet['engine_history']),30)
        self.assertTrue(all(not h['results'] for h in packet['engine_history'].values()))
        self.assertEqual(before,digest());json.dumps(packet,allow_nan=False)

    def test_changed_source_never_silently_joins_old_pivots(self):
        self.report['source_id']='changed'
        with self.assertRaises(ValueError):source.export(self.report)

    def test_cli_complete_export_analysis_and_dashboard(self):
        report=self.root/'cohort.json.gz';report.write_bytes(gzip.compress(json.dumps(self.report).encode()))
        output=self.root/'sequences'
        with patch('sys.argv',['study_btc_hour_sequences.py','--report',str(report),'--output-dir',str(output)]),patch('os.nice',return_value=0,create=True),contextlib.redirect_stdout(io.StringIO()):cli.main()
        raw=cli.read(output/'source_v1.json.gz');analysis=cli.read(output/'analysis_v1.json.gz')
        self.assertEqual(len(raw['candles']),65);self.assertEqual(analysis['counts']['pivots'],3)
        self.assertEqual(len(analysis['snapshots']),65)
        self.assertIn('Every pivot',(output/'analysis_v1.html').read_text())

    def test_publication_compresses_full_dashboard_and_publishes_each_artifact(self):
        report=self.root/'publish-cohort.json.gz';report.write_bytes(gzip.compress(json.dumps(self.report).encode()))
        output=self.root/'published-sequences'
        with patch('sys.argv',['study_btc_hour_sequences.py','--report',str(report),'--output-dir',str(output),'--push-report']),patch('os.nice',return_value=0,create=True),patch.object(cli,'push_report') as publish,contextlib.redirect_stdout(io.StringIO()):cli.main()
        self.assertEqual([c.args[0].name for c in publish.call_args_list],['source_v1.json.gz','analysis_v1.json.gz','analysis_v1.html.gz'])
        self.assertEqual(gzip.decompress((output/'analysis_v1.html.gz').read_bytes()),(output/'analysis_v1.html').read_bytes())
