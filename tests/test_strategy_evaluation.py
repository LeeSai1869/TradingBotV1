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

    def test_recent_window_preserves_gate_warmup_and_reports_gross_and_sides(self):
        result=study(bars(),(1,2),cost_bps=10,since_ms=180000)
        self.assertEqual(result['buy_signals'],1)
        self.assertEqual(result['bars_scanned'],5)
        self.assertEqual(result['bars'],3)
        long=result['by_side']['BUY']['1'];short=result['by_side']['SELL']['1']
        self.assertEqual(long['observations'],1);self.assertEqual(short['observations'],0)
        self.assertAlmostEqual(long['mean_gross_return_pct'],10)
        self.assertAlmostEqual(long['mean_return_pct'],9.9)
        self.assertAlmostEqual(long['break_even_round_trip_cost_bps'],1000)
        self.assertEqual(result['first_signal_available_ms'],180000)

    def test_until_does_not_credit_later_exits_or_signals_at_the_boundary(self):
        result=study(bars(),(1,2),until_ms=240000)
        self.assertEqual(result['horizons']['1']['observations'],1)
        self.assertEqual(result['horizons']['2']['observations'],0)
        self.assertEqual(result['last_outcome_available_ms'],240000)
        self.assertEqual(study(bars(),(1,),until_ms=180000)['buy_signals'],0)

    def test_split_purges_crossing_events_instead_of_leaking_later_returns(self):
        result=study(bars(),(1,2),split_ms=240000)
        self.assertEqual(result['periods']['earlier']['horizons']['1']['observations'],1)
        self.assertEqual(result['periods']['earlier']['horizons']['2']['observations'],0)
        self.assertEqual(result['split_purged_events'],1)
        self.assertEqual(result['horizons']['2']['observations'],0)

    def test_signal_at_split_belongs_to_later_period_and_cost_does_not_change_signals(self):
        result=study(bars(),(1,2),split_ms=180000,cost_bps=10)
        self.assertEqual(result['periods']['later']['horizons']['1']['observations'],1)
        self.assertEqual(result['periods']['earlier']['horizons']['1']['observations'],0)
        self.assertEqual(result['buy_signals'],study(bars(),(1,),cost_bps=0)['buy_signals'])

    def test_dates_are_explicit_and_invalid_parameters_fail_without_data(self):
        from evaluate_strategy import timestamp
        self.assertEqual(timestamp('2026-10-01'),timestamp('2026-10-01T00:00:00Z'))
        for kwargs in (dict(cost_bps=float('nan')),dict(since_ms=10,until_ms=5),dict(split_ms=10,since_ms=20)):
            with self.assertRaises(ValueError):study([],**kwargs)

    def test_sell_returns_are_reported_with_short_direction_not_long_direction(self):
        rows=bars()
        for row in rows:
            row['di_plus'],row['di_minus']=row['di_minus'],row['di_plus']
            row['open']=200-row['open'];row['close']=200-row['close']
        result=study(rows,(1,2),cost_bps=10)
        self.assertEqual(result['sell_signals'],1);self.assertEqual(result['buy_signals'],0)
        self.assertEqual(result['by_side']['BUY']['1']['observations'],0)
        self.assertAlmostEqual(result['by_side']['SELL']['1']['mean_return_pct'],9.9)

    def test_compact_report_keeps_periods_and_unknown_values_explicit(self):
        from evaluate_strategy import summary
        report=dict(round_trip_cost_bps=12,warning='Not a portfolio',pairs=[dict(symbol='BTCUSDT',interval='5m',**study(bars(),(1,),split_ms=180000))])
        text=summary(report)
        self.assertIn('earlier',text);self.assertIn('later',text)
        self.assertIn('BUY',text);self.assertIn('SELL',text);self.assertIn('unknown',text)
