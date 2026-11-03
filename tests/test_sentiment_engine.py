"""Explicit derivatives-only proxy; missing sources never become broad mood."""
import copy
import json
from pathlib import Path
import unittest
from test_liquidity_engine import snapshot as base,observation
from Section_5_Market_Regime.engines import sentiment
from Section_5_Market_Regime.engines.sentiment_config import SentimentConfig


def snapshot(i=10,*,rate=.0001,baseline_rate=.0001,oi=110.,base_oi=100.,liquidations=0.):
    s=base(i);s.update(features=dict(measurement_gap=False,measurement_version='shared-v1',measurement_config_id='shared'),units=sentiment.UNITS.copy())
    s['field_validity']={k:'VALID' for k in sentiment.FIELDS};s['field_available_at']={k:s['as_of'] for k in sentiment.FIELDS}
    bundle=observation(s,oi=oi,base_oi=base_oi);current=bundle['sample'];current['mid']=current['metrics']['mid'];current['context']['funding_rate']=rate
    current['reported_long_liquidations_usdt']=liquidations
    baseline=copy.deepcopy(current);baseline.update(available_ms=s['as_of']-300000,sampled_ms=s['as_of']-300500,context=dict(bundle['oi_baseline']['context'],mark_price=s['candle']['close'],index_price=s['candle']['close'],funding_rate=baseline_rate,mark_exchange_ms=s['as_of']-300600,mark_received_ms=s['as_of']-300550))
    s['sentiment_sources']=dict(version='sentiment-projection-v1',status='RECORDED',current=current,baseline=baseline,last_gap_ms=None,association=bundle['association'])
    return s


class SentimentEngine(unittest.TestCase):
    def test_funding_tilt_is_not_crowding_or_extreme_mood(self):
        for rate,label in ((.0001,'BULLISH'),(-.0001,'BEARISH'),(0.,'NEUTRAL'),(.1,'BULLISH')):
            result,_=sentiment.evaluate(snapshot(rate=rate))
            self.assertEqual(result['classification']['sentiment'],label)
            self.assertEqual(result['classification']['positioning'],'UNKNOWN')
            self.assertEqual(result['measurements']['scope'],'DERIVATIVES_FUNDING_TILT_ONLY')
            self.assertEqual(result['coverage'],.4);self.assertEqual(result['data_quality'],'PARTIAL')
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'Section_5_Market_Regime/contracts/result.schema.json').read_text());jsonschema.Draft202012Validator(schema).validate(result)

    def test_stability_uses_past_point_not_bar_to_bar_mood(self):
        for rate,prior,label in ((.0001,.0001,'STABLE'),(.0001,0.,'IMPROVING'),(-.0001,0.,'DETERIORATING'),(.0003,0.,'RAPIDLY_CHANGING')):
            result,_=sentiment.evaluate(snapshot(rate=rate,baseline_rate=prior))
            self.assertEqual(result['classification']['stability'],label)
            self.assertGreater(result['measurements']['funding_change']['window_ms'],280000)

    def test_no_sources_is_unknown_and_missing_baseline_is_partial(self):
        s=snapshot();s.pop('sentiment_sources')
        result,_=sentiment.evaluate(s);self.assertEqual(result['classification'],sentiment.UNKNOWN);self.assertEqual(result['coverage'],0.)
        s=snapshot();s['sentiment_sources']['baseline']=None
        result,_=sentiment.evaluate(s);self.assertEqual(result['classification']['sentiment'],'BULLISH');self.assertEqual(result['classification']['stability'],'UNKNOWN');self.assertEqual(result['coverage'],.25)

    def test_optimistic_proxy_can_have_elevated_risk_without_buy_edge(self):
        result,_=sentiment.evaluate(snapshot(rate=.0004,liquidations=1500000.))
        self.assertEqual(result['classification']['sentiment'],'BULLISH');self.assertEqual(result['classification']['risk'],'HIGH')
        self.assertEqual(result['classification']['positioning'],'UNKNOWN')
        result,_=sentiment.evaluate(snapshot(rate=.0004,liquidations=15000000.))
        self.assertEqual(result['classification']['risk'],'EXTREME')
        result,_=sentiment.evaluate(snapshot(rate=.0004))
        self.assertEqual(result['classification']['risk'],'MODERATE')
        result,_=sentiment.evaluate(snapshot(rate=0.,oi=100.))
        self.assertEqual(result['classification']['risk'],'UNKNOWN')  # Zero sampled reports cannot prove low risk.

    def test_each_source_missingness_is_independent(self):
        s=snapshot(liquidations=1500000.);s['sentiment_sources']['current']['context']['funding_rate']=None
        result,_=sentiment.evaluate(s);self.assertEqual(result['classification']['sentiment'],'UNKNOWN');self.assertEqual(result['classification']['risk'],'HIGH')
        s=snapshot();s['sentiment_sources']['current']['context']['open_interest_exchange_ms']-=200000
        result,_=sentiment.evaluate(s);self.assertIsNone(result['measurements']['open_interest_change_pct']);self.assertEqual(result['classification']['sentiment'],'BULLISH')
        s=snapshot(base_oi=0.)
        result,_=sentiment.evaluate(s);self.assertIsNone(result['measurements']['open_interest_change_pct'])

    def test_future_stale_identity_association_and_gap_rejection(self):
        for mutate in (
            lambda b:b['current'].update(available_ms=10**12),
            lambda b:b['current'].update(symbol='ETHUSDT'),
            lambda b:b['association'].update(basis_bps=999.),
            lambda b:b.update(last_gap_ms=b['current']['sampled_ms']+1),
        ):
            s=snapshot();mutate(s['sentiment_sources']);result,_=sentiment.evaluate(s)
            self.assertEqual(result['classification'],sentiment.UNKNOWN)
        s=snapshot();s['sentiment_sources']['current']['context']['mark_exchange_ms']-=20000
        result,_=sentiment.evaluate(s);self.assertEqual(result['classification']['sentiment'],'UNKNOWN')
        s=snapshot();s['sentiment_sources']['baseline']['available_ms']=s['as_of']-1000
        result,_=sentiment.evaluate(s);self.assertEqual(result['classification']['stability'],'UNKNOWN')

    def test_restart_preview_event_dedup_and_source_generation(self):
        first,state=sentiment.evaluate(snapshot());self.assertEqual(len(first['measurements']['new_events']),1)
        old=copy.deepcopy(state);s=snapshot(11);s['closed']=False
        result,same=sentiment.evaluate(s,previous_state=state);self.assertEqual(same,old);self.assertEqual(result['measurements']['new_events'],[])
        a,state=sentiment.evaluate(snapshot(11),previous_state=state);b,_=sentiment.evaluate(snapshot(11),previous_state=json.loads(json.dumps(old)))
        self.assertEqual(a,b);self.assertEqual(a['measurements']['new_events'],[])
        s=snapshot(12);s['input_signature']='changed'
        with self.assertRaises(ValueError):sentiment.evaluate(s,previous_state=state)
        result,_=sentiment.evaluate(snapshot(13),previous_state=state);self.assertEqual(result['data_quality'],'GAP')
        self.assertEqual(result['classification']['sentiment'],'BULLISH')  # Still-fresh external context is separate from candle continuity.
        with self.assertRaises(ValueError):SentimentConfig(funding_change_fraction=1.)
        json.dumps(result,allow_nan=False)
