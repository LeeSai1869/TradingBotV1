"""Independent structural, causal sweep and observed market admission rules."""
import copy
import json
from pathlib import Path
import unittest
from test_regime_engine import snapshot as base
from Section_5_Market_Regime.engines import liquidity as engine
from Section_5_Market_Regime.engines.liquidity_config import LiquidityConfig


def snapshot(i, *, candle=None, changes=None, observations=False):
    s=base(i);f=dict(prev_high_liquidity=110.,prev_low_liquidity=100.,previous_day_high=None,previous_day_low=None,prev_close=105.,atr=2.,
        structure_events='[]',structure_events_version='structure-events-v1',structure_event_status='READY',
        measurement_contiguous_bars=1000,measurement_gap=False,measurement_version='shared-v1',measurement_config_id='shared')
    f.update(changes or {});s.update(features=f,units=engine.UNITS.copy(),field_validity={k:'VALID' if v is not None else 'UNAVAILABLE' for k,v in f.items()},field_available_at={k:s['as_of'] for k in f},feature_parameters=dict(liquidityLookback=20),market_metadata=dict(calendar='24/7 UTC'))
    s['candle']=candle or dict(open=104.,high=107.,low=102.,close=105.)
    if observations:s['observations']=observation(s)
    return s


def observation(s, *, oi=110., base_oi=100.):
    at=s['as_of'];sampled=at-500;mid=s['candle']['close'];bid=mid-.001;ask=mid+.001
    sample=dict(venue='binance',market='usdt_perpetual',symbol=s['identity']['symbol'],quote='USDT',observed=True,
        available_ms=sampled,sampled_ms=sampled,exchange_ms=sampled-100,book_received_ms=sampled-50,sequence=100,
        book_window_start_ms=sampled-5000,window_start_ms=sampled-5000,trade_coverage='continuous',reported_long_liquidations_usdt=0.,reported_short_liquidations_usdt=0.,liquidation_coverage='sampled exchange forceOrder stream; not all liquidations',
        coverage=dict(bid_bps=15.,ask_bps=17.),metrics=dict(mid=mid,best_bid=bid,best_ask=ask,spread_bps=(ask-bid)/mid*10000,
            bid_depth_10bps_usdt=200000.,ask_depth_10bps_usdt=250000.,buy_slippage_10000_usdt_bps=.2,sell_slippage_10000_usdt_bps=.2,bid_depth_10bps_change_usdt=0.,ask_depth_10bps_change_usdt=0.),
        context=dict(open_interest=oi,open_interest_exchange_ms=sampled-1000,open_interest_received_ms=sampled-500,
            mark_price=mid,index_price=mid,funding_rate=0.,mark_exchange_ms=sampled-100,mark_received_ms=sampled-50),
        flow_60s=dict(complete=True,coverage=1.,observed_window_ms=60000,aggressive_buy_usdt=900.,aggressive_sell_usdt=100.,price_change_bps=1.))
    baseline=dict(venue='binance',market='usdt_perpetual',symbol=s['identity']['symbol'],quote='USDT',observed=True,available_ms=at-300000,sampled_ms=at-300500,
        context=dict(open_interest=base_oi,open_interest_exchange_ms=at-301000,open_interest_received_ms=at-300500))
    return dict(version='liquidity-projection-v1',status='RECORDED',sample=sample,oi_baseline=baseline,last_gap_ms=None,
        association=dict(kind='RELATED_PERPETUAL_CONTEXT',spot_close=mid,spot_close_time=s['candle_close_time'],perpetual_mid=mid,basis_bps=0.))


class LiquidityEngine(unittest.TestCase):
    def test_structural_proximity_and_unavailable_is_not_balanced_book(self):
        result,_=engine.evaluate(snapshot(0,changes=dict(prev_high_liquidity=105.4)))
        self.assertEqual(result['classification']['structural_side'],'BUY_SIDE_NEAR')
        self.assertEqual(result['classification']['book_state'],'UNKNOWN');self.assertEqual(result['coverage'],.5)
        self.assertIsNone(result['strength'])
        result,_=engine.evaluate(snapshot(0,changes=dict(prev_low_liquidity=104.6)))
        self.assertEqual(result['classification']['structural_side'],'SELL_SIDE_NEAR')
        result,_=engine.evaluate(snapshot(0,changes=dict(prev_high_liquidity=105.)))
        self.assertEqual(result['classification']['structural_side'],'AT_LEVEL')
        result,_=engine.evaluate(snapshot(0));self.assertEqual(result['classification']['structural_side'],'MID_RANGE')

    def test_sweep_potential_then_rejection_and_acceptance_not_backdated(self):
        for side in ('BSL','SSL'):
            s=snapshot(0,candle=dict(open=105.,high=112. if side=='BSL' else 107.,low=102. if side=='BSL' else 98.,close=109. if side=='BSL' else 101.))
            first,state=engine.evaluate(s);original=copy.deepcopy(first)
            self.assertEqual(first['classification']['sweep'],side+'_SWEEP');self.assertEqual(first['classification']['sweep_status'],'POTENTIAL')
            for i in (1,2):
                result,state=engine.evaluate(snapshot(i,candle=dict(open=105.,high=109.,low=101.,close=108. if side=='BSL' else 102.)),previous_state=state)
            self.assertEqual(result['classification']['sweep_status'],'CONFIRMED_REJECTION');self.assertEqual(first,original)
            event=next(e for e in result['measurements']['new_events'] if e['type']=='SWEEP_RESOLVED')
            self.assertEqual(event['sweep_origin_time'],0);self.assertEqual(event['known_time'],180000)
            result,state=engine.evaluate(snapshot(3),previous_state=state)
            self.assertFalse(any(e['type']=='SWEEP_RESOLVED' for e in result['measurements']['new_events']))
        first,state=engine.evaluate(snapshot(0,candle=dict(open=105.,high=112.,low=104.,close=111.)))
        for i in (1,2):result,state=engine.evaluate(snapshot(i,candle=dict(open=111.,high=114.,low=111.,close=113.),changes=dict(prev_close=111.)),previous_state=state)
        self.assertEqual(result['classification']['sweep_status'],'ACCEPTANCE_ABOVE')

    def test_dual_sweeps_and_expiry_do_not_force_direction(self):
        result,state=engine.evaluate(snapshot(0,candle=dict(open=105.,high=112.,low=98.,close=105.)))
        self.assertEqual(result['classification']['sweep'],'UNKNOWN');self.assertIn('TWO_SIDED_SWEEP_AMBIGUITY',result['quality_flags'])
        self.assertEqual(len(state['pending']),2)
        _,state=engine.evaluate(snapshot(0,candle=dict(open=105.,high=112.,low=104.,close=110.)))
        for i in range(1,7):result,state=engine.evaluate(snapshot(i,candle=dict(open=110.,high=110.,low=109.,close=110.),changes=dict(prev_close=110.)),previous_state=state)
        self.assertFalse(state['pending']);self.assertTrue(any(e['type']=='SWEEP_EXPIRED' for e in result['measurements']['new_events']))

    def test_pivot_only_eligible_after_confirmation_and_invalid_batch_atomic(self):
        event=dict(type='PIVOT_HIGH',source_version='structure-events-v1',id='p1',price=106.,origin_time=0,confirmation_time=60000,known_time=120000)
        result,state=engine.evaluate(snapshot(1,changes=dict(structure_events=json.dumps([event]))))
        self.assertEqual(result['classification']['sweep'],'NONE')
        result,state=engine.evaluate(snapshot(2),previous_state=state)
        self.assertEqual(result['classification']['sweep'],'BSL_SWEEP');self.assertEqual(state['pending']['BSL']['level']['price'],106.)
        bad=dict(event,origin_time=999999)
        _,state=engine.evaluate(snapshot(1,changes=dict(structure_events=json.dumps([event,bad]))))
        self.assertFalse(state['pivots'])

    def test_observed_book_flow_oi_zero_funding_and_scope(self):
        s=snapshot(10,observations=True);result,_=engine.evaluate(s)
        self.assertEqual(result['classification']['book_state'],'DEEP');self.assertEqual(result['classification']['derivatives_state'],'BUILDING')
        self.assertEqual(result['coverage'],1.);self.assertEqual(result['measurements']['observed']['derivatives']['funding_rate'],0.)
        self.assertTrue(result['measurements']['observed']['flow_60s']['buy_absorption_evidence'])
        self.assertEqual(result['measurements']['observed']['scope']['market_type'],'usdt_perpetual')
        self.assertIn('PERPETUAL_CONTEXT_IS_NOT_SPOT_DEPTH',result['quality_flags'])
        self.assertEqual(result['measurements']['observed']['reported_liquidations']['long_usdt'],0.)
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'Section_5_Market_Regime/contracts/result.schema.json').read_text());jsonschema.Draft202012Validator(schema).validate(result)

    def test_shallow_coverage_thin_and_withdrawing(self):
        s=snapshot(10,observations=True);s['observations']['sample']['coverage']['bid_bps']=9.
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'UNKNOWN')
        s=snapshot(10,observations=True);m=s['observations']['sample']['metrics'];m['bid_depth_10bps_usdt']=1000.
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'THIN')
        s=snapshot(10,observations=True);m=s['observations']['sample']['metrics'];m.update(bid_depth_10bps_usdt=50000.,bid_depth_10bps_change_usdt=-200000.)
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'WITHDRAWING')

    def test_staleness_future_global_gap_and_basis_rejection(self):
        for key in ('available_ms','sampled_ms','exchange_ms','book_received_ms'):
            s=snapshot(10,observations=True);s['observations']['sample'][key]=s['as_of']+1
            result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'UNKNOWN')
        s=snapshot(10,observations=True);s['observations']['last_gap_ms']=s['as_of']-100
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'UNKNOWN')
        s=snapshot(10,observations=True);s['observations']['association']['basis_bps']=999.
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'UNKNOWN')
        s=snapshot(10,observations=True);s['observations']['sample']['symbol']='ETHUSDT'
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'UNKNOWN')
        s=snapshot(10,observations=True);s['observations']['sample']['available_ms']-=20000
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'UNKNOWN')

    def test_oi_baseline_freshness_and_zero_are_not_fabricated_changes(self):
        s=snapshot(10,observations=True);s['observations']['oi_baseline']=None
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['derivatives_state'],'UNKNOWN')
        for oi,label in ((100.,'STABLE'),(90.,'UNWINDING'),(0.,'UNWINDING')):
            s=snapshot(10);s['observations']=observation(s,oi=oi)
            result,_=engine.evaluate(s);self.assertEqual(result['classification']['derivatives_state'],label)
        s=snapshot(10);s['observations']=observation(s,base_oi=0.)
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['derivatives_state'],'UNKNOWN')
        s=snapshot(10,observations=True);s['observations']['sample']['context']['open_interest_exchange_ms']-=200000
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['derivatives_state'],'UNKNOWN')
        s=snapshot(10,observations=True);s['observations']['sample']['context']['mark_exchange_ms']-=20000
        result,_=engine.evaluate(s);self.assertIsNone(result['measurements']['observed']['derivatives']['funding_rate'])

    def test_restart_preview_gap_units_and_config(self):
        s=snapshot(0,candle=dict(open=105.,high=112.,low=104.,close=109.));_,state=engine.evaluate(s);old=copy.deepcopy(state)
        s=snapshot(1);s['closed']=False;preview,same=engine.evaluate(s,previous_state=state)
        self.assertEqual(same,old);self.assertEqual(preview['measurements']['new_events'],[])
        a,state=engine.evaluate(snapshot(1),previous_state=state);b,_=engine.evaluate(snapshot(1),previous_state=json.loads(json.dumps(old)));self.assertEqual(a,b)
        result,state=engine.evaluate(snapshot(3),previous_state=state);self.assertEqual(result['data_quality'],'GAP');self.assertFalse(state['pending'])
        s=snapshot(4);s['units']['prev_high_liquidity']='percent'
        result,_=engine.evaluate(s,previous_state=state);self.assertIsNone(result['measurements']['prev_high_liquidity'])
        with self.assertRaises(ValueError):LiquidityConfig(depth_bps=20)
        with self.assertRaises(ValueError):LiquidityConfig(sample_max_age_ms=20000)
        with self.assertRaises(ValueError):engine.evaluate(snapshot(3),previous_state=state)
        json.dumps(result,allow_nan=False)

    def test_ssl_acceptance_and_observed_dimensions_independent_of_candle_features(self):
        _,state=engine.evaluate(snapshot(0,candle=dict(open=105.,high=106.,low=98.,close=99.)))
        for i in (1,2):
            result,state=engine.evaluate(snapshot(i,candle=dict(open=99.,high=99.,low=97.,close=98.),changes=dict(prev_close=99.)),previous_state=state)
        self.assertEqual(result['classification']['sweep_status'],'ACCEPTANCE_BELOW')
        s=snapshot(10,changes=dict(prev_high_liquidity=None,prev_low_liquidity=None),observations=True)
        result,_=engine.evaluate(s)
        self.assertEqual(result['classification']['structural_side'],'UNKNOWN');self.assertEqual(result['classification']['book_state'],'DEEP')
        s=snapshot(10,changes=dict(measurement_gap=True),observations=True)
        result,_=engine.evaluate(s);self.assertEqual(result['data_quality'],'GAP');self.assertEqual(result['classification']['book_state'],'DEEP')

    def test_exact_market_flow_gaps_and_partial_windows_remain_explicit(self):
        s=snapshot(10,observations=True);s['identity']['market_type']='usdt_perpetual';s['observations']['association']=dict(kind='EXACT_MARKET')
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'DEEP')
        self.assertNotIn('PERPETUAL_CONTEXT_IS_NOT_SPOT_DEPTH',result['quality_flags'])
        s=snapshot(10,observations=True);s['observations']['sample']['trade_coverage']='partial'
        result,_=engine.evaluate(s);self.assertIsNone(result['measurements']['observed']['flow_60s'])
        s=snapshot(10,observations=True);s['observations']['last_gap_ms']=s['as_of']-20000
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'DEEP')
        self.assertIsNone(result['measurements']['observed']['flow_60s']);self.assertEqual(result['classification']['derivatives_state'],'UNKNOWN')

    def test_explicit_basis_limit_and_bad_optional_numbers(self):
        s=snapshot(10,observations=True);sample=s['observations']['sample'];old=sample['metrics']['mid'];mid=old*1.02
        sample['metrics'].update(mid=mid,best_bid=mid-.001,best_ask=mid+.001,spread_bps=.002/mid*10000)
        s['observations']['association'].update(perpetual_mid=mid,basis_bps=200.)
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'UNKNOWN');self.assertIn('CROSS_MARKET_BASIS_REJECTED',result['quality_flags'])
        s=snapshot(10,observations=True);s['observations']['sample']['metrics']['bid_depth_10bps_usdt']=float('nan')
        result,_=engine.evaluate(s);self.assertEqual(result['classification']['book_state'],'UNKNOWN');json.dumps(result,allow_nan=False)
