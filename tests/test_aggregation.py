"""Horizon budgets, disagreement, stale/partial input and causal publication."""
import copy
import json
import unittest
from Section_5_Market_Regime.aggregation import evaluate
from Section_5_Market_Regime.aggregation_config import AggregationConfig


def snapshot(states=None):
    states=states or {'1m':'BEARISH','5m':'BEARISH','4h':'BULLISH','1d':'BULLISH'}
    identity=dict(venue='binance',market_type='spot',instrument_id='BTCUSDT',symbol='BTCUSDT',dataset_generation='symbol-generation')
    slots=[];at=1000000000
    for tf,direction in states.items():
        duration={'1m':60000,'5m':300000,'4h':14400000,'1d':86400000}.get(tf,120000)
        version=dict(engine_version='1.0.0',config_hash='cfg',input_signature='source-'+tf)
        result=dict(contract_version='1.0.0',engine='TREND',identity=dict(identity,timeframe=tf,dataset_generation='data-'+tf),**version,
            mode='CONFIRMED',candle_open_time=at-duration,candle_close_time=at-1,as_of=at,available_at=at,classification=dict(direction=direction,strength_band='STRONG'),coverage=1.,confidence=.8,data_quality='VALID',confirmation=dict(status='CONFIRMED'),provenance=dict(mode='SIMULATION'))
        slots.append(dict(timeframe=tf,active=True,duration_ms=duration,result=result,result_ref=tf+'-row',reason=None,expected=dict(version,dataset_generation='data-'+tf),fresh_until=at+duration+30000))
    return dict(identity=identity,engine='TREND',as_of=at,computed_at=at,timeframes=slots,producer_generation='code')


class Aggregation(unittest.TestCase):
    def test_countertrend_is_not_outvoted_by_small_timeframes(self):
        s=snapshot();r=evaluate(s)
        self.assertEqual(r['alignment'],'CONFLICTED')
        self.assertAlmostEqual(r['weights']['1m'],1/6);self.assertAlmostEqual(r['weights']['1d'],1/3)
        self.assertEqual(r['horizons']['short']['dimensions']['direction']['state'],'BEARISH')
        self.assertEqual(r['horizons']['long']['dimensions']['direction']['state'],'BULLISH')
        self.assertTrue(any(c['type']=='COUNTERTREND' and c['shorter_timeframe']=='1m' and c['longer_timeframe']=='1d' for c in r['conflicts']))
        self.assertNotIn('overall_direction',r)

    def test_missing_and_partial_sources_keep_full_budget(self):
        s=snapshot();s['timeframes'][-1].update(result=None,reason='MISSING')
        r=evaluate(s);self.assertAlmostEqual(r['coverage'],2/3,places=7)
        s=snapshot({'1m':'BULLISH','5m':'BULLISH'})
        for slot in s['timeframes']:slot['result'].update(coverage=.4,confidence=.4)
        r=evaluate(s);self.assertEqual(r['alignment'],'UNKNOWN');self.assertEqual(r['coverage'],.4)
        self.assertEqual(r['horizons']['short']['dimensions']['direction']['state'],'UNKNOWN')

    def test_future_stale_invalid_quality_config_and_preview_rejected(self):
        for mutate in (
            lambda t:t['result'].update(available_at=10**12),lambda t:t.update(fresh_until=1),
            lambda t:t['result'].update(mode='PROVISIONAL'),lambda t:t['result'].update(data_quality='GAP'),
            lambda t:t['result'].update(input_signature='wrong'),
        ):
            s=snapshot();mutate(s['timeframes'][0]);r=evaluate(s)
            self.assertIsNotNone(r['timeframes']['1m']['reason']);self.assertNotIn('1m-row',r['result_refs'])
        s=snapshot();t=s['timeframes'][0];t['result']['config_hash']='other';t['expected']['config_hash']='other'
        r=evaluate(s);self.assertEqual(r['coverage'],0.);self.assertEqual(r['alignment'],'UNKNOWN')

    def test_regime_dimensions_and_unknown_do_not_turn_neutral(self):
        s=snapshot({'1m':'BULLISH','5m':'BULLISH'});s['engine']='REGIME'
        for t in s['timeframes']:
            t['result']['engine']='REGIME';t['result']['classification']=dict(primary='TRENDING',direction='BULLISH',volatility_level='HIGH')
        s['timeframes'][0]['result']['classification']['volatility_level']='LOW'
        r=evaluate(s);self.assertEqual(r['alignment'],'PARTIALLY_ALIGNED')
        self.assertEqual(r['horizons']['short']['dimensions']['direction']['state'],'BULLISH')
        for t in s['timeframes']:t['result']['classification']=dict(direction='UNKNOWN')
        r=evaluate(s);self.assertEqual(r['alignment'],'UNKNOWN');self.assertFalse(r['conflicts'])

    def test_disabled_scopes_new_timeframes_and_simulation_are_explicit(self):
        s=snapshot({'1m':'BULLISH','5m':'BULLISH','7m':'BULLISH'});s['timeframes'][0]['active']=False
        r=evaluate(s);self.assertEqual(r['alignment'],'ALIGNED');self.assertNotIn('1m',r['weights'])
        for t in s['timeframes']:t['result']['available_at']=s['as_of']+1000
        self.assertEqual(evaluate(s)['alignment'],'UNKNOWN')
        r=evaluate(s,AggregationConfig(availability='RECONSTRUCTED_CLOSE'))
        self.assertEqual(r['alignment'],'ALIGNED');self.assertIn('SIMULATED_CLOSE_AVAILABILITY_NOT_ORIGINAL_PUBLICATION',r['quality_flags'])

    def test_pure_reproducible_input_unchanged_and_temporal_signature(self):
        s=snapshot({'1m':'BULLISH','5m':'BULLISH'});old=copy.deepcopy(s);r=evaluate(s)
        self.assertEqual(s,old);self.assertEqual(r,evaluate(json.loads(json.dumps(s))))
        s['as_of']+=100;s['computed_at']+=100
        self.assertEqual(r['input_signature'],evaluate(s)['input_signature'])
        s['as_of']+=100000;s['computed_at']+=100000
        self.assertNotEqual(r['input_signature'],evaluate(s)['input_signature'])
        with self.assertRaises(ValueError):AggregationConfig(timeframe_weights=(('1m',0),))
