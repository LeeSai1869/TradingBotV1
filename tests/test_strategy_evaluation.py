import unittest
from evaluate_strategy import study


def bars():
    values=[(10,30,20,99),(11,35,21,100),(15,27,22,101),(16,26,23,110),(17,25,24,120)]
    return [dict(open_time=i*60000,close_time=(i+1)*60000-1,open=100 if i==3 else close,
                 close=close,di_plus=p,di_minus=m,di_spread=abs(p-m),adx=adx) for i,(p,m,adx,close) in enumerate(values)]


class EvaluationTests(unittest.TestCase):
    def test_next_bar_entry_horizon_and_cost_no_lookahead(self):
        result=study(bars(),(1,2),cost_bps=10)
        self.assertEqual(result['buy_signals'],1)
        self.assertEqual(result['horizons']['1']['observations'],1)
        self.assertAlmostEqual(result['horizons']['1']['mean_return_pct'],9.9)
        self.assertAlmostEqual(result['horizons']['2']['mean_return_pct'],19.9)

    def test_gap_excludes_future_returns_and_tail_is_not_fabricated(self):
        rows=bars();rows[3]['open_time']+=1
        self.assertEqual(study(rows,(1,))['horizons']['1']['observations'],0)
        self.assertEqual(study(bars()[:3],(1,))['horizons']['1']['observations'],0)
