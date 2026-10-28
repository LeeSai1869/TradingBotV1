import unittest
from Section_10_Opportunity_Engine.engine import evaluate


class BandTests(unittest.TestCase):
    def test_overlap_corroboration_never_expands_native_core(self):
        f=dict(atr=2,resistance_zone_low=105,resistance_zone_high=105.4,
            nearest_bear_fvg_low=105.1,nearest_bear_fvg_high=105.6,
            active_bear_ob_low=105.2,active_bear_ob_high=105.7)
        bands=evaluate(100,f)['buy']['targets']
        self.assertEqual(len(bands),1)
        self.assertEqual((bands[0]['low'],bands[0]['high']),(105,105.4))
        self.assertEqual(set(bands[0]['families']),{'sr','fvg','ob'})

    def test_close_point_references_are_bands_not_three_congested_lines(self):
        f=dict(atr=.0074,nearest_fib_price=.2364948,vwap=.23189008,ema50=.22851471)
        bands=evaluate(.2375,f)['sell']['targets']
        self.assertEqual(len(bands),3)
        self.assertTrue(all(bands[i+1]['high']<bands[i]['low'] for i in range(2)))
        self.assertTrue(all(b['low']<b['high']<.2375 for b in bands))
        self.assertTrue(all(b['net_reward_far_pct']>b['net_reward_pct'] for b in bands))
        self.assertTrue(all(b['modeled'] for b in bands))

    def test_opposing_area_is_distinct_from_the_invalidation_rule(self):
        result=evaluate(100,dict(atr=1,support_zone_low=95,support_zone_high=95.4,resistance_zone_low=104,resistance_zone_high=104.4))
        self.assertEqual(result['sell']['opposing_band']['low'],104)
        self.assertEqual(result['buy']['opposing_band']['high'],95.4)
        self.assertGreater(result['sell']['invalidation'],result['sell']['risk_band']['high'])

    def test_missing_known_levels_are_not_filled_to_force_three_areas(self):
        result=evaluate(100,dict(atr=1,protected_high=110))
        self.assertEqual(len(result['buy']['targets']),1)
        self.assertTrue(result['buy']['targets'][0]['modeled'])
        self.assertEqual(result['sell']['targets'],[])

class SixAreaTests(unittest.TestCase):
    @staticmethod
    def features():
        return dict(formula_version=3,atr=1,support_zone_low=93.6,support_zone_high=94,
            inst_support_zone_low=83.6,inst_support_zone_high=84,nearest_bull_fvg_low=73.6,nearest_bull_fvg_high=74,
            resistance_zone_low=106,resistance_zone_high=106.4,inst_resistance_zone_low=116,inst_resistance_zone_high=116.4,
            nearest_bear_fvg_low=126,nearest_bear_fvg_high=126.4)

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

class GeometryAuditTests(unittest.TestCase):
    def test_every_scalar_input_uses_the_actual_feature_schema(self):
        from Section_10_Opportunity_Engine.engine import FIELDS
        from Section_1_Global_Core.memory_storage.Storage.features_store import COLUMNS
        self.assertFalse(set(FIELDS)-set(COLUMNS))

    def test_huge_native_bounds_remain_json_safe(self):
        import json
        result=evaluate(1e-300,dict(atr=1,resistance_zone_low=1,resistance_zone_high=1e300))
        json.dumps(result,allow_nan=False)


    def test_unbounded_overlap_chain_is_context_not_an_enlarged_entry(self):
        result=evaluate(100,dict(atr=1,resistance_zone_low=105,resistance_zone_high=108,
            nearest_bear_fvg_low=107,nearest_bear_fvg_high=110))
        self.assertEqual(result['areas']['resistance'],[])
        self.assertEqual([(z['low'],z['high']) for z in result['context_zones']],[(105,108),(107,110)])
        self.assertTrue(all(a['reason']=='broad_context_only' for a in result['audit']))

    def test_daily_atr_cannot_discard_nearby_support_or_inflate_points(self):
        result=evaluate(.18,dict(atr=.04,protected_low=.1748,nearest_swing_low=.173,vwap=.13))
        areas=result['areas']['support']
        self.assertEqual(len(areas),3)
        self.assertLess(areas[0]['low'],.1748);self.assertGreater(areas[0]['high'],.1748)
        self.assertTrue(all(a['high']-a['low']<=.001*.18+1e-12 for a in areas))

    def test_same_family_is_never_counted_twice_in_a_core(self):
        areas=evaluate(100,dict(atr=1,active_bear_ob_low=105,active_bear_ob_high=105.2,
            active_strict_bear_ob_low=105.01,active_strict_bear_ob_high=105.21))['areas']['resistance']
        for area in areas:
            self.assertEqual(len(area['contributors']),len(area['families']))

    def test_straddling_zone_is_reported_at_entry(self):
        result=evaluate(100,dict(atr=1,support_zone_low=99.9,support_zone_high=100.1))
        self.assertEqual(len(result['at_entry']),1)
        self.assertEqual(result['areas'],dict(support=[],resistance=[]))

    def test_future_inventory_is_rejected_and_extra_known_zone_is_used(self):
        zones=[dict(id='old',family='sr',low=94,high=94.2,available_ms=1),
               dict(id='future',family='sr',low=96,high=96.2,available_ms=3)]
        result=evaluate(100,dict(atr=1),zones=zones,as_of_ms=2,timeframe='1d')
        self.assertEqual(result['areas']['support'][0]['low'],94)
        self.assertTrue(any(a['reason']=='not_available_at_reference' for a in result['audit']))

    def test_mirrored_geometry_is_symmetric(self):
        upper=evaluate(100,dict(atr=2,protected_high=102,ema50=103))['areas']['resistance']
        lower=evaluate(100,dict(atr=2,protected_low=98,ema50=97))['areas']['support']
        self.assertEqual([(a['low'],a['high']) for a in upper],[(200-a['high'],200-a['low']) for a in lower])
