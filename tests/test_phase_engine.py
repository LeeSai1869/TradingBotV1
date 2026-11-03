"""Ordered cycle hypotheses: freeze geometry, retain knowledge times, no hindsight."""
import copy
import json
from pathlib import Path
import unittest
from test_regime_engine import snapshot as base
from Section_5_Market_Regime.engines import phase
from Section_5_Market_Regime.engines.phase_config import PhaseConfig

CFG = PhaseConfig(preceding_bars=2, range_min_bars=2, evidence_bars=2, breakout_bars=2)


def snapshot(i, direction='BULLISH', *, events=None, candle=None, changes=None, activity='HIGH', price_confirmation='CONFIRMING'):
    s = base(i)
    f = dict(range_high=110., range_low=100., atr=2., efficiency_ratio=.2,
             natr_change_fraction=-.1, bb_width_change_fraction=-.1,
             measurement_contiguous_bars=1000, measurement_gap=False,
             measurement_version='shared-v1', measurement_config_id='shared')
    f.update(changes or {})
    s.update(features=f, units=phase.UNITS.copy(), field_validity={k:'VALID' if v is not None else 'UNAVAILABLE' for k,v in f.items()},
             field_available_at={k:s['as_of'] for k in f}, feature_parameters=dict(rangeLookback=100, measurementERLength=20, measurementChangeLength=5),
             market_metadata=dict(calendar='24/7 UTC'), dependencies={}, dependency_expectations={}, dependency_refs={})
    s['candle'] = candle or dict(open=104., high=107., low=102., close=105.)
    for name, version in phase.DEPENDENCIES.items():
        classification = (dict(direction=direction, condition='ESTABLISHED' if direction!='NEUTRAL' else 'UNCONFIRMED') if name=='TREND'
                          else dict(direction=direction, condition='BROKEN' if events else 'CONFIRMED', active_structure='RANGE' if direction=='NEUTRAL' else 'HH_HL' if direction=='BULLISH' else 'LH_LL') if name=='STRUCTURE'
                          else dict(activity=activity, confirmation=price_confirmation, dominance='UNKNOWN', participation='INCREASING'))
        dep = dict(engine=name, engine_version=version, identity=copy.deepcopy(s['identity']), mode='CONFIRMED',
                   candle_open_time=s['candle_open_time'], candle_close_time=s['candle_close_time'], as_of=s['as_of'], available_at=s['as_of'],
                   classification=classification, coverage=.75 if name=='PARTICIPATION' else 1., data_quality='PARTIAL' if name=='PARTICIPATION' else 'VALID',
                   config_hash=name+'-config', input_signature=name+'-source', provenance=dict(mode='SIMULATION'), confirmation=dict(status='CONFIRMED'))
        if name=='STRUCTURE': dep['measurements']=dict(new_events=events or [])
        s['dependencies'][name]=dep
        s['dependency_expectations'][name]={k:dep[k] for k in ('engine_version','config_hash','input_signature')}
        s['dependency_refs'][name]=name+'-run:'+str(i)
    return s


def structural(i, kind='BOS', *, direction='bullish', origin=2*60000, classification=None, price=None):
    e = dict(id=str(i)+kind+direction, type=kind, source_version='structure-events-v1', origin_time=origin,
             known_time=(i+1)*60000, confirmation_time=i*60000, source_type=direction+'BOS')
    if classification: e['classification']=classification
    if price: e['price']=price
    return e


def demand(): return dict(open=101., high=106., low=99., close=105.)
def supply(): return dict(open=109., high=111., low=104., close=105.)


class PhaseEngine(unittest.TestCase):
    def setup_hypothesis(self, prior='BULLISH', side='demand'):
        state=None; results=[]
        for i in range(5):
            s=snapshot(i, prior if i<2 else 'NEUTRAL', candle=(demand() if side=='demand' else supply()) if i>=3 else None)
            result,state=phase.evaluate(s,CFG,state);results.append(result)
        return results,state

    def test_trend_range_evidence_sequence_and_four_hypotheses(self):
        for prior,side,label in (('BULLISH','demand','REACCUMULATION'),('BEARISH','demand','ACCUMULATION'),('BULLISH','supply','DISTRIBUTION'),('BEARISH','supply','REDISTRIBUTION')):
            results,state=self.setup_hypothesis(prior,side)
            self.assertEqual(results[1]['classification']['phase'],'MARKUP' if prior=='BULLISH' else 'MARKDOWN')
            self.assertEqual(results[2]['classification']['phase'],'TRANSITION')
            self.assertEqual(results[3]['classification']['phase'],'TRANSITION')
            self.assertEqual(results[4]['classification'],dict(phase=label,development='DEVELOPING',preceding_trend=prior))
            self.assertEqual(len(state['range'][side]),2)
            self.assertEqual(results[4]['confirmation']['status'],'PENDING')
            self.assertLessEqual(results[4]['confidence'],results[4]['coverage'])
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'Section_5_Market_Regime/contracts/result.schema.json').read_text())
        jsonschema.Draft202012Validator(schema).validate(results[-1])

    def test_sideways_without_prior_or_evidence_is_not_accumulation(self):
        state=None
        for i in range(8):
            result,state=phase.evaluate(snapshot(i,'NEUTRAL',candle=demand()),CFG,state)
            self.assertEqual(result['classification']['phase'],'TRANSITION')
        self.assertIn('PRECEDING_TREND_UNAVAILABLE',result['quality_flags'])
        state=None
        for i in range(8):
            result,state=phase.evaluate(snapshot(i,'BEARISH' if i<2 else 'NEUTRAL'),CFG,state)
        self.assertEqual(result['classification']['phase'],'TRANSITION')

    def test_frozen_geometry_breakout_causal_confirmation_not_backdated(self):
        results,state=self.setup_hypothesis();original=copy.deepcopy(results)
        for i in (5,6):
            s=snapshot(i,events=[structural(i)] if i==5 else [],candle=dict(open=111.,high=114.,low=110.,close=113.),changes=dict(range_high=120.,range_low=90.,atr=4.))
            result,state=phase.evaluate(s,CFG,state)
            self.assertEqual(state['range']['high'],110.);self.assertEqual(state['range']['low'],100.)
            self.assertEqual(result['classification']['development'],'DEVELOPING' if i==5 else 'CONFIRMED')
        self.assertEqual(results,original)
        event=next(e for e in result['measurements']['new_events'] if e['type']=='PHASE_CONFIRMED')
        self.assertEqual(event['origin_time'],6*60000);self.assertEqual(event['known_time'],7*60000)
        self.assertEqual(event['range_origin_time'],2*60000)
        result,state=phase.evaluate(snapshot(7),CFG,state)
        self.assertFalse(any(e['type']=='PHASE_CONFIRMED' for e in result['measurements']['new_events']))

    def test_no_structure_proof_old_event_and_wrong_side_cannot_confirm(self):
        for event in (None,structural(5,origin=0),structural(5,direction='bearish')):
            _,state=self.setup_hypothesis()
            for i in (5,6,7):
                result,state=phase.evaluate(snapshot(i,events=[event] if i==5 and event else [],candle=dict(open=111.,high=114.,low=110.,close=113.)),CFG,state)
            self.assertEqual(result['classification']['development'],'DEVELOPING')
            self.assertIn('STRUCTURAL_BREAK_CONFIRMATION_UNAVAILABLE',result['quality_flags'])

    def test_invalidation_and_failed_breakout_are_distinct(self):
        _,state=self.setup_hypothesis()
        result,state=phase.evaluate(snapshot(5,'BEARISH',candle=dict(open=100.,high=101.,low=97.,close=98.)),CFG,state)
        self.assertEqual(result['classification']['development'],'INVALIDATED')
        self.assertTrue(any(e['type']=='PHASE_INVALIDATED' for e in result['measurements']['new_events']))
        _,state=self.setup_hypothesis()
        _,state=phase.evaluate(snapshot(5,candle=dict(open=111.,high=114.,low=110.,close=113.)),CFG,state)
        result,state=phase.evaluate(snapshot(6,'NEUTRAL'),CFG,state)
        self.assertEqual(result['classification']['development'],'DEVELOPING')
        self.assertTrue(any(e['type']=='FAILED_BREAKOUT' for e in result['measurements']['new_events']))
        self.assertEqual(state['range']['breakout_count'],0)

    def test_pivots_must_originate_after_range_and_volume_is_not_aggressor(self):
        _,state=self.setup_hypothesis()
        # New clean sequence with no wick evidence, old pivots cannot seed demand.
        state=None
        for i in range(6):
            event=structural(i,'PIVOT_LOW',origin=60000,classification='HIGHER_LOW',price=102.) if i>=3 else None
            result,state=phase.evaluate(snapshot(i,'BULLISH' if i<2 else 'NEUTRAL',events=[event] if event else []),CFG,state)
        self.assertEqual(result['classification']['phase'],'TRANSITION')
        for i in (6,7):
            event=structural(i,'PIVOT_LOW',origin=(i-1)*60000,classification='HIGHER_LOW',price=102.)
            result,state=phase.evaluate(snapshot(i,'NEUTRAL',events=[event]),CFG,state)
        self.assertEqual(result['classification']['phase'],'REACCUMULATION')
        self.assertEqual(result['coverage'],.95)

    def test_missing_dependency_future_time_identity_and_config_rejection(self):
        for field,value in (('mode','PROVISIONAL'),('available_at',10**12),('engine_version','wrong'),('input_signature','wrong')):
            s=snapshot(0);s['dependencies']['TREND'][field]=value
            result,_=phase.evaluate(s,CFG);self.assertEqual(result['classification'],phase.UNKNOWN)
        s=snapshot(0);s['dependencies']['PARTICIPATION']['identity']['market_type']='usdt_perpetual'
        result,_=phase.evaluate(s,CFG);self.assertEqual(result['classification'],phase.UNKNOWN)
        s=snapshot(0);s['field_available_at']['measurement_version']=s['as_of']+1
        result,_=phase.evaluate(s,CFG);self.assertEqual(result['classification'],phase.UNKNOWN)
        with self.assertRaises(ValueError):PhaseConfig(range_max_bars=2)
        with self.assertRaises(ValueError):PhaseConfig(preceding_bars=True)

    def test_restart_preview_gap_prefix_and_zero_movement(self):
        _,state=self.setup_hypothesis();old=copy.deepcopy(state)
        s=snapshot(5,candle=dict(open=111.,high=114.,low=110.,close=113.));s['closed']=False
        preview,same=phase.evaluate(s,CFG,state)
        self.assertEqual(same,old);self.assertEqual(state,old);self.assertEqual(preview['measurements']['new_events'],[])
        a,first=phase.evaluate(snapshot(5,'NEUTRAL'),CFG,state)
        b,second=phase.evaluate(snapshot(5,'NEUTRAL'),CFG,json.loads(json.dumps(state)))
        self.assertEqual(a,b);self.assertEqual(first,second)
        gap,state=phase.evaluate(snapshot(7),CFG,first)
        self.assertEqual(gap['classification'],phase.UNKNOWN);self.assertEqual(gap['data_quality'],'GAP');self.assertIsNone(state['range'])
        result,_=phase.evaluate(snapshot(0,'NEUTRAL',changes=dict(atr=0.,range_high=100.,range_low=100.)),CFG)
        self.assertNotEqual(result['data_quality'],'INVALID');self.assertEqual(result['classification']['phase'],'TRANSITION')
        with self.assertRaises(ValueError):phase.evaluate(snapshot(7),CFG,state)
        json.dumps(a,allow_nan=False)

    def test_range_width_expiry_conflicting_evidence_and_stale_prior(self):
        _,state=self.setup_hypothesis()
        short=PhaseConfig(preceding_bars=2,range_min_bars=2,range_max_bars=3,evidence_bars=2,breakout_bars=2)
        state=None
        for i in range(6):
            result,state=phase.evaluate(snapshot(i,'BULLISH' if i<2 else 'NEUTRAL'),short,state)
        self.assertEqual(result['classification']['development'],'INVALIDATED')
        self.assertTrue(any(e['type']=='RANGE_EXPIRED' for e in result['measurements']['new_events']))
        wide=snapshot(0,'NEUTRAL',changes=dict(range_high=140.))
        result,state=phase.evaluate(wide,CFG)
        self.assertIsNone(state['range']);self.assertIn('RANGE_TOO_WIDE',result['quality_flags'])
        _,state=self.setup_hypothesis()
        for i in (5,6):result,state=phase.evaluate(snapshot(i,'NEUTRAL',candle=supply()),CFG,state)
        self.assertEqual(result['classification']['phase'],'TRANSITION')
        self.assertIsNone(state['range']['hypothesis'])
        # A distant old directional state is not evidence for a new range.
        cfg=PhaseConfig(preceding_bars=2,preceding_max_age=2,range_min_bars=2)
        state=None
        for i in range(6):
            result,state=phase.evaluate(snapshot(i,'BULLISH' if i<2 else 'NEUTRAL',changes=dict(efficiency_ratio=.8) if 2<=i<5 else None),cfg,state)
        self.assertIsNone(state['range']['prior'])

    def test_missingness_clears_sequence_and_rejects_future_pivot(self):
        _,state=self.setup_hypothesis();s=snapshot(5)
        del s['dependencies']['PARTICIPATION']
        result,state=phase.evaluate(s,CFG,state)
        self.assertEqual(result['classification'],phase.UNKNOWN);self.assertIsNone(state['range'])
        _,state=self.setup_hypothesis();s=snapshot(5,'NEUTRAL',events=[structural(5,'PIVOT_LOW',origin=9*60000,classification='HIGHER_LOW',price=102.)])
        result,state=phase.evaluate(s,CFG,state)
        self.assertIn('STRUCTURE_EVENT_REJECTED',result['quality_flags'])
        self.assertEqual(len(state['range']['demand']),2)
        s=snapshot(6);s['feature_parameters']['rangeLookback']=50
        result,state=phase.evaluate(s,CFG,state)
        self.assertEqual(result['classification'],phase.UNKNOWN);self.assertIsNone(state['range'])

    def test_ordinary_range_breakout_has_no_retrospective_cycle_story(self):
        state=None
        for i in range(2):
            result,state=phase.evaluate(snapshot(i,'NEUTRAL'),CFG,state)
        for i in (2,3):
            event=structural(i,origin=60000) if i==2 else None
            result,state=phase.evaluate(snapshot(i,events=[event] if event else [],candle=dict(open=111.,high=114.,low=110.,close=113.)),CFG,state)
        self.assertEqual(result['classification'],dict(phase='MARKUP',development='CONFIRMED',preceding_trend='UNKNOWN'))
        self.assertIsNone(state['range']['hypothesis'])
        self.assertTrue(any(e['type']=='RANGE_BREAKOUT_CONFIRMED' for e in result['measurements']['new_events']))
