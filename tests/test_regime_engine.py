"""Regime rules, independent dimensions, causal availability and state boundaries."""
import copy
import json
from pathlib import Path
import unittest
from Section_5_Market_Regime.config import RegimeConfig
from Section_5_Market_Regime.engines.regime import evaluate,UNITS,FIELDS


def snapshot(i,**changes):
    f=dict.fromkeys(FIELDS)
    f.update(adx=30.,di_plus=30.,di_minus=10.,di_signed_dominance=.5,efficiency_ratio=.6,
        natr_pct=2.,natr_percentile=80.,natr_baseline_count=500,natr_baseline_degenerate=False,
        bb_width_percentile=80.,natr_change_fraction=.1,bb_width_change_fraction=.1,
        zero_price_movement=False,directional_movement_zero=False,measurement_gap=False,
        measurement_contiguous_bars=1000,measurement_version='shared-v1',measurement_config_id='shared-config')
    f.update(changes)
    start=i*60000;end=(i+1)*60000-1
    return dict(identity=dict(venue='binance',market_type='spot',instrument_id='BTCUSDT',symbol='BTCUSDT',timeframe='1m',dataset_generation='generation1'),
        candle_open_time=start,candle_close_time=end,as_of=end+1,computed_at=end+10,closed=True,
        candle=dict(open=100.,high=102.,low=99.,close=101.),features=f,units=UNITS.copy(),
        field_validity={k:'VALID' if f[k] is not None else 'UNAVAILABLE' for k in FIELDS},
        field_available_at={k:end+1 for k in FIELDS},input_signature='source1',source_versions={'shared':'v1'},
        feature_parameters=dict(measurementERLength=20,measurementRankLength=500,measurementChangeLength=5),
        quality_flags=[],provenance_mode='SIMULATION')

class RegimeEngine(unittest.TestCase):
    def confirm(self,state=None,start=0,**changes):
        for i in range(start,start+3):result,state=evaluate(snapshot(i,**changes),previous_state=state)
        return result,state

    def test_three_candle_confirmation_hysteresis_and_range(self):
        state=None
        for i in range(3):
            result,state=evaluate(snapshot(i),previous_state=state)
            self.assertEqual(result['classification']['primary'],'UNKNOWN' if i<2 else 'TRENDING')
            self.assertEqual(result['confirmation']['candidate_bars'],i+1)
        result,state=evaluate(snapshot(3,adx=21,efficiency_ratio=.35,di_signed_dominance=.05),previous_state=state)
        self.assertEqual(result['classification']['primary'],'TRENDING');self.assertEqual(result['evidence'][0]['code'],'TREND_HOLD')
        result,state=self.confirm(state,4,adx=18,efficiency_ratio=.3,di_signed_dominance=.1)
        self.assertEqual(result['classification']['primary'],'RANGING');self.assertEqual(result['classification']['direction'],'NEUTRAL')
        result,state=self.confirm(state,7,di_signed_dominance=-.5)
        self.assertEqual(result['classification']['direction'],'BEARISH')

    def test_new_candidate_cancels_pending_and_transitional_deadband(self):
        result,state=self.confirm()
        _,state=evaluate(snapshot(3,adx=10,efficiency_ratio=.1,di_signed_dominance=0),previous_state=state)
        result,state=evaluate(snapshot(4),previous_state=state)
        self.assertEqual(result['confirmation']['status'],'CONFIRMED');self.assertIsNone(state['dimensions']['primary']['candidate'])
        result,state=self.confirm(state,5,adx=23,efficiency_ratio=.1,di_signed_dominance=.1)
        self.assertEqual(result['classification']['primary'],'TRANSITIONAL');self.assertEqual(result['classification']['direction'],'NEUTRAL')

    def test_dimensions_warm_independently_and_missing_is_not_zero(self):
        result,state=self.confirm(natr_percentile=None,natr_baseline_count=10)
        self.assertEqual(result['classification']['primary'],'TRENDING');self.assertEqual(result['classification']['volatility_level'],'UNKNOWN')
        self.assertEqual(result['coverage'],.8);self.assertEqual(result['data_quality'],'PARTIAL')
        result,state=evaluate(snapshot(3,di_plus=None),previous_state=state)
        self.assertEqual(result['classification']['primary'],'UNKNOWN');self.assertEqual(result['confirmation']['status'],'UNAVAILABLE')
        result,state=self.confirm(adx=0,di_plus=0,di_minus=0,di_signed_dominance=0,efficiency_ratio=0,natr_pct=0,natr_percentile=50,natr_baseline_degenerate=True,zero_price_movement=True,directional_movement_zero=True)
        self.assertEqual(result['classification']['primary'],'RANGING');self.assertEqual(result['classification']['volatility_level'],'EXTREMELY_LOW')
        self.assertIn('DIRECTIONAL_MOVEMENT_ZERO',result['quality_flags'])
        self.assertLessEqual(result['confidence'],result['coverage'])

    def test_volatility_bands_degeneracy_and_disagreement(self):
        for value,label in ((9.99,'EXTREMELY_LOW'),(10,'LOW'),(25,'NORMAL'),(75,'HIGH'),(90,'EXTREME')):
            result,_=self.confirm(natr_percentile=value);self.assertEqual(result['classification']['volatility_level'],label)
        result,_=self.confirm(natr_baseline_degenerate=True,natr_percentile=50)
        self.assertEqual(result['classification']['volatility_level'],'NORMAL');self.assertEqual(result['measurements']['evidence_contributions']['volatility_level'],.1)
        result,_=self.confirm(natr_change_fraction=-.1,bb_width_change_fraction=.1)
        self.assertEqual(result['classification']['volatility_change'],'UNKNOWN');self.assertIn('VOLATILITY_CHANGE_DISAGREEMENT',result['quality_flags'])
        result,_=self.confirm(natr_change_fraction=-.05,bb_width_change_fraction=-.05)
        self.assertEqual(result['classification']['volatility_change'],'CONTRACTING')

    def test_gap_resets_and_future_or_wrong_units_are_unavailable(self):
        _,state=self.confirm();result,state=evaluate(snapshot(4),previous_state=state)
        self.assertEqual(result['data_quality'],'GAP');self.assertEqual(result['classification']['primary'],'UNKNOWN')
        snap=snapshot(5);snap['field_available_at']['adx']=snap['as_of']+1
        result,state=evaluate(snap,previous_state=state);self.assertEqual(result['classification']['primary'],'UNKNOWN')
        self.assertIn('INPUT_NOT_AVAILABLE:adx',result['quality_flags'])
        snap=snapshot(6);snap['units']['natr_pct']='fraction';result,_=evaluate(snap,previous_state=state)
        self.assertEqual(result['classification']['volatility_level'],'UNKNOWN');self.assertEqual(result['data_quality'],'INVALID')

    def test_preview_restart_prefix_identity_and_json_contract(self):
        state=None;prior=[]
        for i in range(2):result,state=evaluate(snapshot(i),previous_state=state);prior.append(result)
        original=copy.deepcopy(state);snap=snapshot(2);snap['closed']=False
        preview,unchanged=evaluate(snap,previous_state=state)
        self.assertEqual(state,original);self.assertEqual(unchanged,original)
        self.assertEqual(preview['mode'],'PROVISIONAL');self.assertIsNone(preview['available_at']);self.assertEqual(preview['classification']['primary'],'UNKNOWN')
        restored=json.loads(json.dumps(state));expected,state=evaluate(snapshot(2),previous_state=state);actual,restored=evaluate(snapshot(2),previous_state=restored)
        self.assertEqual(expected,actual);self.assertEqual(state,restored)
        for change in ('identity','input_signature'):
            snap=snapshot(3)
            if change=='identity':snap['identity']['market_type']='usdt_perpetual'
            else:snap[change]='new'
            with self.assertRaises(ValueError):evaluate(snap,previous_state=state)
        with self.assertRaises(ValueError):evaluate(snapshot(2),previous_state=state)
        fresh=None
        for i in range(2):result,fresh=evaluate(snapshot(i),previous_state=fresh);self.assertEqual(prior[i],result)
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'Section_5_Market_Regime/contracts/result.schema.json').read_text())
        jsonschema.Draft202012Validator(schema).validate(expected);json.dumps(expected,allow_nan=False)

    def test_validation_and_inputs_are_not_mutated(self):
        with self.assertRaises(ValueError):RegimeConfig(adx_trend_hold=40)
        with self.assertRaises(ValueError):RegimeConfig(confirmation_bars=True)
        snap=snapshot(0);original=copy.deepcopy(snap);evaluate(snap);self.assertEqual(snap,original)
        snap['as_of']=0
        with self.assertRaises(ValueError):evaluate(snap)
        result,_=evaluate(snapshot(0,adx=float('nan')));self.assertIsNone(result['measurements']['adx']);json.dumps(result,allow_nan=False)

    def test_calendar_close_times_and_incompatible_window_configuration(self):
        from datetime import datetime,timezone
        times=[int(datetime(2026,m,1,tzinfo=timezone.utc).timestamp()*1000) for m in (1,2,3)]
        state=None
        for i in range(2):
            snap=snapshot(i);snap['identity']['timeframe']='1M'
            snap.update(candle_open_time=times[i],candle_close_time=times[i+1]-1,as_of=times[i+1],computed_at=times[i+1]+10)
            snap['field_available_at']={key:times[i+1] for key in FIELDS}
            result,state=evaluate(snap,previous_state=state)
            self.assertNotIn('CANDLE_GAP',result['quality_flags'])
        snap=snapshot(0);snap['feature_parameters']['measurementRankLength']=30
        result,_=evaluate(snap);self.assertEqual(result['classification']['primary'],'UNKNOWN')
        self.assertIn('INCOMPATIBLE_FEATURE_PARAMETERS',result['quality_flags'])

    def test_preview_different_candidate_does_not_inherit_pending_count(self):
        _,state=self.confirm(adx=10,efficiency_ratio=.1,di_signed_dominance=0)
        for i in (3,4):_,state=evaluate(snapshot(i),previous_state=state)
        snap=snapshot(5,di_signed_dominance=-.5);snap['closed']=False
        result,returned=evaluate(snap,previous_state=state)
        self.assertEqual(result['confirmation']['candidate_bars'],0)
        self.assertEqual(result['classification']['primary'],'RANGING');self.assertEqual(returned,state)

    def test_pure_import_does_not_load_core_or_feature_execution(self):
        import subprocess,sys
        code="""import sys
from Section_5_Market_Regime.engines.regime import evaluate
from Section_5_Market_Regime.engines.trend import evaluate as trend
from Section_5_Market_Regime.engines.momentum import evaluate as momentum
from Section_5_Market_Regime.engines.volatility import evaluate as volatility
from Section_5_Market_Regime.engines.participation import evaluate as participation
from Section_5_Market_Regime.engines.phase import evaluate as phase
from Section_5_Market_Regime.engines.liquidity import evaluate as liquidity
from Section_5_Market_Regime.engines.sentiment import evaluate as sentiment
from Section_5_Market_Regime.aggregation import evaluate as aggregate
assert not any(key.startswith(('Section_1_Global_Core','Section_4_Features')) for key in sys.modules)
from Section_5_Market_Regime import RegimePacket,create_regime_packet
assert callable(RegimePacket) and callable(create_regime_packet)
"""
        result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
