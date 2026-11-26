"""Regression checks against the exact Mac export; no market DB or network."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('pivot_audit',ROOT/'Section_13_Development/diagnostics/audit_pivot_debug.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
DATA=ROOT/'Section_12_Research/reports/pivot_debug/ENAUSDT-15m-20261126'


class MacPivotEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stored=audit.read(DATA/'stored-pivots.json.gz');cls.chart=audit.read(DATA/'chart-pivots.json')
        cls.result=audit.audit(cls.stored,cls.chart)
    def test_all_exported_confirmations_have_correct_origins_and_25_percent_closes(self):
        self.assertEqual(self.result['confirmed_events'],dict(PIVOT_HIGH=884,PIVOT_LOW=884))
        self.assertEqual(self.result['confirmation_errors'],[])
    def test_browser_and_database_events_match(self):
        self.assertEqual(self.result['chart']['overlapping_closed_candles'],2503)
        self.assertEqual(self.result['chart']['event_mismatches'],[])
    def test_long_gap_has_no_eligible_25_percent_close(self):
        gap=[r for r in self.stored['candles'] if 1795445100000<r['open_time']<1795627800000]
        self.assertEqual(len(gap),202)
        for row in gap:
            f=row['features'];threshold=f['candidate_pivot_low_price']+.25*(f['current_active_pivot_high']-f['candidate_pivot_low_price'])
            self.assertLess(row['close'],threshold)
    def test_current_high_has_not_retraced_25_percent(self):
        f=self.stored['candles'][-1]['features']
        level=f['candidate_pivot_high_price']-.25*(f['candidate_pivot_high_price']-f['current_active_pivot_low'])
        self.assertAlmostEqual(level,.10075)
        after=[r for r in self.stored['candles'] if r['open_time']>f['candidate_pivot_high_time']]
        self.assertEqual(min(r['close'] for r in after),.1015)
    def test_detects_separate_float_boundary_cases_without_confusing_them_with_gap(self):
        missed=self.result['eligible_closes_without_confirmation']
        self.assertEqual(len(missed),4)
        for item in missed:self.assertLess(abs(item['close']-item['threshold']),1e-15)
        self.assertFalse(any(1795445100000<i['open_time']<1795627800000 for i in missed))
