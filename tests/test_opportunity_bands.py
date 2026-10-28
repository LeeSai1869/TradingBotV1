import unittest
from Section_10_Opportunity_Engine.engine import evaluate


class BandTests(unittest.TestCase):
    def test_overlapping_real_zones_merge_before_layer_selection(self):
        f=dict(atr=1,resistance_zone_low=105,resistance_zone_high=108,
            nearest_bear_fvg_low=107,nearest_bear_fvg_high=110,
            active_bear_ob_low=109,active_bear_ob_high=112)
        bands=evaluate(100,f)['buy']['targets']
        self.assertEqual(len(bands),1)
        self.assertEqual((bands[0]['low'],bands[0]['high']),(105,112))
        self.assertEqual(set(bands[0]['families']),{'sr','fvg','ob'})

    def test_close_point_references_are_bands_not_three_congested_lines(self):
        f=dict(atr=.0074,nearest_fib_price=.2364948,vwap=.23189008,ema50=.22851471)
        bands=evaluate(.2375,f)['sell']['targets']
        self.assertLess(len(bands),3)
        self.assertTrue(all(b['low']<b['high']<.2375 for b in bands))
        self.assertTrue(all(b['net_reward_far_pct']>b['net_reward_pct'] for b in bands))
        self.assertTrue(all(b['modeled'] for b in bands))

    def test_opposing_area_is_distinct_from_the_invalidation_rule(self):
        result=evaluate(100,dict(atr=1,support_zone_low=95,support_zone_high=97,resistance_zone_low=104,resistance_zone_high=106))
        self.assertEqual(result['sell']['opposing_band']['low'],104)
        self.assertEqual(result['buy']['opposing_band']['high'],97)
        self.assertGreater(result['sell']['invalidation'],result['sell']['risk_band']['high'])

    def test_missing_known_levels_are_not_filled_to_force_three_areas(self):
        result=evaluate(100,dict(atr=1,protected_high=110))
        self.assertEqual(len(result['buy']['targets']),1)
        self.assertTrue(result['buy']['targets'][0]['modeled'])
        self.assertEqual(result['sell']['targets'],[])

class SixAreaTests(unittest.TestCase):
    @staticmethod
    def features():
        return dict(formula_version=3,atr=1,support_zone_low=92,support_zone_high=94,
            inst_support_zone_low=82,inst_support_zone_high=84,nearest_bull_fvg_low=72,nearest_bull_fvg_high=74,
            resistance_zone_low=106,resistance_zone_high=108,inst_resistance_zone_low=116,inst_resistance_zone_high=118,
            nearest_bear_fvg_low=126,nearest_bear_fvg_high=128)

    def test_three_support_and_three_resistance_areas_from_one_point(self):
        result=evaluate(100,self.features());areas=result['areas']
        self.assertEqual(len(areas['support']),3);self.assertEqual(len(areas['resistance']),3)
        self.assertEqual([a['high'] for a in areas['support']],[94,84,74])
        self.assertEqual([a['low'] for a in areas['resistance']],[106,116,126])
        for a in areas['resistance']:
            self.assertGreater(a['outcomes']['BUY']['net_low'],0)
            self.assertLess(a['outcomes']['SELL']['net_high'],0)
        for a in areas['support']:
            self.assertGreater(a['outcomes']['SELL']['net_low'],0)
            self.assertLess(a['outcomes']['BUY']['net_high'],0)

    def test_directional_fvg_features_do_not_enter_the_wrong_side(self):
        result=evaluate(100,dict(atr=1,nearest_bull_fvg_low=110,nearest_bull_fvg_high=112,
                                nearest_bear_fvg_low=88,nearest_bear_fvg_high=90))
        self.assertEqual(result['areas'],{'support':[],'resistance':[]})

    def test_a_missing_risk_model_does_not_erase_known_areas(self):
        result=evaluate(1,dict(atr=10,protected_high=30))
        self.assertEqual(len(result['areas']['resistance']),1)
        self.assertIsNone(result['buy']['invalidation'])
