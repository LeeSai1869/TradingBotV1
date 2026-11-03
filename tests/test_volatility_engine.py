"""Independent volatility dimensions, past-baseline shocks and causal state."""
import copy
import json
from pathlib import Path
import unittest
from test_regime_engine import snapshot as base
from Section_5_Market_Regime.engines import volatility
from Section_5_Market_Regime.engines.volatility_config import VolatilityConfig


def snapshot(i,**changes):
    s=base(i);f=dict(atr=2.,prev_atr=2.,prev_close=100.,candle_range=3.,natr_pct=2.,natr_percentile=80.,natr_baseline_count=500,natr_baseline_degenerate=False,
        bb_width_fraction=.05,bb_width_percentile=80.,bb_width_baseline_count=500,bb_width_baseline_degenerate=False,natr_change_fraction=.1,bb_width_change_fraction=.1,
        realized_volatility=.02,return_skewness=.2,zero_price_movement=False,measurement_contiguous_bars=1000,measurement_gap=False,measurement_version='shared-v1',measurement_config_id='shared')
    f.update(changes);s.update(features=f,units=volatility.UNITS.copy(),field_validity={k:'VALID' if v is not None else 'UNAVAILABLE' for k,v in f.items()},field_available_at={k:s['as_of'] for k in f},feature_parameters=dict(measurementRankLength=500,measurementChangeLength=5,measurementReturnLength=20,atrLen=10),market_metadata=dict(calendar='24/7 UTC'))
    return s

class VolatilityEngine(unittest.TestCase):
    def confirm(self,**changes):
        state=None
        for i in range(3):result,state=volatility.evaluate(snapshot(i,**changes),previous_state=state)
        return result,state

    def test_percentile_boundaries_are_not_shock_or_direction(self):
        for rank,label in ((9.9,'EXTREMELY_LOW'),(10,'LOW'),(25,'NORMAL'),(75,'HIGH'),(90,'EXTREME')):
            result,_=self.confirm(natr_percentile=rank,bb_width_percentile=rank)
            self.assertEqual(result['classification']['level'],label);self.assertEqual(result['classification']['shock'],'NONE')
            self.assertNotIn('direction',result['classification'])
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'Section_5_Market_Regime/contracts/result.schema.json').read_text());jsonschema.Draft202012Validator(schema).validate(result)

    def test_immediate_prior_atr_shock_and_deduplicated_event(self):
        # Current ATR may be elevated by the shock; prior ATR remains the baseline.
        snap=snapshot(0,atr=20.,prev_atr=1.,candle_range=6.)
        snap['candle']=dict(open=100.,high=104.,low=98.,close=101.)
        result,state=volatility.evaluate(snap)
        self.assertEqual(result['classification']['shock'],'EXTREME');self.assertEqual(result['measurements']['shock_range_or_gap_atr'],6.)
        self.assertEqual(len(result['measurements']['new_events']),1)
        again=snapshot(1,prev_atr=1.,candle_range=6.);again['candle']=snap['candle']
        result,state=volatility.evaluate(again,previous_state=state);self.assertEqual(result['measurements']['new_events'],[])
        gap=snapshot(2,prev_atr=1.,prev_close=90.,candle_range=3.)
        result,state=volatility.evaluate(gap,previous_state=state);self.assertEqual(result['classification']['shock'],'EXTREME')

    def test_direction_mirror_keeps_shock_and_skew_sign_is_not_a_vote(self):
        high=snapshot(0,prev_atr=1.,candle_range=3.);high['candle']=dict(open=110.,high=112.,low=109.,close=111.)
        low=snapshot(0,prev_atr=1.,candle_range=3.);low['candle']=dict(open=90.,high=91.,low=88.,close=89.)
        self.assertEqual(volatility.evaluate(high)[0]['classification']['shock'],volatility.evaluate(low)[0]['classification']['shock'])
        for skew in (-2.,2.):
            result,_=self.confirm(return_skewness=skew);self.assertEqual(result['classification']['distribution'],'SKEWED')

    def test_flat_without_percentile_history_and_zero_denominator_are_explicit(self):
        kwargs=dict(atr=0.,prev_atr=0.,candle_range=0.,natr_pct=0.,bb_width_fraction=0.,realized_volatility=0.,return_skewness=None,zero_price_movement=True,natr_percentile=None,bb_width_percentile=None,natr_baseline_count=0,bb_width_baseline_count=0,natr_baseline_degenerate=None,bb_width_baseline_degenerate=None,natr_change_fraction=None,bb_width_change_fraction=None)
        state=None
        for i in range(3):
            snap=snapshot(i,**kwargs);snap['candle']=dict(open=100.,high=100.,low=100.,close=100.)
            result,state=volatility.evaluate(snap,previous_state=state)
        self.assertEqual(result['classification'],dict(level='EXTREMELY_LOW',state='STABLE',distribution='UNKNOWN',shock='NONE'))
        self.assertEqual(result['strength'],0.);self.assertEqual(result['coverage'],.85)
        result,_=volatility.evaluate(snapshot(0,prev_atr=0.));self.assertEqual(result['classification']['shock'],'UNKNOWN');self.assertIn('ZERO_SHOCK_BASELINE',result['quality_flags'])

    def test_independent_warmup_change_conflict_and_degeneracy(self):
        result,_=self.confirm(natr_percentile=None,natr_baseline_count=10,bb_width_percentile=None,bb_width_baseline_count=10)
        self.assertEqual(result['classification']['level'],'UNKNOWN');self.assertEqual(result['classification']['state'],'EXPANDING');self.assertEqual(result['classification']['shock'],'NONE')
        result,_=self.confirm(natr_change_fraction=-.1,bb_width_change_fraction=.1)
        self.assertEqual(result['classification']['state'],'UNKNOWN');self.assertIn('VOLATILITY_CHANGE_DISAGREEMENT',result['quality_flags'])
        result,_=self.confirm(natr_percentile=50.,bb_width_percentile=50.,natr_baseline_degenerate=True,bb_width_baseline_degenerate=True)
        self.assertEqual(result['classification']['level'],'NORMAL');self.assertEqual(result['measurements']['evidence_contributions']['natr_level'],.15)

    def test_preview_restart_gap_future_units_and_window_validation(self):
        _,state=self.confirm();old=copy.deepcopy(state);snap=snapshot(3,prev_atr=1.,candle_range=6.);snap['closed']=False
        preview,returned=volatility.evaluate(snap,previous_state=state);self.assertEqual(returned,old);self.assertEqual(preview['measurements']['new_events'],[])
        first,state=volatility.evaluate(snapshot(3),previous_state=state);second,_=volatility.evaluate(snapshot(3),previous_state=json.loads(json.dumps(old)));self.assertEqual(first,second)
        result,state=volatility.evaluate(snapshot(5),previous_state=state);self.assertEqual(result['data_quality'],'GAP');self.assertEqual(result['classification'],volatility.UNKNOWN)
        snap=snapshot(6);snap['field_available_at']['prev_atr']=snap['as_of']+1
        result,_=volatility.evaluate(snap,previous_state=state);self.assertEqual(result['classification']['shock'],'UNKNOWN')
        with self.assertRaises(ValueError):VolatilityConfig(moderate_shock_atr=6.)
        with self.assertRaises(ValueError):volatility.evaluate(snapshot(5),previous_state=state)

    def test_shock_boundaries_and_fresh_contiguous_baseline(self):
        for ratio,label in ((2.99,'NONE'),(3.,'MODERATE'),(5.,'EXTREME')):
            snap=snapshot(0,prev_atr=1.,candle_range=ratio)
            snap['candle']=dict(open=100.,high=100+ratio/2,low=100-ratio/2,close=100.)
            result,_=volatility.evaluate(snap);self.assertEqual(result['classification']['shock'],label)
        result,_=volatility.evaluate(snapshot(0,measurement_contiguous_bars=2,prev_atr=.1,candle_range=10.))
        self.assertEqual(result['classification']['shock'],'UNKNOWN');self.assertIn('SHOCK_BASELINE_WARMUP',result['quality_flags'])

    def test_calendar_month_continuity_and_unsupported_sessions(self):
        from datetime import datetime,timezone
        times=[int(datetime(2026,m,1,tzinfo=timezone.utc).timestamp()*1000) for m in (1,2,3)]
        state=None
        for i in range(2):
            snap=snapshot(i);snap['identity']['timeframe']='1M'
            snap.update(candle_open_time=times[i],candle_close_time=times[i+1]-1,as_of=times[i+1],computed_at=times[i+1]+10)
            snap['field_available_at']={key:times[i+1] for key in volatility.FIELDS}
            result,state=volatility.evaluate(snap,previous_state=state);self.assertNotIn('CANDLE_GAP',result['quality_flags'])
        snap=snapshot(0);snap['market_metadata']['calendar']='NYSE'
        result,_=volatility.evaluate(snap);self.assertEqual(result['classification'],volatility.UNKNOWN)
        self.assertIn('UNSUPPORTED_MARKET_CALENDAR',result['quality_flags'])
