
from Section_1_Global_Core.paths import REPO_ROOT
import importlib.util
from pathlib import Path
import sys
import unittest
from copy import deepcopy
from Section_12_Research.reports.BTC_1h_di_spread_trailing_v2 import intrabar_5m as intra
from Section_4_Features.features.momentum import calculate_dmi,calculate_rsi

path=REPO_ROOT/'Section_12_Research/reports/BTC_1h_di_spread_trailing_v2/replay.py'
spec=importlib.util.spec_from_file_location('di_spread_trailing_v2',path)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

def hourly(i,*,plus=5,minus=55,rsi=15,direction='BEARISH'):
    return dict(open_time=i*m.HOUR,close_time=(i+1)*m.HOUR-1,open=100,high=102,low=99,close=100,
                features=dict(di_plus=plus,di_minus=minus,rsi=rsi,measurement_gap=False),
                context={'REGIME':dict(data_quality='VALID',classification={'direction':direction})})
def bar(i,o,h,l,c):
    start=m.HOUR+i*m.MINUTE;return [start,start+m.MINUTE-1,o,h,l,c]
class Prices:
    def __init__(self,rows):self.rows=rows;self.until=rows[-1][1]
    def bars(self,*_):yield from self.rows
class Fixed:
    def __init__(self,direction='BEARISH',plus=10):self.direction=direction;self.plus=plus
    def at(self,t):return self.direction,self.plus

class TrailingTests(unittest.TestCase):
    def replay(self,bars,policy=None,context=None,order='low_first'):
        return m.trade([hourly(0),hourly(1)],0,Prices(bars),context or Fixed(),policy or m.Policy(fee=0,slip=0,activation='price_1pct'),order,'1m')

    def test_hard_stop_is_active_before_trailing_and_net_budget_includes_costs(self):
        p=m.Policy();entry,hard,_=m.levels(100,p)
        self.assertAlmostEqual(m.net(hard,entry,p),-.5994522590963558)
        p=m.Policy(risk='net_0_5pct');entry,hard,_=m.levels(100,p)
        self.assertAlmostEqual(m.net(hard,entry,p),-.5)
        r=self.replay([bar(0,100,100.4,99,99.2)])
        self.assertEqual(r['reason'],'HARD_STOP');self.assertFalse(r['armed']);self.assertAlmostEqual(r['net_pct'],-.5)

    def test_bearish_activation_is_not_a_sale_and_trail_tracks_further_highs(self):
        r=self.replay([bar(0,100,101.2,99.9,101.1),bar(1,101.1,102,101,101.5),bar(2,101.5,101.6,101.4,101.45)])
        self.assertEqual(r['reason'],'TRAILING_STOP');self.assertEqual(r['bars'],3)
        self.assertAlmostEqual(r['highest'],102);self.assertAlmostEqual(r['exit_reference'],101.49)

    def test_bullish_activation_requires_profit_and_strict_di_plus_above_50(self):
        rows=[bar(0,100,102,100,101.5)]
        r=self.replay(rows,context=Fixed('BULLISH',50));self.assertFalse(r['armed'])
        r=self.replay(rows,context=Fixed('BULLISH',50.1));self.assertTrue(r['armed'])
        r=self.replay([bar(0,100,100.8,99.9,100.7)],context=Fixed('BULLISH',60));self.assertFalse(r['armed'])

    def test_late_gate_uses_highest_since_buy_and_exits_at_current_market(self):
        class Gate:
            def at(self,t):return 'BULLISH',10 if t==m.HOUR else 60
        r=self.replay([bar(0,100,103,100,102),bar(1,101.5,102,101,101.7)],context=Gate())
        self.assertEqual(r['reason'],'TRAILING_STOP');self.assertEqual(r['highest'],103)
        self.assertEqual(r['exit_reference'],101.5,'never fill above market at a newly activated stop')

    def test_opening_gap_can_breach_intended_cap_and_holding_time_is_a_duration(self):
        r=self.replay([bar(0,100,100.2,99.8,100),bar(1,99,99.2,98.8,99)])
        self.assertAlmostEqual(r['net_pct'],-1);self.assertEqual(r['holding_minutes_upper'],1)

    def test_current_context_never_reads_an_unclosed_hours_di(self):
        rows=[hourly(0,plus=10),hourly(1,plus=80,direction='BULLISH')];c=m.Context(rows)
        self.assertEqual(c.at(m.HOUR),('BEARISH',10));self.assertEqual(c.at(2*m.HOUR-1),('BEARISH',10))
        self.assertEqual(c.at(2*m.HOUR),('BULLISH',80))

    def test_one_percent_activation_does_not_lock_in_one_percent_after_a_half_percent_trail(self):
        p=m.Policy(risk='net_0_5pct');entry,_,trigger=m.levels(100,p)
        self.assertAlmostEqual(m.net(trigger,entry,p),1)
        self.assertAlmostEqual(m.net(trigger*.995,entry,p),.495)

    def test_setup_uses_displayed_absolute_spread_and_shows_filter_timing(self):
        rows=[hourly(0,plus=60,minus=0),hourly(1,minus=55),hourly(2,minus=50),hourly(3)]
        self.assertFalse(m.setup(rows,2,40,'peak_no_rsi'),'absolute spread is already falling; previous bar is not a peak')
        rows[0]=hourly(0,minus=45);rows[2]=hourly(2,minus=42,rsi=25)
        self.assertTrue(m.setup(rows,2,50,'peak_no_rsi'));self.assertFalse(m.setup(rows,2,50,'confirmation_no_rsi'))
        self.assertTrue(m.setup(rows,2,50,'peak_rsi_at_peak'));self.assertFalse(m.setup(rows,2,50,'peak_rsi_at_signal'))

    def test_ohlc_ordering_remains_visible(self):
        bars=[bar(0,100,102,99,101)]
        low=self.replay(bars,order='low_first');high=self.replay(bars,order='high_first')
        self.assertEqual(low['reason'],'HARD_STOP');self.assertEqual(high['reason'],'TRAILING_STOP')
        self.assertNotEqual(low['net_pct'],high['net_pct'])

    def test_unresolved_trade_keeps_capital_occupied(self):
        first=dict(status='EXECUTION_GAP',entry_time=0,execution_tf='5m',entry_regime='BEARISH')
        second=dict(status='CLOSED',entry_time=m.HOUR,exit_time_upper=2*m.HOUR,net_pct=1,holding_minutes_upper=60,execution_tf='1m',entry_regime='BEARISH')
        result=m.portfolio([first,second]);self.assertEqual(result['entries'],1);self.assertEqual(result['overlap_skipped'],1)
        self.assertFalse(result['account_return_complete'])

class IntrabarTests(unittest.TestCase):
    def test_preview_matches_existing_kernels_without_committing_partial_hours(self):
        dmi={};rsi={}
        for i in range(30):
            row=dict(high=102+i*.2,low=99+i*.15,close=100+i*.1)
            calculate_dmi(dmi,row,10,10);calculate_rsi(rsi,row['close'],7)
        state=(dmi['atr']['value'],dmi['plus']['value'],dmi['minus']['value'],*dmi['previous'],rsi['gain']['value'],rsi['loss']['value'])
        original=deepcopy((dmi,rsi))
        for h,l,c in [(108,103,106),(109,102,105),(110,101,109)]:
            got=intra.preview(state,h,l,c);d,r=deepcopy(original)
            dp,dm,_=calculate_dmi(d,dict(high=h,low=l,close=c),10,10);rs=calculate_rsi(r,c,7)
            for actual,expected in zip(got,(dp,dm,rs)):self.assertAlmostEqual(actual,expected,12)
        self.assertEqual((dmi,rsi),original,'preview must not advance the permanent hourly recurrence')

    def test_plateaus_after_a_decline_do_not_manufacture_new_peaks(self):
        detector=intra.Peak();events=[]
        for i,s in enumerate([45,50,50,49,49,48]):
            event=detector.step(((i+1)*intra.STEP,5,s+5,15))
            if event:events.append(event)
        self.assertEqual(len(events),1);self.assertEqual(events[0][2],55)

    def test_forming_hour_di_plus_is_only_available_after_its_5m_close(self):
        from array import array
        rows=[hourly(0),hourly(1,direction='BULLISH')]
        known=array('q',[m.HOUR,m.HOUR+intra.STEP]);values=array('d',[10,80])
        context=intra.PreviewContext(rows,known,values)
        self.assertEqual(context.at(m.HOUR+intra.STEP-1),('BEARISH',10))
        self.assertEqual(context.at(m.HOUR+intra.STEP),('BEARISH',80))

if __name__=='__main__':unittest.main()
