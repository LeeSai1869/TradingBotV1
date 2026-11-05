import copy
import unittest
from Section_8_Decision_Engine.btc_research import simulate,turns
from Section_1_Global_Core import btc_strategy_history


def bar(n,o=100,h=100.2,l=99.8,c=100,plus=20,minus=30,**features):
    return dict(open_time=n*300000,close_time=(n+1)*300000-1,open=o,high=h,low=l,close=c,
                features=dict(di_plus=plus,di_minus=minus,atr=.2,**features))


def setup():
    # DI- peak is known at candle 2; later price confirms on candle 3.
    # Neither improving DI+ nor continued falling DI- is required at confirmation.
    return [bar(0,minus=30),bar(1,minus=40),bar(2,minus=35),
            bar(3,h=100.5,c=100.4,plus=19,minus=36)]


class BTCVisualStrategy(unittest.TestCase):
    def test_independent_turn_and_later_confirmation_then_next_open(self):
        rows=setup()+[bar(4,o=100.4,h=100.5,l=100.3,c=100.4)]
        result=simulate(rows);trade=result['trades'][0]
        self.assertEqual(trade['entry_time'],1200000)
        self.assertEqual(trade['setup_time'],600000)
        self.assertEqual(trade['confirmation_time'],1200000)
        self.assertIsNone(trade['candidate_confluence'])
        self.assertEqual([e['type'] for e in result['observations']],['BUY SETUP','BUY CONFIRMED'])
        self.assertFalse(simulate(rows[:3])['trades'])
        self.assertFalse(simulate(rows[:4])['trades'])

    def test_candidate_alone_never_arms_and_confluence_cannot_change_trades(self):
        rows=[bar(n,plus=20,minus=30,candidate_pivot=-1,
                  candidate_pivot_low_price=99.8,candidate_pivot_low_time=n*300000) for n in range(8)]
        result=simulate(rows)
        self.assertFalse(result['trades']);self.assertFalse(result['observations'])
        clean=setup()+[bar(4,o=100.4,h=100.5,l=100.3,c=100.4)]
        with_candidates=copy.deepcopy(clean)
        for row in with_candidates:row['features'].update(candidate_pivot=-1,candidate_pivot_low_price=99,candidate_pivot_low_time=0)
        a,b=simulate(clean),simulate(with_candidates)
        self.assertEqual(a['trades'][0]['entry_time'],b['trades'][0]['entry_time'])
        self.assertEqual(a['trades'][0]['entry'],b['trades'][0]['entry'])
        self.assertIsNotNone(b['trades'][0]['candidate_confluence'])

    def test_same_candle_price_confirmation_is_not_enough(self):
        rows=setup()[:3];rows[-1].update(high=101,close=100.8)
        result=simulate(rows+[bar(3,o=100.8,h=100.9,l=100.6,c=100.8)])
        self.assertFalse(result['trades'])
        self.assertFalse(any(e['type']=='BUY_CONFIRMED' for e in result['events']))

    def test_both_di_channels_are_independent_and_plateaus_do_not_invent_turns(self):
        a,b,c=bar(0,plus=10,minus=30),bar(1,plus=15,minus=40),bar(2,plus=20,minus=35)
        self.assertEqual([e['type'] for e in turns(a,b,c)],['DI_MINUS_PEAK'])
        b['features']['di_plus']=25
        self.assertEqual({e['type'] for e in turns(a,b,c)},{'DI_MINUS_PEAK','DI_PLUS_PEAK'})
        b['features']['di_minus']=30
        self.assertFalse(any(e['channel']=='di_minus' for e in turns(a,b,c)))

    def test_dominance_gate_expiry_and_invalidated_price_cancel(self):
        for tail,reason in [([bar(3,plus=40,minus=35)],'Dominance gate changed'),
                            ([bar(3,l=99.5)],'Setup price invalidated'),
                            ([bar(n,plus=20,minus=35) for n in range(3,12)],'Confirmation expired')]:
            result=simulate(setup()[:3]+tail)
            self.assertFalse(result['trades'])
            self.assertTrue(any(e.get('reason')==reason for e in result['events']))
        plus_dominant=[bar(0,plus=40,minus=20),bar(1,plus=40,minus=30),bar(2,plus=40,minus=25),bar(3,plus=40,minus=24,h=101,c=100.8)]
        self.assertFalse(simulate(plus_dominant)['trades'])

    def test_next_open_entry_stop_gap_costs_and_immutable_input(self):
        rows=setup()+[bar(4,o=100.4,h=100.5,l=100.3,c=100.4),bar(5,o=99,h=99.2,l=98.9,c=99)]
        original=copy.deepcopy(rows);trade=simulate(rows)['trades'][0]
        self.assertAlmostEqual(trade['entry'],100.4*1.0002)
        self.assertAlmostEqual(trade['exit'],99*.9998)
        self.assertLess(trade['net_pct'],-.5)
        self.assertEqual(trade['reason'],'Hard stop');self.assertEqual(rows,original)

    def test_trail_not_retroactive_and_profit_not_fixed_target(self):
        rows=setup()+[bar(4,o=100.4,h=102,l=100.3,c=101.8)]
        first=simulate(rows);self.assertEqual(first['trades'][0]['status'],'OPEN')
        self.assertEqual(first['levels'][0]['stop'],first['trades'][0]['hard_stop'])
        later=simulate(rows+[bar(5,o=101.8,h=102,l=101.6,c=101.9)])
        self.assertEqual(later['trades'][0]['reason'],'Trailing stop')
        self.assertEqual(first['levels'],later['levels'][:1])

    def test_di_plus_peak_then_later_price_weakness_exits_spot_at_next_open(self):
        rows=setup()+[bar(4,o=100.4,h=100.5,l=100.3,c=100.4,plus=30,minus=20),
            bar(5,o=100.4,h=100.6,l=100.3,c=100.5,plus=40,minus=20),
            bar(6,o=100.5,h=100.6,l=100.3,c=100.5,plus=35,minus=20),
            bar(7,o=100.5,h=100.6,l=100.1,c=100.2,plus=36,minus=19),
            bar(8,o=100.2,h=100.4,l=100,c=100.1)]
        result=simulate(rows);trade=result['trades'][0]
        self.assertEqual(trade['reason'],'DI+ peak then later price weakness')
        self.assertEqual(trade['exit_time'],2400000)
        self.assertTrue(any(e['type']=='SELL_SETUP' for e in result['events']))
        self.assertTrue(any(e['type']=='SELL_CONFIRMED' for e in result['events']))
        self.assertEqual(len(result['trades']),1)

    def test_gap_censors_and_resets_three_candle_memory(self):
        result=simulate(setup()+[bar(4,o=100.4,h=100.5,l=100.3,c=100.4),bar(6)])
        trade=result['trades'][0]
        self.assertEqual(trade['status'],'CENSORED');self.assertNotIn('net_pct',trade)
        self.assertEqual(result['gaps'],1)
        self.assertFalse(simulate([bar(0,minus=30),bar(2,minus=40),bar(3,minus=35)])['observations'])

    def test_prefix_event_history_is_not_rewritten_by_future_candles(self):
        rows=setup()+[bar(4,o=100.4,h=100.5,l=100.3,c=100.4),bar(5,plus=50,minus=10)]
        early=simulate(rows[:4]);later=simulate(rows)
        self.assertEqual(early['events'],[e for e in later['events'] if e['time']<1200000])
        peak=next(e for e in early['events'] if e['type']=='DI_MINUS_PEAK')
        self.assertEqual(peak['origin_time'],300000);self.assertEqual(peak['known_time'],900000)

    def test_bounded_details_keep_identical_position_state_and_event_ids(self):
        rows=setup()+[bar(n,o=100.4,h=100.5,l=100.3,c=100.4) for n in range(4,12)]
        whole=simulate(rows);bounded=simulate(rows,detail_since=900000)
        self.assertEqual(whole['trades'],bounded['trades'])
        self.assertEqual(whole['summary'],bounded['summary'])
        for key in ('events','levels','observations'):
            self.assertEqual(bounded[key],[r for r in whole[key] if r['time']>=900000])

    def test_only_requested_symbol_timeframes(self):
        for symbol,tf in [('ETHUSDT','5m'),('BTCUSDT','1m'),('BTCUSDT','4h')]:
            with self.assertRaises(ValueError):btc_strategy_history.history(symbol,tf)
