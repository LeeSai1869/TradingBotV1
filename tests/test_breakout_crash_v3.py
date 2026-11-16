from dataclasses import asdict
import unittest
from research_reports.BTC_1h_bear_target_breakouts_v3 import features as f,study as v3
from research_reports.BTC_1h_di_spread_trailing_v2 import replay as base
from tests.test_di_spread_trailing_v2 import hourly,bar,Prices,Fixed

def stable(count=20):
    return [[i*f.STEP,(i+1)*f.STEP-1,100,100.1,99.9,100] for i in range(count)]
def candle(i,o,h,l,c):return [i*f.STEP,(i+1)*f.STEP-1,o,h,l,c]

class ExitPolicyTests(unittest.TestCase):
    def test_bearish_exits_at_one_percent_instead_of_waiting_for_trailing(self):
        p=v3.Policy(fee=0,slip=0,activation='price_1pct')
        prices=Prices([bar(0,100,101.2,99.9,101.1)])
        got=base.trade([hourly(0),hourly(1)],0,prices,Fixed(),p,'low_first','1m')
        self.assertEqual(got['reason'],'TAKE_PROFIT');self.assertAlmostEqual(got['net_pct'],1);self.assertFalse(got['armed'])

    def test_bullish_exit_keeps_profit_and_di_plus_gate(self):
        p=v3.Policy(fee=0,slip=0,activation='price_1pct')
        prices=Prices([bar(0,100,101.2,99.9,101.1)])
        got=base.trade([hourly(0),hourly(1)],0,prices,Fixed('BULLISH',10),p,'low_first','1m')
        self.assertEqual(got['status'],'OPEN_AT_BOUNDARY');self.assertFalse(got['armed'])
        got=base.trade([hourly(0),hourly(1)],0,prices,Fixed('BULLISH',60),p,'low_first','1m')
        self.assertTrue(got['armed']);self.assertEqual(got['status'],'OPEN_AT_BOUNDARY')

    def test_stop_is_still_active_before_bearish_target(self):
        p=v3.Policy(fee=0,slip=0,activation='price_1pct')
        got=base.trade([hourly(0),hourly(1)],0,Prices([bar(0,100,102,99,100)]),Fixed(),p,'low_first','1m')
        self.assertEqual(got['reason'],'HARD_STOP');self.assertAlmostEqual(got['net_pct'],-.5)

    def test_bearish_price_target_sensitivity_does_not_change_bullish_profit_gate(self):
        policy=v3.Policy(bearish_target_basis='price_1pct')
        fill,_,net_trigger=base.levels(100,policy);price_trigger=fill*1.01
        high=(price_trigger+net_trigger)/2
        prices=Prices([bar(0,100,high,99.99,high-.01)])
        bearish=base.trade([hourly(0),hourly(1)],0,prices,Fixed(),policy,'low_first','1m')
        bullish=base.trade([hourly(0),hourly(1)],0,prices,Fixed('BULLISH',60),policy,'low_first','1m')
        self.assertEqual(bearish['reason'],'TAKE_PROFIT');self.assertAlmostEqual(bearish['exit_reference'],price_trigger)
        self.assertFalse(bullish['armed']);self.assertEqual(bullish['status'],'OPEN_AT_BOUNDARY')

class MarketFeatureTests(unittest.TestCase):
    def test_breakout_compares_with_prior_range_and_prior_volume_only(self):
        bars=stable()+[candle(20,100,101.1,99.95,101)]
        observation=f.observe(bars,[100]*20+[200])[-1]
        self.assertTrue(observation.breakout_up);self.assertEqual(observation.prior_high,100.1)
        self.assertEqual(observation.rvol,2);self.assertTrue(observation.micro_reclaim)

    def test_crash_is_confirmed_breakdown_not_an_oversold_reading(self):
        bars=stable()+[candle(20,100,100.05,98.7,98.75),candle(21,98.75,100.2,98.7,100.1)]
        observations=f.observe(bars,[100]*20+[200,100])
        self.assertTrue(observations[20].crash);self.assertTrue(observations[20].breakdown)
        self.assertTrue(observations[21].crash_recent,'fixed recent-event window remains known after recovery')
        self.assertFalse(observations[21].crash_unrecovered,'close above recorded crash high confirms recovery')

    def test_retest_preserves_original_breakout_level(self):
        bars=stable()+[candle(20,100,101.1,99.95,101),candle(21,100.2,100.4,100.08,100.35)]
        observation=f.observe(bars,[100]*20+[200,100])[-1]
        self.assertTrue(observation.breakout_retest);self.assertEqual(observation.retest_level,100.1)

    def test_no_future_bar_changes_an_existing_flag(self):
        prefix=stable()+[candle(20,100,101.1,99.95,101)]
        a=f.observe(prefix,[100]*20+[200])
        b=f.observe(prefix+[candle(21,101,110,90,95)],[100]*20+[200,10000])
        self.assertEqual([asdict(x) for x in a],[asdict(x) for x in b[:len(a)]])

    def test_missing_volume_does_not_fabricate_confirmation_and_gaps_reset_window(self):
        bars=stable()+[candle(20,100,101.1,99.95,101)]
        self.assertFalse(f.observe(bars,[100]*20+[None])[-1].breakout_up)
        bars.append(candle(23,101,103,100,102))
        self.assertFalse(f.observe(bars,[100]*20+[200,200])[-1].ready)

    def test_waiting_for_confirmation_changes_entry_time_causally(self):
        bars=stable(30);obs=[f.Observation(known_time=b[1]+1,ready=True) for b in bars];obs[23].micro_reclaim=True
        signal=dict(method='test',signal_time=bars[20][0],known_time=bars[20][1]+1,peak_di_minus=55,preview_rsi=15,hour_index=0)
        entries,reasons=v3.candidates([signal],bars,obs,Fixed(),40,'signal','test','wait_micro_reclaim')
        self.assertEqual(len(entries),1);self.assertEqual(entries[0]['entry_time'],bars[24][0])
        self.assertGreater(entries[0]['known_time'],signal['known_time'])
        obs[22].crash=True
        entries,_=v3.candidates([signal],bars,obs,Fixed(),40,'signal','test','wait_micro_reclaim')
        self.assertEqual(entries,[])

if __name__=='__main__':unittest.main()
