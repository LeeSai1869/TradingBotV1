"""Momentum sign/magnitude separation, confirmed anchors, and no hindsight."""
import copy
import json
from pathlib import Path
import unittest
from test_regime_engine import snapshot as base
from Section_5_Market_Regime.engines import momentum
from Section_5_Market_Regime.engines.momentum_config import MomentumConfig


def snapshot(i,**changes):
    s=base(i);f=dict(rsi=70.,di_signed_dominance=.5,roc_pct=1.,momentum_atr=2.,momentum_atr_change=.1,momentum_strength_change=.1,macd_histogram=.2,atr=2.,di_anchor_events='[]',di_anchor_continuous=True,bull_momentum_divergence=False,bear_momentum_divergence=False,
        di_price_high_time=0,di_price_high_known_time=60000,di_signed_spread_from_price_high=2.,di_price_low_time=0,di_price_low_known_time=60000,di_signed_spread_from_price_low=5.,measurement_gap=False,measurement_version='shared-v1',measurement_config_id='shared')
    f.update(changes);s.update(features=f,units=momentum.UNITS.copy(),field_validity={k:'VALID' if v is not None else 'UNAVAILABLE' for k,v in f.items()},field_available_at={k:s['as_of'] for k in f},feature_parameters=dict(measurementMomentumLength=10))
    return s

class MomentumEngine(unittest.TestCase):
    def confirm(self,**changes):
        state=None
        for i in range(3):result,state=momentum.evaluate(snapshot(i,**changes),previous_state=state)
        return result,state

    def test_bullish_and_bearish_acceleration_are_strength_increases(self):
        result,_=self.confirm();self.assertEqual(result['classification']['condition'],'BUILDING');self.assertEqual(result['classification']['direction'],'BULLISH')
        result,_=self.confirm(rsi=30,di_signed_dominance=-.5,roc_pct=-1,momentum_atr=-2,momentum_atr_change=-.2,momentum_strength_change=.2,di_signed_spread_from_price_high=-5,di_signed_spread_from_price_low=-2)
        self.assertEqual(result['classification']['direction'],'BEARISH');self.assertEqual(result['classification']['acceleration'],'ACCELERATING')
        self.assertEqual(result['classification']['condition'],'BUILDING')
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'Section_5_Market_Regime/contracts/result.schema.json').read_text());jsonschema.Draft202012Validator(schema).validate(result)

    def test_exhaustion_needs_persistence_and_corroboration(self):
        _,state=self.confirm()
        for i in range(3,7):result,state=momentum.evaluate(snapshot(i,momentum_strength_change=-.1),previous_state=state)
        self.assertEqual(result['classification']['condition'],'WEAKENING')
        event=dict(type='di_high',channel='di_plus',value=35.,time=6*60000,confirmed_time=8*60000,qualified=True)
        result,state=momentum.evaluate(snapshot(7,momentum_strength_change=-.1,di_anchor_events=json.dumps([event])),previous_state=state)
        self.assertEqual(result['classification']['condition'],'EXHAUSTING')
        self.assertEqual(result['measurements']['admitted_di_turns'][0]['time'],6*60000)
        for i in range(8,14):result,state=momentum.evaluate(snapshot(i,momentum_strength_change=-.1),previous_state=state)
        self.assertEqual(result['classification']['condition'],'WEAKENING')

    def test_future_anchor_does_not_get_counted_and_missing_is_not_neutral(self):
        result,_=self.confirm(di_price_high_known_time=999999999,di_price_low_known_time=None)
        self.assertEqual(result['coverage'],.85);self.assertIn('ANCHOR_UNAVAILABLE:high',result['quality_flags'])
        self.assertEqual(result['data_quality'],'PARTIAL')
        result,_=self.confirm(momentum_strength_change=None);self.assertEqual(result['classification']['acceleration'],'UNKNOWN')
        result,_=self.confirm(rsi=None);self.assertEqual(result['classification']['direction'],'UNKNOWN')

    def test_preview_restart_gap_and_enabled_missing_macd(self):
        _,state=self.confirm();old=copy.deepcopy(state);snap=snapshot(3);snap['closed']=False
        result,returned=momentum.evaluate(snap,previous_state=state);self.assertEqual(returned,old);self.assertEqual(state,old)
        one,state=momentum.evaluate(snapshot(3),previous_state=state);two,_=momentum.evaluate(snapshot(3),previous_state=json.loads(json.dumps(old)));self.assertEqual(one,two)
        result,state=momentum.evaluate(snapshot(5),previous_state=state);self.assertEqual(result['data_quality'],'GAP');self.assertEqual(result['classification']['direction'],'UNKNOWN')
        result,_=momentum.evaluate(snapshot(0,macd_histogram=None),MomentumConfig(use_macd=True));self.assertIsNone(result['strength']);self.assertLess(result['coverage'],1)
        with self.assertRaises(ValueError):MomentumConfig(use_macd='yes')

    def test_flat_price_cannot_get_direction_from_oscillators_or_anchors_alone(self):
        result,_=self.confirm(momentum_atr=0.,roc_pct=0.,rsi=90.,di_signed_dominance=1.,di_signed_spread_from_price_high=20.,di_signed_spread_from_price_low=20.)
        self.assertEqual(result['classification']['direction'],'NEUTRAL');self.assertEqual(result['classification']['condition'],'UNKNOWN')

    def test_malformed_anchor_batch_is_atomic_and_future_turns_do_not_corroborate(self):
        _,state=self.confirm()
        event=dict(type='di_high',channel='di_plus',value=35.,time=120000,confirmed_time=240000,qualified=True)
        future={**event,'confirmed_time':999999999}
        result,state=momentum.evaluate(snapshot(3,di_anchor_events=json.dumps([event,future])),previous_state=state)
        self.assertEqual(result['measurements']['admitted_di_turns'],[]);self.assertIsNone(state['corroboration']['BULLISH'])
        self.assertIn('INVALID_DI_ANCHOR_EVENTS',result['quality_flags'])

    def test_missing_zero_gap_and_identity_do_not_leak_state(self):
        _,state=self.confirm()
        with self.assertRaises(ValueError):momentum.evaluate(snapshot(2),previous_state=state)
        snap=snapshot(3);snap['identity']['market_type']='usdt_perpetual'
        with self.assertRaises(ValueError):momentum.evaluate(snap,previous_state=state)
        result,state=momentum.evaluate(snapshot(3,momentum_atr=None),previous_state=state)
        self.assertEqual(result['classification']['direction'],'UNKNOWN');self.assertIsNone(result['strength'])
        result,_=momentum.evaluate(snapshot(0,momentum_strength_change=0.));self.assertEqual(result['candidate_classification']['acceleration'],'STABLE')

    def test_di_stream_discontinuity_clears_retained_turn_corroboration(self):
        _,state=self.confirm()
        event=dict(type='di_high',channel='di_plus',value=35.,time=120000,confirmed_time=240000,qualified=True)
        _,state=momentum.evaluate(snapshot(3,momentum_strength_change=-.1,di_anchor_events=json.dumps([event])),previous_state=state)
        self.assertIsNotNone(state['corroboration']['BULLISH'])
        result,state=momentum.evaluate(snapshot(4,momentum_strength_change=-.1,di_anchor_continuous=False),previous_state=state)
        self.assertIsNone(state['corroboration']['BULLISH']);self.assertIn('DI_ANCHOR_CONTINUITY_UNAVAILABLE',result['quality_flags'])
        result,state=momentum.evaluate(snapshot(5,momentum_strength_change=-.1),previous_state=state)
        self.assertEqual(result['classification']['condition'],'WEAKENING')
