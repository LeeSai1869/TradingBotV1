"""Capped directional families, context/risk separation and closed output lineage."""
import copy
import json
from pathlib import Path
import unittest
from test_regime_engine import snapshot as base
from Section_5_Market_Regime.engines import bias


def snapshot(i):
    s=base(i);s.update(features=dict(measurement_gap=False,measurement_version='shared-v1',measurement_config_id='shared'),units=bias.UNITS.copy(),dependencies={},dependency_expectations={},dependency_refs={})
    s['field_available_at']={k:s['as_of'] for k in bias.FIELDS};s['field_validity']={k:'VALID' for k in bias.FIELDS}
    classifications=dict(REGIME=dict(primary='TRENDING',direction='BEARISH',stability='STABLE'),TREND=dict(direction='BULLISH',condition='ESTABLISHED'),STRUCTURE=dict(direction='BULLISH',condition='CONFIRMED'),MOMENTUM=dict(direction='BULLISH',condition='SUSTAINING'),
        VOLATILITY=dict(level='NORMAL',state='STABLE',shock='NONE'),PHASE=dict(phase='TRANSITION',development='DEVELOPING'),PARTICIPATION=dict(activity='NORMAL',dominance='UNKNOWN'),LIQUIDITY=dict(book_state='UNKNOWN',sweep='NONE'),SENTIMENT=dict(sentiment='BULLISH',risk='UNKNOWN',positioning='UNKNOWN'))
    for name,version in bias.DEPENDENCIES.items():
        partial=.4 if name=='SENTIMENT' else .5 if name=='LIQUIDITY' else 1.
        dep=dict(contract_version='1.0.0',engine=name,engine_version=version,identity=copy.deepcopy(s['identity']),mode='CONFIRMED',candle_open_time=s['candle_open_time'],candle_close_time=s['candle_close_time'],as_of=s['as_of'],available_at=s['as_of'],
            classification=classifications[name],coverage=partial,confidence=min(.8,partial),strength=90.,data_quality='VALID' if partial==1 else 'PARTIAL',confirmation=dict(status='CONFIRMED'),config_hash=name+'-config',input_signature=name+'-source',provenance=dict(mode='SIMULATION'))
        if name=='SENTIMENT':dep['measurements']=dict(scope='DERIVATIVES_FUNDING_TILT_ONLY')
        if name=='LIQUIDITY':dep['measurements']=dict(observed=None,evidence_contributions=dict(flow=0.))
        s['dependencies'][name]=dep;s['dependency_expectations'][name]={k:dep[k] for k in ('engine_version','config_hash','input_signature')};s['dependency_refs'][name]=name+':'+str(i)
    return s


class BiasEngine(unittest.TestCase):
    def confirmed(self,mutate=lambda s:None):
        state=None
        for i in range(3):
            s=snapshot(i);mutate(s);result,state=bias.evaluate(s,previous_state=state)
        return result,state

    def test_price_families_capped_regime_not_an_extra_direction_vote(self):
        result,_=self.confirmed()
        self.assertIn(result['classification']['direction'],('BULLISH','STRONG_BULLISH'))
        self.assertEqual(result['candidate_classification']['direction'],result['classification']['direction'])
        m=result['measurements'];self.assertLessEqual(abs(m['contributions']['TREND'])+abs(m['contributions']['STRUCTURE']),.45)
        self.assertEqual(m['contributions']['INDEPENDENT_SENTIMENT'],0.)
        self.assertNotIn('REGIME',m['contributions']);self.assertAlmostEqual(m['directional_coverage'],.7)
        self.assertLessEqual(result['confidence'],result['coverage'])
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'Section_5_Market_Regime/contracts/result.schema.json').read_text());jsonschema.Draft202012Validator(schema).validate(result)

    def test_cancellation_neutral_is_not_unknown_or_high_confidence(self):
        def neutral(s):
            s['dependencies']['TREND']['strength']=100.;s['dependencies']['STRUCTURE']['classification']['direction']='BEARISH';s['dependencies']['MOMENTUM']['classification']['direction']='NEUTRAL'
        result,_=self.confirmed(neutral)
        self.assertEqual(result['classification']['direction'],'NEUTRAL');self.assertEqual(result['classification']['alignment'],'CONFLICTED')
        self.assertAlmostEqual(result['measurements']['agreement'],0.)
        s=snapshot(0);s['dependencies'].clear()
        result,_=bias.evaluate(s);self.assertEqual(result['classification'],bias.UNKNOWN);self.assertIsNone(result['strength'])

    def test_missing_structure_keeps_budget_and_pending_direction_cannot_vote(self):
        result,_=self.confirmed(lambda s:s['dependencies'].pop('STRUCTURE'))
        self.assertEqual(result['classification']['direction'],'UNKNOWN');self.assertLess(result['measurements']['directional_coverage'],.6)
        result,_=self.confirmed(lambda s:s['dependencies']['MOMENTUM']['confirmation'].update(status='PENDING'))
        self.assertEqual(result['classification']['direction'],'UNKNOWN')

    def test_risk_changes_without_direction_and_unknown_is_not_low(self):
        base_result,_=self.confirmed()
        def shock(s):s['dependencies']['VOLATILITY']['classification']['shock']='EXTREME'
        result,_=self.confirmed(shock)
        self.assertEqual(result['classification']['direction'],base_result['classification']['direction'])
        self.assertEqual(result['classification']['risk'],'EXTREME');self.assertEqual(base_result['classification']['risk'],'UNKNOWN')
        result,_=self.confirmed(lambda s:s['dependencies']['SENTIMENT']['classification'].update(risk='HIGH'))
        self.assertEqual(result['classification']['risk'],'HIGH')

    def test_actual_flow_is_separate_from_inferred_liquidity_and_capped(self):
        def flow(s):
            d=s['dependencies']['LIQUIDITY'];d['measurements']=dict(evidence_contributions=dict(flow=.05),observed=dict(scope=dict(venue='binance',market_type='usdt_perpetual',symbol='BTCUSDT'),association=dict(kind='RELATED_PERPETUAL_CONTEXT',basis_bps=0.),flow_60s=dict(imbalance=-1.)))
        result,_=self.confirmed(flow)
        self.assertEqual(result['measurements']['contributions']['OBSERVED_FLOW'],-.15)
        self.assertEqual(result['classification']['alignment'],'CONFLICTED')
        self.assertIn('RELATED_PERPETUAL_FLOW_NOT_SPOT_EXECUTION',result['quality_flags'])
        result,_=self.confirmed(lambda s:s['dependencies']['LIQUIDITY']['classification'].update(sweep='SSL_SWEEP'))
        self.assertEqual(result['measurements']['contributions']['OBSERVED_FLOW'],0.)

    def test_preview_restart_gap_hysteresis_identity_and_events(self):
        result,state=self.confirmed();old=copy.deepcopy(state);s=snapshot(3);s['closed']=False
        preview,same=bias.evaluate(s,previous_state=state);self.assertEqual(same,old);self.assertEqual(preview['measurements']['new_events'],[])
        a,state=bias.evaluate(snapshot(3),previous_state=state);b,_=bias.evaluate(snapshot(3),previous_state=json.loads(json.dumps(old)))
        self.assertEqual(a,b);self.assertEqual(a['measurements']['new_events'],[])
        result,state=bias.evaluate(snapshot(5),previous_state=state);self.assertEqual(result['data_quality'],'GAP');self.assertEqual(result['classification']['direction'],'UNKNOWN')
        with self.assertRaises(ValueError):bias.evaluate(snapshot(5),previous_state=state)
        s=snapshot(6);s['input_signature']='changed'
        with self.assertRaises(ValueError):bias.evaluate(s,previous_state=state)
        json.dumps(result,allow_nan=False)

    def test_future_provisional_wrong_market_and_aggregate_inputs_rejected(self):
        for key,value in (('available_at',10**12),('mode','PROVISIONAL'),('input_signature','changed')):
            s=snapshot(0);s['dependencies']['TREND'][key]=value
            result,_=bias.evaluate(s);self.assertEqual(result['classification']['direction'],'UNKNOWN')
        s=snapshot(0);s['dependencies']['STRUCTURE']['identity']['market_type']='usdt_perpetual'
        result,_=bias.evaluate(s);self.assertEqual(result['classification']['direction'],'UNKNOWN')
        s=snapshot(0);s['dependencies']['MTF']={}
        with self.assertRaises(ValueError):bias.evaluate(s)
