"""Experimental rules only: never start a writer or change stored formulas."""
import copy
import unittest
from Section_12_Research.experiments.current_move_pivots.trial import simulate,D
from test_pivot_confirmation_trial import bars,seed

class CurrentMoveTrial(unittest.TestCase):
    def test_user_prices_confirm_first_high_with_current_move_not_fixed_pair(self):
        s=dict(pair=['.5818','.1302'],direction=1,candidate=dict(price=D('.4802'),origin=0))
        rows=bars([.4802,.43,.38])
        proposed=simulate(rows,seed=s)
        event=proposed['events'][0]
        self.assertEqual(event['reference_range'],.35)
        self.assertEqual(event['threshold'],.3927)
        self.assertEqual(event['reverse_closes'],2)
        self.assertEqual(event['confirmation_time'],rows[2]['open_time'])
        self.assertEqual(simulate(rows,seed=s,reference='confirmed_pair')['events'],[])
    def test_new_extreme_changes_current_move_and_resets_closes(self):
        s=dict(pair=[100,80],direction=1,candidate=dict(price=D(100),origin=0))
        r=simulate(bars([100,97,110,108,103,102]),seed=s)
        self.assertEqual(r['states'][2]['reference_range'],30)
        self.assertEqual(r['states'][2]['threshold'],102.5)
        self.assertEqual(r['states'][2]['reverse_closes'],0)
        self.assertEqual(r['events'][0]['confirmation_time'],4500000)
        self.assertEqual(r['events'][0]['price'],110)
    def test_distance_alone_one_reverse_close_is_not_enough(self):
        self.assertEqual(simulate(bars([97500,100000]),seed=seed())['events'],[])
    def test_high_and_low_are_mirrors(self):
        high=dict(pair=[100,80],direction=1,candidate=dict(price=D(100),origin=0))
        low=dict(pair=[100,120],direction=-1,candidate=dict(price=D(100),origin=0))
        h=simulate(bars([100,98,95]),seed=high)['events'][0]
        l=simulate(bars([100,102,105]),seed=low)['events'][0]
        self.assertEqual(h['reference_range'],l['reference_range'])
        self.assertEqual(h['threshold'],95);self.assertEqual(l['threshold'],105)
    def test_equal_and_interrupted_closes_reset_streak(self):
        s=dict(pair=[120,80],direction=1,candidate=dict(price=D(100),origin=0))
        for rows in (bars([100,94,94]),bars([100,94,95])):
            self.assertEqual(simulate(rows,seed=s)['events'],[])
    def test_wick_alone_does_not_cross_close_threshold(self):
        s=dict(pair=[120,80],direction=1,candidate=dict(price=D(100),origin=0))
        rows=bars([100,99,98]);rows[-1]['low']=90
        self.assertEqual(simulate(rows,seed=s)['events'],[])
    def test_missing_candles_rejected_and_input_not_mutated(self):
        rows=bars([100,98,95]);before=copy.deepcopy(rows)
        s=dict(pair=[100,80],direction=1,candidate=dict(price=D(100),origin=0))
        simulate(rows,seed=s);self.assertEqual(rows,before)
        rows[-1]['open_time']+=900000
        with self.assertRaisesRegex(ValueError,'gap'):simulate(rows,seed=s)
    def test_prefix_events_unchanged_by_future_candles(self):
        rows=bars([100,98,95,96,98,102,100,98,99,100])
        s=dict(pair=[100,80],direction=1,candidate=dict(price=D(100),origin=0))
        events=simulate(rows,seed=s)['events']
        for n in range(2,len(rows)):
            self.assertEqual(simulate(rows[:n],seed=s)['events'],[e for e in events if e['confirmation_time']<=rows[n-1]['open_time']])

    def test_two_closes_do_not_guarantee_a_minimum_swing_size(self):
        from Section_12_Research.experiments.current_move_pivots.evaluate import shrinking_rows
        rows,s=shrinking_rows()
        events=simulate(rows,seed=s)['events']
        self.assertEqual(len(events),30)
        self.assertTrue(all(e['reverse_closes']>=2 for e in events))
        self.assertLess(abs(events[-1]['price']-events[-2]['price']),.000001)

class ArchivedCurrentMoveResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gzip,json
        from pathlib import Path
        from Section_12_Research.experiments.current_move_pivots.evaluate import ROOT,HERE
        cls.summary=json.loads((HERE/'results/summary.json').read_text())
        cls.events=json.loads((HERE/'results/ENAUSDT_15m-events.json').read_text())['current_move_two_closes']
        cls.rows=json.loads(gzip.decompress((ROOT/'Section_12_Research/reports/pivot_debug/ENAUSDT-15m-20261126/stored-pivots.json.gz').read_bytes()))['candles']
    def test_both_archives_filter_over_half_the_distance_only_events(self):
        for key in ('ENAUSDT_15m','BTCUSDT_1h'):
            stats=self.summary[key]['summary']
            self.assertLess(stats['current_move_two_closes']['confirmations'],stats['current_move_only']['confirmations']/2)
            self.assertEqual(stats['current_move_two_closes']['adjacent_confirmations'],0)
            self.assertEqual(stats['current_move_two_closes']['median_confirmation_lag_bars'],3)
        self.assertEqual(self.summary['ENAUSDT_15m']['summary']['confirmed_pair_two_closes']['confirmations'],528)
    def test_real_events_obey_current_move_distance_close_sequence_and_extremes(self):
        from decimal import Decimal
        bytime={r['open_time']:i for i,r in enumerate(self.rows)}
        previous=None
        for event in self.events:
            span=abs(event['price']-event['anchor_price'])
            self.assertAlmostEqual(span,event['reference_range'],places=10)
            high=event['type']=='PIVOT_HIGH';level=event['price']+(-1 if high else 1)*span*.25
            self.assertAlmostEqual(level,event['threshold'],places=10)
            self.assertTrue(event['confirmation_close']<=level+1e-12 if high else event['confirmation_close']>=level-1e-12)
            i=bytime[event['confirmation_time']];closes=[r['close'] for r in self.rows[i-2:i+1]]
            self.assertTrue(closes[0]>closes[1]>closes[2] if high else closes[0]<closes[1]<closes[2])
            if previous:
                self.assertNotEqual(previous['type'],event['type'])
                self.assertEqual(event['anchor_price'],previous['price'])
                start=bytime[previous['origin_time']]+1
                field='high' if high else 'low'
                extreme=(max if high else min)(r[field] for r in self.rows[start:i+1])
                self.assertEqual(event['price'],extreme)
            self.assertGreater(event['confirmation_time'],event['origin_time'])
            previous=event

    def test_archived_prefix_does_not_use_future_bars(self):
        from Section_12_Research.experiments.pivot_confirmation.trial import seed_from_row
        s=seed_from_row(self.rows[0])
        for length in (250,1000,2000):
            prefix=simulate(self.rows[:length],seed=s)['events']
            self.assertEqual(prefix,[e for e in self.events if e['confirmation_time']<=self.rows[length-1]['open_time']])
