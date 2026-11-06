import copy
import json
import unittest
from Section_8_Decision_Engine import pivot_sequences as s
from study_btc_hour_sequences import visual


def packet():
    rows=[];plus=[5,8,10,15,30,28,26,29,31,27,20,24,29,32];minus=[20,30,40,35,20,15,12,13,11,35,45,42,35,25]
    for i in range(36):
        active=-1 if i<3 or i>=6 else 1
        low_time=2*s.STEP if i>=2 else i*s.STEP;low_price=97 if i>=2 else 99-i
        high_time=4*s.STEP if i>=4 else 3*s.STEP if i==3 else 0;high_price=106 if i>=4 else 104
        p=plus[i] if i<len(plus) else 20.;m=minus[i] if i<len(minus) else 20.
        f=dict(di_plus=p,di_minus=m,di_spread=abs(p-m),adx=20+i,measurement_gap=False,candidate_pivot=active,
            candidate_pivot_low_time=low_time,candidate_pivot_low_price=low_price,candidate_pivot_low_bar=low_time//s.STEP,
            candidate_pivot_high_time=high_time,candidate_pivot_high_price=high_price,candidate_pivot_high_bar=high_time//s.STEP,
            rsi=40,atr=2,relative_volume=1,regime_state='LEGACY',trend_state='MATURE',current_structure='STRUCTURE_BULL')
        rows.append(dict(open_time=i*s.STEP,close_time=(i+1)*s.STEP-1,open=100,high=106 if i==4 else 104,low=97 if i==2 else 98,close=101,volume=100,features=f,feature_valid=True))
    low=dict(id='a'*64,side='BUY_SIDE',pivot=dict(type='PIVOT_LOW',origin_time=2*s.STEP,confirmation_time=3*s.STEP,known_time=4*s.STEP,price=97),origin=dict(status='HIT',first_hit=dict(known_by=4*s.STEP)),next_opposite=dict(origin_time=4*s.STEP))
    high=dict(id='b'*64,side='SELL_SIDE',pivot=dict(type='PIVOT_HIGH',origin_time=4*s.STEP,confirmation_time=6*s.STEP,known_time=7*s.STEP,price=106),origin=dict(status='HIT',first_hit=dict(known_by=6*s.STEP)),next_opposite=None)
    return dict(version='btc-hour-sequence-source-v1',symbol='BTCUSDT',timeframe='1h',threshold_pct=1.,source_id='source',observed_as_of=36*s.STEP,candles=rows,pivots=[low,high],engine_history={},archived_scores=dict(status='UNAVAILABLE',rows={}),definitions=dict(di_score='raw values, no probability',industry_bias='UNAVAILABLE'))


class Sequences(unittest.TestCase):
    def test_independent_exact_three_candle_turn_and_spread(self):
        p=packet();events,flags=s.events(p['candles'])
        self.assertTrue(flags[3]['di_minus_peak']);self.assertTrue(flags[3]['spread_peak']);self.assertTrue(flags[3]['di_only_buy_turn'])
        self.assertFalse(flags[3]['di_plus_peak'])
        self.assertEqual(events[3][0]['known_time'],4*s.STEP)

    def test_candidate_phase_start_is_not_final_extreme_update(self):
        p=packet();episodes,_,observations,first,matches=s.candidate_history(p['candles'])
        self.assertEqual(episodes[0]['start_index'],0);self.assertEqual(first['BUY',2*s.STEP],2)
        self.assertEqual(matches['BUY',2*s.STEP][0][:2],(0,2))
        self.assertTrue(any(o['event']=='CARRIED_FORWARD' for o in observations))

    def test_preserved_control_and_lost_control_recoveries_are_separate(self):
        dips=s.dip_recoveries(packet()['candles']);by={d['recovery_index']:d for d in dips}
        self.assertEqual(by[7]['comparison_path'],'STAYED_ABOVE_BOTH');self.assertEqual(by[7]['declining_bars'],2)
        self.assertEqual(by[7]['regained_pre_dip_level_at'],8)
        self.assertEqual(by[11]['comparison_path'],'LOST_BOTH')

    def test_spread_crossing_cannot_precede_loss_to_minus(self):
        for plus in range(0,30):
            for minus in range(0,30):
                if abs(plus-minus)>plus:self.assertGreater(minus,plus)

    def test_fixed_outlook_reports_ohlc_ambiguity_and_incomplete_tail(self):
        p=packet();out=s.future(p['candles'],4,3)
        self.assertEqual(out['first_target'],'SAME_CANDLE_AMBIGUOUS');self.assertTrue(out['complete'])
        out=s.future(p['candles'],34,12);self.assertFalse(out['complete']);self.assertEqual(out['status'],'CENSORED')
        self.assertIsNone(out['close_return_pct'])

    def test_exact_closed_context_and_missing_not_neutral(self):
        p=packet();p['engine_history']={'4h:REGIME':dict(status='READY',results={'0':dict(candle_close_time=4*s.STEP-1,as_of=4*s.STEP,data_quality='VALID',classification=dict(primary='RANGING'))})}
        lookup=s.ContextLookup(p)
        self.assertTrue(lookup.at(3*s.STEP)['4h:REGIME'].startswith('UNAVAILABLE:'))
        ref=lookup.at(4*s.STEP)['4h:REGIME'];self.assertEqual(lookup.resolve('4h:REGIME',ref)['classification']['primary'],'RANGING')
        self.assertTrue(lookup.at(8*s.STEP)['4h:REGIME'].startswith('UNAVAILABLE:'))

    def test_full_cohort_has_all_pivots_all_candidate_bars_and_causal_snapshots(self):
        p=packet();before=copy.deepcopy(p);result=s.analyze(p)
        self.assertEqual(result['counts']['pivots'],2);self.assertEqual(result['counts']['linked_candidate_pivots'],2)
        low=result['cases'][0]
        self.assertEqual(low['stages']['candidate_start'],0);self.assertEqual(low['stages']['final_extreme_first_recorded'],2)
        self.assertFalse(low['pressure_peak_seen_by_origin']);self.assertEqual(low['pressure_peaks'],[3])
        self.assertTrue(result['snapshots']['3']['events']['di_minus_peak'])
        self.assertEqual(result['snapshots']['2']['latest_known_turns'].get('DI_MINUS_PEAK'),None)
        self.assertGreater(result['counts']['candidate_observations'],result['counts']['pivots'])
        self.assertEqual(p,before);json.dumps(result,allow_nan=False)
        page=visual(result);self.assertIn('Every pivot',page);self.assertIn('Asia/Karachi',page)

    def test_future_changes_cannot_change_candidate_start_or_origin_flags(self):
        original=packet();first=s.analyze(original)
        changed=packet()
        for r in changed['candles'][10:]:r['features']['di_plus']=99
        second=s.analyze(changed)
        self.assertEqual(first['snapshots']['2'],second['snapshots']['2'])
        self.assertEqual(first['cases'][0]['pressure_peak_seen_by_origin'],second['cases'][0]['pressure_peak_seen_by_origin'])

    def test_di_and_spread_confirmation_can_arrive_on_different_candles(self):
        p=packet()
        for i,(plus,minus) in enumerate(((5,20),(10,30),(4,28),(10,25))):
            p['candles'][i]['features'].update(di_plus=plus,di_minus=minus,di_spread=abs(plus-minus))
        result=s.analyze(p);low=result['cases'][0]
        self.assertEqual(low['pressure_peaks'],[2]);self.assertEqual(low['spread_peaks'],[3]);self.assertEqual(low['spread_peak_lag_bars'],1)
        self.assertTrue(result['snapshots']['2']['events']['di_minus_peak']);self.assertFalse(result['snapshots']['2']['events']['spread_peak'])
        self.assertTrue(result['snapshots']['3']['events']['spread_peak']);self.assertFalse(result['snapshots']['3']['events']['di_minus_peak'])

    def test_plateau_gap_and_unrecovered_down_runs_remain_visible(self):
        rows=packet()['candles'][:5]
        for r,value in zip(rows,(10,9,9,8,7)):r['features']['di_plus']=value
        runs=s.down_runs(rows)
        self.assertEqual([r['end_reason'] for r in runs],['PLATEAU','END_OF_DATA'])
        self.assertEqual(len(s.dip_recoveries(rows)),0)
        rows[2]['feature_valid']=False
        self.assertEqual(s.down_runs(rows)[0]['end_reason'],'GAP')

    def test_gap_during_regain_search_is_not_counted_as_failed_regain(self):
        p=packet();p['candles'][8]['feature_valid']=False
        first=next(d for d in s.dip_recoveries(p['candles']) if d['recovery_index']==7)
        self.assertEqual(first['regained_pre_dip_level_status'],'CENSORED')
        self.assertFalse(first['regained_pre_dip_level_window_complete'])

    def test_native_outcomes_and_extremes_are_checked_against_raw_candles(self):
        p=packet();p['pivots'][0]['origin']['status']='NO_HIT'
        with self.assertRaisesRegex(ValueError,'outcome differs'):s.analyze(p)
        p=packet();p['pivots'][0]['pivot']['price']-=.01
        with self.assertRaisesRegex(ValueError,'raw candle extreme'):s.analyze(p)
