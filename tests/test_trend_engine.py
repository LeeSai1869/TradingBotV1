"""Trend directional interpretation and exact dependency/causality boundaries."""
import copy
import json
from pathlib import Path
import unittest
from test_regime_engine import snapshot as base
from Section_5_Market_Regime.engines import trend
from Section_5_Market_Regime.engines.trend_config import TrendConfig


def snapshot(i,structure='BULLISH',**changes):
    s=base(i);s['feature_parameters']=dict(measurementERLength=20,measurementSlopeLength=5,measurementReturnLength=20,**{'ema'+str(p)+'Len':p for p in (7,25,50,100,200)})
    f=dict(ema7=108.,ema25=106.,ema50=104.,ema100=102.,ema200=100.,ema50_slope_atr=.5,ema200_slope_atr=.5,
        adx=40.,di_signed_dominance=.7,efficiency_ratio=.8,positive_return_fraction=.8,negative_return_fraction=.1,flat_return_fraction=.1,
        measurement_gap=False,measurement_version='shared-v1',measurement_config_id='shared',measurement_contiguous_bars=1000)
    f.update(changes);s.update(features=f,units=trend.UNITS.copy(),field_validity={k:'VALID' if v is not None else 'UNAVAILABLE' for k,v in f.items()},field_available_at={k:s['as_of'] for k in f},candle=dict(open=109.,high=112.,low=108.,close=110.))
    if structure is not None:
        s['dependencies']={'STRUCTURE':dict(engine='STRUCTURE',engine_version='1.1.0',identity=copy.deepcopy(s['identity']),mode='CONFIRMED',candle_open_time=s['candle_open_time'],candle_close_time=s['candle_close_time'],as_of=s['as_of'],available_at=s['as_of'],classification=dict(direction=structure,condition='CONFIRMED'),coverage=1.,data_quality='VALID',config_hash='structure-config',input_signature='structure-source',provenance=dict(mode='SIMULATION'))}
        s['dependency_expectations']={'STRUCTURE':dict(engine_version='1.1.0',config_hash='structure-config',input_signature='structure-source')}
        s['dependency_refs']={'STRUCTURE':'stored-structure:'+str(i)}
    return s

class TrendEngine(unittest.TestCase):
    def confirm(self,**changes):
        state=None
        for i in range(3):result,state=trend.evaluate(snapshot(i,**changes),previous_state=state)
        return result,state

    def test_confirmation_capped_strength_and_structural_alignment(self):
        result,state=self.confirm()
        self.assertEqual(result['classification']['direction'],'BULLISH');self.assertEqual(result['classification']['condition'],'ESTABLISHED')
        self.assertEqual(result['classification']['structural_alignment'],'ALIGNED');self.assertEqual(result['coverage'],1)
        self.assertAlmostEqual(result['strength'],85.5)
        self.assertLessEqual(result['confidence'],1);self.assertEqual(result['provenance']['dependency_results'],['stored-structure:2'])
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'Section_5_Market_Regime/contracts/result.schema.json').read_text())
        jsonschema.Draft202012Validator(schema).validate(result)

    def test_structure_missing_is_not_neutral_or_conflict(self):
        result,_=self.confirm(structure=None)
        self.assertEqual(result['classification']['direction'],'BULLISH');self.assertEqual(result['classification']['structural_alignment'],'UNAVAILABLE');self.assertEqual(result['coverage'],.8)
        self.assertEqual(result['classification']['condition'],'DEVELOPING')
        neutral,_=self.confirm(structure='NEUTRAL');self.assertEqual(neutral['classification']['structural_alignment'],'NEUTRAL')
        opposite,_=self.confirm(structure='BEARISH');self.assertEqual(opposite['classification']['structural_alignment'],'CONFLICTED');self.assertEqual(opposite['classification']['condition'],'UNCONFIRMED')

    def test_weakening_does_not_immediately_reverse_direction_and_history_is_bounded(self):
        _,state=self.confirm()
        for i in range(3,20):
            value=max(.01,.5-(i-2)*.03)
            result,state=trend.evaluate(snapshot(i,ema50_slope_atr=value,ema200_slope_atr=value,adx=max(10,40-i),efficiency_ratio=.3),previous_state=state)
        self.assertEqual(result['classification']['direction'],'BULLISH');self.assertLessEqual(len(state['history']),6)
        self.assertIn(result['classification']['persistence'],('DECLINING','STABLE'))
        flat=snapshot(20,structure=None,ema7=100.,ema25=100.,ema50=100.,ema100=100.,ema200=100.,ema50_slope_atr=0.,ema200_slope_atr=0.,di_signed_dominance=-.2)
        flat['candle']=dict(open=100.,high=101.,low=99.,close=100.)
        result,state=trend.evaluate(flat,previous_state=state)
        self.assertEqual(result['classification']['direction'],'BULLISH');self.assertEqual(result['confirmation']['status'],'PENDING')

    def test_wrong_candle_market_version_and_future_dependency_are_rejected(self):
        for field,value in (('candle_open_time',999),('engine_version','0.1.0'),('available_at',999999999),('config_hash','wrong-config'),('input_signature','wrong-generation')):
            snap=snapshot(0);snap['dependencies']['STRUCTURE'][field]=value
            result,_=trend.evaluate(snap);self.assertEqual(result['classification']['structural_alignment'],'UNAVAILABLE');self.assertEqual(result['coverage'],.8)
        snap=snapshot(0);snap['dependencies']['STRUCTURE']['identity']['market_type']='usdt_perpetual'
        result,_=trend.evaluate(snap);self.assertIn('STRUCTURE_DEPENDENCY_REJECTED',result['quality_flags'])

    def test_preview_checkpoint_gap_and_missing_inputs(self):
        _,state=self.confirm();before=copy.deepcopy(state);snap=snapshot(3);snap['closed']=False
        preview,returned=trend.evaluate(snap,previous_state=state);self.assertEqual(returned,before);self.assertEqual(state,before)
        actual,state=trend.evaluate(snapshot(3),previous_state=state);restored=trend.evaluate(snapshot(3),previous_state=json.loads(json.dumps(before)))[0];self.assertEqual(actual,restored)
        missing,state=trend.evaluate(snapshot(4,ema50=None),previous_state=state);self.assertEqual(missing['classification']['direction'],'UNKNOWN')
        gap,state=trend.evaluate(snapshot(6),previous_state=state);self.assertEqual(gap['data_quality'],'GAP');self.assertEqual(gap['classification']['direction'],'UNKNOWN')
        with self.assertRaises(ValueError):TrendConfig(hold_deadband=.4)
        with self.assertRaises(ValueError):trend.evaluate(snapshot(6),previous_state=state)

    def test_hold_deadband_pullback_and_three_candle_bearish_reversal(self):
        _,state=self.confirm()
        hold=snapshot(3,structure=None,ema7=100.,ema25=100.,ema50=100.,ema100=100.,ema200=100.,di_signed_dominance=-.4)
        result,state=trend.evaluate(hold,previous_state=state)
        self.assertAlmostEqual(result['measurements']['direction_score'],.13)
        self.assertEqual(result['confirmation']['status'],'CONFIRMED');self.assertEqual(result['classification']['direction'],'BULLISH')
        for i in range(4,7):
            snap=snapshot(i,structure='BEARISH',ema7=92.,ema25=94.,ema50=96.,ema100=98.,ema200=100.,ema50_slope_atr=-.5,ema200_slope_atr=-.5,di_signed_dominance=-.7)
            snap['candle']=dict(open=91.,high=93.,low=88.,close=90.)
            result,state=trend.evaluate(snap,previous_state=state)
            self.assertEqual(result['classification']['direction'],'BEARISH' if i==6 else 'BULLISH')
            self.assertEqual(result['candidate_classification']['structural_alignment'],'ALIGNED')
            if i<6:self.assertEqual(result['classification']['structural_alignment'],'CONFLICTED')

    def test_exhaustion_retains_direction_and_seeded_ema_history_reduces_coverage(self):
        _,state=self.confirm()
        for i in range(3,10):
            result,state=trend.evaluate(snapshot(i,adx=48-4*i,efficiency_ratio=0.,positive_return_fraction=.5,negative_return_fraction=.5,flat_return_fraction=0.),previous_state=state)
        self.assertEqual(result['classification']['direction'],'BULLISH');self.assertEqual(result['classification']['condition'],'EXHAUSTING')
        fresh,_=trend.evaluate(snapshot(0,measurement_contiguous_bars=100))
        self.assertEqual(fresh['coverage'],.8);self.assertEqual(fresh['measurements']['ema_seed_fraction'],.5)
        self.assertIn('EMA_RECURSIVE_SEED_HISTORY',fresh['quality_flags'])

    def test_structure_alone_cannot_create_direction_in_a_flat_market(self):
        state=None
        for i in range(3):
            snap=snapshot(i,ema7=100.,ema25=100.,ema50=100.,ema100=100.,ema200=100.,ema50_slope_atr=0.,ema200_slope_atr=0.,adx=0.,di_signed_dominance=0.,efficiency_ratio=0.,positive_return_fraction=0.,negative_return_fraction=0.,flat_return_fraction=1.)
            snap['candle']=dict(open=100.,high=101.,low=99.,close=100.)
            result,state=trend.evaluate(snap,previous_state=state)
        self.assertEqual(result['classification']['direction'],'NEUTRAL');self.assertEqual(result['strength'],0.)
