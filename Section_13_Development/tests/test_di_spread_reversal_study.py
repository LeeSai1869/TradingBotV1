
from Section_1_Global_Core.paths import REPO_ROOT
import importlib.util
from pathlib import Path
import unittest

path=REPO_ROOT/'Section_12_Research/reports/BTC_1h_di_spread_reversal/study.py'
spec=importlib.util.spec_from_file_location('di_reversal_study',path)
study=importlib.util.module_from_spec(spec);spec.loader.exec_module(study)

def row(i,minus=55,plus=5,rsi=15,**prices):
    return dict(open_time=i*study.HOUR,close_time=(i+1)*study.HOUR-1,open=100,high=100.5,low=99.5,close=100,features=dict(di_minus=minus,di_plus=plus,rsi=rsi,measurement_gap=False),**prices)

class ReversalStudyTests(unittest.TestCase):
    def test_first_drop_is_known_at_close_and_cannot_buy_peak_or_repeated_declines(self):
        rows=[row(0,minus=50),row(1,minus=60),row(2,minus=55),row(3,minus=53),row(4)]
        self.assertFalse(study.signal(rows,1,50,rsi=True))
        self.assertTrue(study.signal(rows,2,50,rsi=True))
        self.assertFalse(study.signal(rows,3,50,rsi=True))
        rows[2]['features']['rsi']=20;self.assertFalse(study.signal(rows,2,50,rsi=True))

    def test_plateaus_threshold_timing_and_input_gaps_are_explicit(self):
        rows=[row(0,minus=60),row(1,minus=60),row(2,minus=49),row(3)]
        self.assertFalse(study.signal(rows,2,50))
        self.assertTrue(study.signal(rows,2,45));self.assertTrue(study.signal(rows,2,50,at_peak=True))
        rows[2]['features']['di_minus']=44
        self.assertFalse(study.signal(rows,2,40));self.assertTrue(study.signal(rows,2,40,peak_only=True))
        rows[1]['features']['measurement_gap']=True;self.assertFalse(study.signal(rows,2,40,peak_only=True))

    def test_net_target_includes_both_sides_costs_and_next_open_entry(self):
        self.assertAlmostEqual(study.net_return(study.target_reference(100),100),1)
        self.assertGreater(study.target_reference(100),101)
        rows=[row(0),row(1)];rows[1].update(open=110,high=111,low=109,close=110)
        result=study.outcome(rows,0,horizon=1)
        self.assertEqual(result['status'],'TIMEOUT','signal-candle close must not be used as entry')

    def test_stop_target_ambiguity_is_conservative_but_a_gap_up_target_is_first(self):
        rows=[row(0),row(1),row(2)];rows[1].update(high=103,low=98)
        result=study.outcome(rows,0,horizon=2,stop=.01)
        self.assertEqual(result['status'],'STOP');self.assertTrue(result['ambiguous'])
        rows[1].update(high=100.5,low=99.5);rows[2].update(open=103,high=104,low=98,close=103)
        result=study.outcome(rows,0,horizon=2,stop=.01)
        self.assertEqual(result['status'],'TARGET');self.assertFalse(result['ambiguous'])

    def test_dataset_end_and_missing_candles_never_count_as_successful_recovery(self):
        rows=[row(0),row(1)];rows[1]['high']=103
        early=study.outcome(rows,0,horizon=24)
        self.assertEqual(early['status'],'TARGET');self.assertEqual(study.summary([early])['evaluable'],0)
        rows=[row(0),row(1),row(3)];gap=study.outcome(rows,0,horizon=3)
        self.assertEqual(gap['status'],'GAP_CENSORED');self.assertIsNone(gap['net_pct'])

if __name__=='__main__':unittest.main()
