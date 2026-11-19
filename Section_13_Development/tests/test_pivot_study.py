import unittest
from Section_8_Decision_Engine.pivot_study import measure


def row(n,high=101,low=99,open=100,close=100):
    return dict(open_time=n*60000,close_time=(n+1)*60000-1,open=open,high=high,low=low,close=close)


class PivotOutcomes(unittest.TestCase):
    def test_both_directions_exact_two_percent_first_hit_and_count(self):
        up=measure([row(1),row(2,high=102)],100,'BUY_SIDE',60000,end_time=120000)
        down=measure([row(1),row(2,low=98)],100,'SELL_SIDE',60000,end_time=120000)
        for packet in (up,down):
            self.assertEqual(packet['status'],'HIT');self.assertEqual(packet['first_hit']['bars'],2)
            self.assertTrue(packet['complete']);self.assertEqual(packet['max_favorable_pct'],2.0000000000000018)

    def test_missing_bars_censor_without_invented_target_hits(self):
        result=measure([row(1),row(3,high=110)],100,'BUY_SIDE',60000,end_time=180000)
        self.assertEqual(result['status'],'CENSORED');self.assertTrue(result['gap'])
        self.assertIsNone(result['first_hit'])
        observed=measure([row(1,high=103),row(3)],100,'BUY_SIDE',60000,end_time=180000)
        self.assertEqual(observed['status'],'HIT');self.assertFalse(observed['complete'])

    def test_incomplete_tail_is_not_a_failed_swing(self):
        result=measure([row(1)],100,'BUY_SIDE',60000,end_time=120000)
        self.assertEqual(result['status'],'CENSORED')
        complete=measure([row(1),row(2)],100,'BUY_SIDE',60000,end_time=120000)
        self.assertEqual(complete['status'],'NO_HIT')

    def test_horizon_limits_outcomes_and_does_not_use_future_extremes(self):
        result=measure([row(1),row(2,high=110)],100,'BUY_SIDE',60000,bars=1)
        self.assertEqual(result['status'],'NO_HIT');self.assertIsNone(result['first_hit'])
        self.assertEqual(result['max_favorable_pct'],1.0000000000000009)

    def test_invalid_reference_or_price_does_not_fabricate_a_move(self):
        for reference in (0,float('nan'),float('inf')):
            result=measure([row(1,high=110)],reference,'BUY_SIDE',60000,end_time=60000)
            self.assertEqual(result['status'],'CENSORED');self.assertIsNone(result['reference'])
        result=measure([row(1,high=float('nan'))],100,'BUY_SIDE',60000,end_time=60000)
        self.assertEqual(result['status'],'CENSORED');self.assertIsNone(result['first_hit'])
