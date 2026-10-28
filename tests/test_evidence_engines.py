import copy
import unittest
from Section_9_Confidence_Engine.engine import evaluate as confidence,_context as confidence_cache
from Section_10_Opportunity_Engine.engine import evaluate as opportunity
from Section_9_Confidence_Engine.presentation import annotate


def features():
    return dict(formula_version=3,atr=2.,ema50=98.,ema200=95.,vwap=99.,rsi=65.,
        di_plus=30.,di_minus=10.,adx=32.,current_structure='STRUCTURE_BULL',
        support_zone_low=96.,support_zone_high=98.,resistance_zone_low=106.,resistance_zone_high=106.5,
        inst_resistance_zone_low=106.,inst_resistance_zone_high=106.5,nearest_swing_high=116.,
        protected_high=125.,atr_ma_ratio=1.)


class ConfidenceTests(unittest.TestCase):
    def test_directional_scores_and_explainable_caps(self):
        f=features();before=copy.deepcopy(f);result=confidence(100.,f)
        self.assertEqual(result['status'],'ready');self.assertGreater(result['buy_score'],result['sell_score'])
        self.assertEqual(result['coverage'],1.)
        self.assertEqual(sum(g['weight'] for g in result['groups']),100)
        self.assertEqual(f,before)
        for g in result['groups']:
            self.assertLessEqual(g['buy_points'],g['weight']);self.assertLessEqual(g['sell_points'],g['weight'])

    def test_missing_values_never_add_confidence_or_fake_probability(self):
        result=confidence(100.,{'atr':2.})
        self.assertEqual(result['buy_score'],0);self.assertEqual(result['coverage'],0.)
        self.assertEqual(result['preference'],'not a decision');self.assertIn('never from BUY/SELL',result['interpretation'])
        self.assertIsNone(confidence(100.,{'atr':0})['buy_score'])
        self.assertIsNone(confidence(float('nan'),features())['sell_score'])

    def test_correlated_location_features_do_not_multiply_weight(self):
        f=features();a=confidence(100.,f)
        f.update(inst_support_zone_low=96.,inst_support_zone_high=98.,nearest_bull_fvg_low=96.,nearest_bull_fvg_high=98.)
        b=confidence(100.,f)
        self.assertEqual(a['buy_score'],b['buy_score'])

    def test_bear_mirror_and_changed_features_invalidate_cache(self):
        confidence_cache.cache_clear();a=confidence(100.,features());confidence(100.,features())
        self.assertGreater(confidence_cache.cache_info().hits,0)
        f=features();f.update(ema50=102.,ema200=105.,vwap=101.,rsi=35.,di_plus=10.,di_minus=30.,current_structure='STRUCTURE_BEAR',support_zone_low=92.,support_zone_high=94.,resistance_zone_low=102.,resistance_zone_high=104.,inst_resistance_zone_low=None,inst_resistance_zone_high=None)
        b=confidence(100.,f);self.assertGreater(b['sell_score'],b['buy_score']);self.assertNotEqual(a,b)


class OpportunityTests(unittest.TestCase):
    def test_three_ordered_targets_costs_and_structural_invalidation(self):
        result=opportunity(100.,features());buy=result['buy'];sell=result['sell']
        self.assertEqual([t['price'] for t in buy['targets']],[106.,115.95,124.95])
        self.assertEqual(buy['invalidation'],95.8);self.assertEqual(buy['invalidation_source'],'support')
        self.assertGreater(buy['risk_pct'],4.2)
        for target in buy['targets']:
            self.assertLess(target['net_reward_pct'],target['gross_reward_pct'])
            self.assertGreater(target['reward_risk'],0)
        self.assertGreater(sell['invalidation'],100.)
        self.assertTrue(all(t['price']<100 for t in sell['targets']))

    def test_deduplicate_families_and_no_transitive_zone_chaining(self):
        f=features();f.update(nearest_swing_high=106.2,protected_high=106.4)
        targets=opportunity(100.,f)['buy']['targets']
        self.assertEqual(targets[0]['sources'].count('resistance'),1)
        self.assertEqual(targets[0]['families'].count('sr'),1)
        self.assertEqual(len(targets),1);self.assertEqual(targets[0]['low'],106.);self.assertEqual(targets[0]['high'],106.5)

    def test_missing_layers_and_atr_stop_are_explicit(self):
        result=opportunity(100.,{'atr':2.})
        self.assertEqual(result['buy']['targets'],[])
        self.assertEqual(result['buy']['invalidation_source'],'ATR model (1.5 ATR)')
        self.assertEqual(result['buy']['status'],'no known targets')
        self.assertEqual(opportunity(100.,{'atr':0})['status'],'unavailable')
        f=features();f.update(ema50=None,ema200=None,vwap=None,support_zone_low=None,support_zone_high=None,nearest_swing_high=None,protected_high=None)
        result=opportunity(100.,f)
        self.assertEqual(len(result['buy']['targets']),1)
        self.assertIsNotNone(result['sell']['invalidation']) # No three-zone prerequisite.

    def test_fees_reduce_reward_and_unprofitable_nearby_barrier_is_not_favorable(self):
        a=opportunity(100.,features(),fee_bps=0,slippage_bps=0)
        b=opportunity(100.,features(),fee_bps=10,slippage_bps=10)
        self.assertGreater(a['buy']['targets'][0]['net_reward_pct'],b['buy']['targets'][0]['net_reward_pct'])
        f=features();f.update(atr=.001,ema50=100.01)
        self.assertLess(opportunity(100.,f)['buy']['targets'][0]['net_reward_pct'],0)
        self.assertEqual(opportunity(100.,f)['buy']['status'],'limited reward/risk')
        for invalid in (-1,float('nan'),101):
            with self.assertRaises(ValueError):opportunity(100.,f,fee_bps=invalid)

    def test_extreme_numeric_inputs_never_publish_nonfinite_outputs(self):
        import json
        result=opportunity(1e-300,{'atr':1e300,'protected_high':1e300})
        json.dumps(result,allow_nan=False)

    def test_near_barrier_edge_not_center_and_input_not_mutated(self):
        f=features();before=dict(f)
        self.assertEqual(opportunity(100.,f)['buy']['targets'][0]['price'],106.)
        self.assertEqual(f,before)


class EvidencePresentationTests(unittest.TestCase):
    def test_only_closed_ready_features_annotated_and_signals_unchanged(self):
        rows=[dict(open_time=i*60000,client={'close':100.,'close_time':(i+1)*60000-1},features=features(),momentum={'signal_type':'BUY' if i==0 else None}) for i in range(3)]
        rows[1]['features']['formula_version']=2
        before=copy.deepcopy(rows)
        annotate(rows,now_ms=120000)
        self.assertEqual(rows[0]['momentum'],before[0]['momentum'])
        self.assertIsNotNone(rows[0]['confidence']);self.assertIsNotNone(rows[0]['opportunity'])
        self.assertEqual(rows[1]['confidence'],rows[0]['confidence'])
        self.assertEqual(rows[1]['signal_context']['state'],'coverage unknown')
        self.assertIsNone(rows[2]['opportunity'])
        for a,b in zip(rows,before):self.assertEqual(a['features'],b['features']);self.assertEqual(a['client'],b['client'])

if __name__=='__main__':unittest.main()
