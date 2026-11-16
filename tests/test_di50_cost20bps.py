"""User's fixed round-trip costs, net loss budget and causal protection."""
import unittest
from research_reports.DI50_breakout_exit_routing_cost20bps import study as s
from research_reports.DI50_breakout_exit_routing_v1.study import Policy


START=900000


class Execution:
    def __init__(self,bars):
        self.prices=[[START+i*60000,START+(i+1)*60000-1,*b] for i,b in enumerate(bars)];self.until=self.prices[-1][1]
    def bars(self,start,tf):yield from self.prices


class Context:
    def __init__(self,direction='BEARISH',plus=60):self.direction=direction;self.plus=plus
    def at(self,t):return self.direction,self.plus


def trade(bars,policy=None,order='low_first',context=None):
    rows=[dict(open_time=0,close_time=START-1,context={}),dict(open_time=START,open=100)]
    obs=s.FrozenObservations(dict(values=[]),START)
    return s.simulate(rows,0,Execution(bars),obs,{},policy or Policy('fixed',target=.5),order,'1m',context or Context())


class CostCorrection(unittest.TestCase):
    def test_user_cost_arithmetic_and_break_even(self):
        self.assertAlmostEqual(s.net_pct(100.5,100),.3)
        self.assertAlmostEqual(s.net_pct(101,100),.8)
        self.assertAlmostEqual(s.net_pct(100,100),-.2)
        self.assertAlmostEqual(.5/(.3+.5)*100,62.5)
        self.assertAlmostEqual(s.level(100,-.5),99.7)
        self.assertAlmostEqual(s.level(100,0),100.2)

    def test_gross_profit_and_net_stop_are_distinct(self):
        win=trade([(100,100.6,99.8,100.5)])
        self.assertEqual(win['reason'],'TAKE_PROFIT');self.assertAlmostEqual(win['net_pct'],.3)
        loss=trade([(100,100.6,99.6,100.5)])
        self.assertEqual(loss['reason'],'HARD_STOP');self.assertAlmostEqual(loss['net_pct'],-.5)
        self.assertAlmostEqual(loss['exit_reference'],99.7)

    def test_net_control_keeps_one_percent_after_cost(self):
        t=trade([(100,101.3,99.8,101.25)],Policy('net',basis='net'))
        self.assertAlmostEqual(t['exit_reference'],101.2);self.assertAlmostEqual(t['net_pct'],1)

    def test_old_regime_policy_uses_corrected_cost_too(self):
        t=trade([(100,101.3,99.8,101.25)],Policy('old_regime_reference'))
        self.assertAlmostEqual(t['exit_reference'],101.2);self.assertAlmostEqual(t['net_pct'],1)
        t=trade([(100,101.3,99.8,101.25)],Policy('old_regime_reference'),context=Context('BULLISH',49))
        self.assertEqual(t['status'],'OPEN_AT_BOUNDARY')

    def test_adverse_opening_gap_is_real_loss(self):
        t=trade([(100,100.1,99.8,100),(99.5,99.6,99.4,99.5)])
        self.assertAlmostEqual(t['exit_reference'],99.5);self.assertAlmostEqual(t['net_pct'],-.7)

    def test_trail_arms_at_gross_one_percent(self):
        t=trade([(100,101.5,99.8,100.9)],Policy('all',gate='all'))
        self.assertEqual(t['reason'],'TRAILING_STOP');self.assertAlmostEqual(t['exit_reference'],101.5*.995)
        self.assertAlmostEqual(t['net_pct'],.7925)

    def test_protection_only_after_half_percent_gain(self):
        policy=Policy('protected',gate='all',protect=True)
        t=trade([(100,100.6,99.8,100.1)],policy,order='high_first')
        self.assertEqual(t['reason'],'BREAKEVEN_STOP');self.assertEqual(t['net_pct'],0.)
        t=trade([(100,100.49,99.6,100)],policy,order='high_first')
        self.assertEqual(t['reason'],'HARD_STOP');self.assertFalse(t['protected'])


if __name__=='__main__':unittest.main()
