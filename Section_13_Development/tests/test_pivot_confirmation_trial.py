"""Offline proposed pivot rules: fixed confirmed-pair range and close confluence."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('pivot_trial',ROOT/'Section_12_Research/experiments/pivot_confirmation/trial.py')
trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)


def bars(values,**overrides):
    rows=[]
    for i,value in enumerate(values):
        row=dict(open_time=i*900000,close_time=(i+1)*900000-1,open=value,high=value,low=value,close=value)
        row.update(overrides.get(i,{}));rows.append(row)
    return rows


def seed(direction=-1,price=97500):
    return dict(pair=[90000,100000] if direction==-1 else [100000,90000],direction=direction,candidate=dict(price=price,origin=0))


class ProposedPivotRules(unittest.TestCase):
    def test_reference_is_last_two_confirmed_not_candidate_to_anchor(self):
        result=trial.simulate(bars([97500,98000,99000]),seed=seed())
        self.assertEqual(result['events'],[])
        self.assertEqual(result['final']['reference_range'],10000)
        self.assertEqual(result['final']['threshold'],100000)
        result=trial.simulate(bars([97500,98000,99000,100000]),seed=seed())
        self.assertEqual(result['events'][0]['price'],97500)
        self.assertEqual(result['events'][0]['reference_range'],10000)
        self.assertEqual(result['events'][0]['confirmation_time'],2700000)
    def test_new_low_replaces_candidate_resets_closes_but_not_reference(self):
        result=trial.simulate(bars([97500,98000,95000,97000,97500]),seed=seed())
        self.assertEqual(len(result['events']),1)
        event=result['events'][0]
        self.assertEqual(event['price'],95000);self.assertEqual(event['origin_time'],1800000)
        self.assertEqual(event['threshold'],97500);self.assertEqual(event['reverse_closes'],2)
    def test_distance_without_two_closes_does_not_confirm(self):
        self.assertEqual(trial.simulate(bars([97500,100000]),seed=seed())['events'],[])
    def test_interruption_and_equal_close_reset_count(self):
        for values in ([97500,100000,99000,100100],[97500,100000,100000,100100]):
            self.assertEqual(trial.simulate(bars(values),seed=seed())['events'],[])
    def test_high_rule_mirrors_low_rule(self):
        result=trial.simulate(bars([92500,92000,91000,90000]),seed=seed(1,92500))
        event=result['events'][0]
        self.assertEqual(event['type'],'PIVOT_HIGH');self.assertEqual(event['threshold'],90000)
    def test_opposite_extreme_is_preserved_from_pivot_origin_not_confirmation(self):
        rows=bars([97500,98000,99000,100000])
        rows[1]['high']=101000
        result=trial.simulate(rows,seed=seed())
        self.assertEqual(result['final']['candidate_price'],101000)
        self.assertEqual(result['final']['candidate_time'],900000)
        self.assertEqual(result['final']['reference_range'],2500)
    def test_delayed_activation_retains_extremes_observed_before_activation(self):
        s=dict(pair=[100,110],direction=-1,candidate=dict(price=80,origin=0))
        result=trial.simulate(bars([80,95,82,81,81.5,83,82,81.8]),seed=s)
        self.assertEqual([e['price'] for e in result['events']],[80,95])
        self.assertEqual(result['final']['candidate_price'],81)
        self.assertEqual(result['final']['candidate_time'],2700000)
    def test_decimal_equality_counts(self):
        s=dict(pair=['.1038','.1026'],direction=1,candidate=dict(price='.1038',origin=0))
        result=trial.simulate(bars([.1038,.1036,.1035]),seed=s)
        self.assertEqual(result['events'][0]['threshold'],.1035)
    def test_gaps_are_not_treated_as_consecutive_closes(self):
        rows=bars([97500,98000,100000]);rows[-1]['open_time']+=900000
        with self.assertRaisesRegex(ValueError,'gap'):trial.simulate(rows,seed=seed())
    def test_prefix_results_do_not_change_when_future_candles_are_appended(self):
        rows=bars([97500,98000,99000,100000,99000,98000,97000,98000,99000])
        full=trial.simulate(rows,seed=seed())
        for length in range(2,len(rows)):
            partial=trial.simulate(rows[:length],seed=seed())
            expected=[e for e in full['events'] if e['confirmation_time']<=rows[length-1]['open_time']]
            self.assertEqual(partial['events'],expected)


class RealExportTrial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json,gzip
        path=ROOT/'Section_12_Research/reports/pivot_debug/ENAUSDT-15m-20261126/stored-pivots.json.gz'
        cls.stored=json.loads(gzip.decompress(path.read_bytes()));cls.result=trial.run(cls.stored)
    def test_real_export_counts_and_no_adjacent_confirmations(self):
        stats=self.result['summary']
        self.assertEqual(stats['current_stored']['confirmations'],1768)
        self.assertEqual(stats['confirmed_pair_only']['confirmations'],1811)
        self.assertEqual(stats['confirmed_pair_two_closes']['confirmations'],528)
        self.assertEqual(stats['confirmed_pair_two_closes']['confirmations_on_adjacent_candles'],0)
    def test_every_proposed_event_satisfies_frozen_pair_reference_and_two_closes(self):
        pair=[trial.D(v) for v in trial.seed_from_row(self.stored['candles'][0])['pair']]
        bytime={r['open_time']:i for i,r in enumerate(self.stored['candles'])};previous=None
        for event in self.result['variants']['confirmed_pair_two_closes']['events']:
            self.assertEqual(trial.D(event['reference_range']),abs(pair[-1]-pair[-2]))
            self.assertGreaterEqual(event['reverse_closes'],2)
            self.assertGreater(event['confirmation_time'],event['origin_time'])
            self.assertEqual(event['known_time'],event['confirmation_time']+900000)
            if previous:self.assertNotEqual(previous['type'],event['type'])
            i=bytime[event['confirmation_time']];values=[trial.D(r['close']) for r in self.stored['candles'][i-2:i+1]]
            self.assertTrue(values[0]>values[1]>values[2] if event['type']=='PIVOT_HIGH' else values[0]<values[1]<values[2])
            pair=[pair[-1],trial.D(event['price'])];previous=event
    def test_no_confirmed_high_or_low_skips_a_more_extreme_post_anchor_candle(self):
        rows=self.stored['candles'];bytime={r['open_time']:i for i,r in enumerate(rows)}
        previous=None
        for event in self.result['variants']['confirmed_pair_two_closes']['events']:
            if previous:
                first=bytime[previous['origin_time']]+1;last=bytime[event['confirmation_time']]+1
                field='high' if event['type']=='PIVOT_HIGH' else 'low'
                extreme=(max if field=='high' else min)(r[field] for r in rows[first:last])
                self.assertEqual(event['price'],extreme)
            previous=event
