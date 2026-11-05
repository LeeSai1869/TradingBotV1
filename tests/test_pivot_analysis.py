import copy
import unittest
from analyze_pivot_report import analyze


class PivotReportAnalysis(unittest.TestCase):
    def report(self):
        step=300000;origin=4*step;case=dict(id='one',side='BUY_SIDE',pivot=dict(origin_time=origin,known_time=origin+2*step,price=99),
            next_opposite=dict(origin_time=origin+4*step),origin=dict(status='HIT',first_hit=dict(bars=3)),
            after_known=dict(status='NO_HIT'),origin_hit_by_confirmation=False)
        bars=[]
        for offset,minus in [(-2,30),(-1,40),(0,35),(1,30)]:
            bars.append(dict(client=dict(open_time=origin+offset*step,open=100,high=101,low=99,close=100),
                features=dict(di_plus=10,di_minus=minus,atr=1,rsi=40,adx=30,relative_volume=2,
                              candidate_pivot=-1,current_structure='STRUCTURE_BULL',bearish_structure_active=0)))
        return dict(version='pivot-moves-v1',source_id='source',timeframe='5m',coverage={},summary=dict(pivots=1),cases=[case],contexts={'one':dict(bars=bars)})

    def test_full_counts_timeframe_units_and_feature_profiles(self):
        report=self.report();original=copy.deepcopy(report);result=analyze(report)
        side=result['sides']['BUY_SIDE']
        self.assertEqual(side['origin_hits'],1)
        self.assertEqual(side['median_leg_bars'],4)
        self.assertEqual(side['median_confirmation_delay_bars'],2)
        self.assertIsNone(result['sides']['SELL_SIDE']['median_leg_bars'])
        self.assertEqual(result['profiles'][0]['atr_pct'],1)
        self.assertTrue(result['profiles'][0]['pressure_falling'])
        self.assertTrue(result['profiles'][0]['pressure_peak_near_origin'])
        self.assertEqual(result['quality']['pivot_prices_matching_raw_candle'],1)
        self.assertEqual(report,original)

    def test_missing_values_do_not_become_zero_or_negative_evidence(self):
        report=self.report()
        for row in report['contexts']['one']['bars']:
            for key in ('di_plus','di_minus','atr','rsi'):row['features'][key]=None
        result=analyze(report);profile=result['profiles'][0]
        self.assertIsNone(profile['atr_pct']);self.assertIsNone(profile['pressure_peak_near_origin'])
        self.assertIsNone(profile['pressure_dominant'])
        self.assertIsNone(result['sample_groups'][0]['medians']['rsi'])
        self.assertEqual(result['sample_groups'][0]['counts']['pressure_peak_near_origin']['available'],0)

    def test_inconsistent_or_wrong_report_is_rejected(self):
        report=self.report();report['summary']['pivots']=2
        with self.assertRaises(ValueError):analyze(report)
        report=self.report();report['version']='other'
        with self.assertRaises(ValueError):analyze(report)
