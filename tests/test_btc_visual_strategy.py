import copy
import unittest
from Section_8_Decision_Engine.btc_research import simulate,turns
from Section_1_Global_Core import btc_strategy_history


def bar(n,o=100,h=100.2,l=99.8,c=100,plus=20,minus=30,**features):
    return dict(open_time=n*300000,close_time=(n+1)*300000-1,open=o,high=h,low=l,close=c,
                features=dict(di_plus=plus,di_minus=minus,atr=.2,**features))


def setup():
    # DI- is independently confirmed on candle 2; no price breakout occurs.
    return [bar(0,minus=30),bar(1,minus=40),bar(2,minus=35)]


class BTCVisualStrategy(unittest.TestCase):
    def test_independent_turn_confirms_without_price_gate_then_next_open(self):
        rows=setup()+[bar(3,o=100,h=100.2,l=99.8,c=100)]
        result=simulate(rows);trade=result['trades'][0]
        self.assertEqual(trade['entry_time'],900000)
        self.assertEqual(trade['setup_time'],600000)
        self.assertEqual(trade['confirmation_time'],900000)
        self.assertIsNone(trade['candidate_confluence'])
        self.assertFalse(trade['price_confluence']['close_above_previous_high'])
        self.assertEqual([e['type'] for e in result['observations']],['BUY DI CONFIRMED'])
        self.assertFalse(simulate(rows[:3])['trades'])
        self.assertTrue(any(e['type']=='BUY_CONFIRMED' for e in simulate(rows[:3])['events']))

    def test_candidate_alone_never_arms_and_confluence_cannot_change_trades(self):
        rows=[bar(n,plus=20,minus=30,candidate_pivot=-1,
                  candidate_pivot_low_price=99.8,candidate_pivot_low_time=n*300000) for n in range(8)]
        result=simulate(rows)
        self.assertFalse(result['trades']);self.assertFalse(result['observations'])
        clean=setup()+[bar(3,o=100.4,h=100.5,l=100.3,c=100.4)]
        with_candidates=copy.deepcopy(clean)
        for row in with_candidates:row['features'].update(candidate_pivot=-1,candidate_pivot_low_price=99,candidate_pivot_low_time=0)
        a,b=simulate(clean),simulate(with_candidates)
        self.assertEqual(a['trades'][0]['entry_time'],b['trades'][0]['entry_time'])
        self.assertEqual(a['trades'][0]['entry'],b['trades'][0]['entry'])
        self.assertIsNotNone(b['trades'][0]['candidate_confluence'])

    def test_recognition_candle_can_have_candidate_and_price_confluence(self):
        rows=setup();rows[-1].update(high=101,close=100.8)
        rows[-1]['features'].update(candidate_pivot=-1,candidate_pivot_low_price=99.8,candidate_pivot_low_time=0)
        result=simulate(rows+[bar(3,o=100.8,h=100.9,l=100.6,c=100.8)])
        self.assertEqual(result['trades'][0]['entry_time'],900000)
        self.assertTrue(result['trades'][0]['price_confluence']['close_above_previous_high'])
        self.assertIsNotNone(result['trades'][0]['candidate_confluence'])

    def test_both_di_channels_are_independent_and_plateaus_do_not_invent_turns(self):
        a,b,c=bar(0,plus=10,minus=30),bar(1,plus=15,minus=40),bar(2,plus=20,minus=35)
        self.assertEqual([e['type'] for e in turns(a,b,c)],['DI_MINUS_PEAK'])
        b['features']['di_plus']=25
        self.assertEqual({e['type'] for e in turns(a,b,c)},{'DI_MINUS_PEAK','DI_PLUS_PEAK'})
        b['features']['di_minus']=30
        self.assertFalse(any(e['channel']=='di_minus' for e in turns(a,b,c)))

    def test_dominance_gate_and_no_wait_for_another_price_candle(self):
        plus_dominant=[bar(0,plus=40,minus=20),bar(1,plus=40,minus=30),bar(2,plus=40,minus=25),bar(3,plus=40,minus=24,h=101,c=100.8)]
        self.assertFalse(simulate(plus_dominant)['trades'])
        neutral=setup();neutral[-1]['features'].update(di_plus=35)
        self.assertFalse(simulate(neutral+[bar(3)])['trades'])
        result=simulate(setup()+[bar(3,o=99.7,h=99.9,l=99.6,c=99.8)])
        self.assertEqual(len(result['trades']),1) # no setup-low or chase entry gate
        self.assertFalse(any(e['type'].endswith('_CANCELLED') for e in result['events']))
        jump=simulate(setup()+[bar(3,o=102,h=102.2,l=101.9,c=102)])
        self.assertEqual(len(jump['trades']),1) # no hidden 0.5% chase gate

    def test_next_open_entry_stop_gap_costs_and_immutable_input(self):
        rows=setup()+[bar(3,o=100.4,h=100.5,l=100.3,c=100.4),bar(4,o=99,h=99.2,l=98.9,c=99)]
        original=copy.deepcopy(rows);trade=simulate(rows)['trades'][0]
        self.assertAlmostEqual(trade['entry'],100.4*1.0002)
        self.assertAlmostEqual(trade['exit'],99*.9998)
        self.assertLess(trade['net_pct'],-.5)
        self.assertEqual(trade['reason'],'Hard stop');self.assertEqual(rows,original)

    def test_profit_alone_no_longer_arms_trailing(self):
        rows=setup()+[bar(3,o=100.4,h=102,l=100.3,c=101.8)]
        result=simulate(rows);trade=result['trades'][0]
        self.assertEqual(trade['status'],'OPEN')
        self.assertFalse(trade['sell_state']['trailing_armed'])
        self.assertEqual(trade['stop'],trade['hard_stop'])

    def test_early_setup_arms_trail_only_then_independent_nonretroactive_stop(self):
        rows=setup()+[bar(3,o=100,h=100.2,l=99.9,c=100.1,plus=30,minus=20),
            bar(4,o=100.1,h=100.3,l=100,c=100.2,plus=40,minus=20),
            bar(5,o=100.2,h=100.3,l=99.9,c=100.2,plus=35,minus=20)]
        first=simulate(rows);trade=first['trades'][0]
        self.assertEqual(trade['status'],'OPEN')
        self.assertTrue(trade['sell_state']['trailing_armed'])
        self.assertLess(first['levels'][-1]['stop'],trade['stop'])
        self.assertFalse(any(e['type']=='SELL_CONFIRMED' for e in first['events']))
        # DI+ resumes rising; trailing remains armed and tightens anyway.
        rows += [bar(6,o=100.2,h=100.4,l=100.05,c=100.3,plus=45,minus=20),
                 bar(7,o=100.3,h=100.4,l=100,c=100.2,plus=46,minus=20)]
        later=simulate(rows)
        self.assertEqual(later['trades'][0]['reason'],'Trailing stop')
        self.assertEqual(later['trades'][0]['exit_rule_id'],'P_TRAILING_STOP')
        self.assertEqual(later['trades'][0]['exit_time'],2100000)
        self.assertEqual(first['levels'],later['levels'][:len(first['levels'])])

    def test_spread_maturity_decrease_exits_with_explicit_rule_reason(self):
        from Section_8_Decision_Engine.btc_sell_rules import MATURITY
        result=simulate(setup()+[bar(3,plus=60,minus=10),bar(4,plus=61,minus=10),
                                bar(5,plus=60.999,minus=10),bar(6)])
        trade=result['trades'][0]
        self.assertEqual(trade['exit_rule_id'],MATURITY)
        self.assertEqual(trade['exit_time'],1800000)
        self.assertEqual(trade['matched_exit_rules'],[MATURITY])
        self.assertTrue(any(e['type']=='BULLISH_SPREAD_MATURE' for e in result['events']))

    def test_emerging_control_loss_exit_is_separate_from_small_peaks(self):
        from Section_8_Decision_Engine.btc_sell_rules import CONTROL
        rows=setup()
        for row in rows:row['features']['di_plus']=10
        result=simulate(rows+[bar(3,plus=30,minus=20),bar(4,plus=20,minus=21),bar(5)])
        trade=result['trades'][0]
        self.assertEqual(trade['exit_rule_id'],CONTROL)
        self.assertEqual(trade['exit_time'],1500000)
        self.assertEqual(trade['sell_state']['entry_scenario'],'BELOW_BOTH')
        self.assertTrue(any(e['type']=='BUYER_CONTROL_GAINED' for e in result['events']))

    def test_gap_censors_and_resets_three_candle_memory(self):
        result=simulate(setup()+[bar(3,o=100.4,h=100.5,l=100.3,c=100.4),bar(5)])
        trade=result['trades'][0]
        self.assertEqual(trade['status'],'CENSORED');self.assertNotIn('net_pct',trade)
        self.assertEqual(result['gaps'],1)
        self.assertFalse(simulate([bar(0,minus=30),bar(2,minus=40),bar(3,minus=35)])['observations'])

    def test_prefix_event_history_is_not_rewritten_by_future_candles(self):
        rows=setup()+[bar(3,o=100.4,h=100.5,l=100.3,c=100.4),bar(4,plus=50,minus=10)]
        early=simulate(rows[:4]);later=simulate(rows)
        self.assertEqual(early['events'],[e for e in later['events'] if e['time']<1200000])
        peak=next(e for e in early['events'] if e['type']=='DI_MINUS_PEAK')
        self.assertEqual(peak['origin_time'],300000);self.assertEqual(peak['known_time'],900000)

    def test_bounded_details_keep_identical_position_state_and_event_ids(self):
        rows=setup()+[bar(n,o=100.4,h=100.5,l=100.3,c=100.4) for n in range(3,12)]
        whole=simulate(rows);bounded=simulate(rows,detail_since=900000)
        self.assertEqual(whole['trades'],bounded['trades'])
        self.assertEqual(whole['summary'],bounded['summary'])
        for key in ('events','levels','observations'):
            self.assertEqual(bounded[key],[r for r in whole[key] if r['time']>=900000])

    def test_cash_summary_compounds_complete_closed_trade_returns(self):
        result=simulate(setup()+[bar(3,o=100,h=100.2,l=99.8,c=100),bar(4,o=99,h=99.2,l=98.9,c=99)])
        expected=100.
        for trade in result['trades']:
            if trade['status']=='CLOSED':expected*=1+trade['net_pct']/100
        self.assertAlmostEqual(result['summary']['realized_balance_usd'],expected)
        self.assertLess(expected,100)

    def test_only_requested_symbol_timeframes(self):
        for symbol,tf in [('ETHUSDT','5m'),('BTCUSDT','1m'),('BTCUSDT','4h')]:
            with self.assertRaises(ValueError):btc_strategy_history.history(symbol,tf)
