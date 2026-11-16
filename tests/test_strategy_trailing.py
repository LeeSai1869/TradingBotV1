"""Standing risk, net activation, causal DI gating and trailing path ambiguity."""
import copy
from datetime import datetime,timezone
import unittest

from Section_8_Decision_Engine import strategy_analyzer as a, strategy_exits as exits
from Section_8_Decision_Engine.candle_calendar import end, latest_closed

STEP=900000


def branch(condition=None,profit=1,distance=.5):
    return dict(id='trail',side='SELL',action='TRAILING_SELL',trail=dict(distance_pct=distance,activation_profit_pct=profit),
                when=condition or dict(field='price.close',op='available'))


def config(sell=None,path='low_first',fee=0,slip=0):
    return dict(version=a.VERSION,id='trailing',execution=dict(fee_bps_per_side=fee,slippage_bps_per_side=slip,intrabar_path=path),branches=[
        dict(id='buy',side='BUY',when=dict(field='feature.buy',op='eq',value=1)),sell or branch()])


def source(prices,plus=None):
    rows=[]
    for i,(o,h,l,c) in enumerate(prices):
        rows.append(dict(open_time=i*STEP,close_time=(i+1)*STEP-1,open=o,high=h,low=l,close=c,volume=10,feature_valid=True,
                         features=dict(buy=int(i==0),di_plus=plus[i] if plus else 55,di_minus=10,adx=20,measurement_gap=False)))
    return dict(version='memory-candle-source-v1',symbol='SUIUSDT',timeframe='15m',source_id='trail_fixture',observed_as_of=len(rows)*STEP,candles=rows,engine_history={})


class TrailingSell(unittest.TestCase):
    def test_trailing_sell_does_not_sell_as_soon_as_condition_is_true(self):
        p=source([(100,100.1,99.9,100),(100,102,99.8,101.8),(101.8,103,101.4,102)])
        r=a.analyze(p,config());t=r['trades'][0]
        self.assertEqual(t['exit_reason'],'TRAILING_STOP')
        self.assertAlmostEqual(t['exit'],102*.995)
        self.assertEqual(t['trail_branch'],'trail')
        self.assertEqual(len([s for s in r['signals'] if s['side']=='SELL']),1)

    def test_explicit_paths_expose_high_low_order_ambiguity(self):
        p=source([(100,100.1,99.9,100),(100,103,99,102)])
        low=a.analyze(p,config(path='low_first'))['trades'][0]
        high=a.analyze(p,config(path='high_first'))['trades'][0]
        self.assertEqual(low['exit_reason'],'HARD_STOP');self.assertAlmostEqual(low['net_pct'],-.5)
        self.assertEqual(high['exit_reason'],'TRAILING_STOP');self.assertGreater(high['net_pct'],2)

    def test_profit_and_di_condition_are_both_required_and_no_future_di(self):
        condition=dict(field='di.di_plus',op='gt',value=50)
        p=source([(100,100.1,99.9,100),(100,103,99.8,100.8),(100.8,101.5,100.7,101.4)],plus=[20,55,20])
        r=a.analyze(p,config(branch(condition)))
        t=r['trades'][0]
        self.assertEqual(t['status'],'CLOSED')
        self.assertEqual(t['trail_armed_at'],3*STEP)
        self.assertAlmostEqual(t['trail_arm_price'],101)
        self.assertAlmostEqual(t['exit'],101)
        self.assertEqual(t['trail_inputs']['di.di_plus@lag0']['value'],55)
        self.assertEqual(t['trail_condition_known_time'],2*STEP)

    def test_false_later_condition_does_not_disarm(self):
        condition=dict(field='di.di_plus',op='gt',value=50)
        p=source([(100,100.1,99.9,100),(100,102,99.8,101.8),(101.8,102,101,101.2)],plus=[55,10,10])
        t=a.analyze(p,config(branch(condition)))['trades'][0]
        self.assertEqual(t['exit_reason'],'TRAILING_STOP')
        self.assertAlmostEqual(t['exit'],101.49)

    def test_new_close_condition_cannot_retroactively_stop_inside_that_bar(self):
        condition=dict(field='di.di_plus',op='gt',value=50)
        p=source([(100,100.1,99.9,100),(100,104,99.8,101.5),(101.4,102,101.3,101.5)],plus=[10,55,10])
        t=a.analyze(p,config(branch(condition)))['trades'][0]
        self.assertEqual(t['trail_arm_time_precision'],'CONFIRMED_CLOSE')
        self.assertEqual(t['exit_time'],2*STEP)
        self.assertAlmostEqual(t['exit'],101.4)

    def test_gap_uses_actual_open_not_the_more_favorable_stop(self):
        p=source([(100,100.1,99.9,100),(100,102,99.8,101.8),(100,101,99,100)])
        t=a.analyze(p,config())['trades'][0]
        self.assertEqual(t['exit_time_precision'],'OPEN')
        self.assertEqual(t['exit'],100)

    def test_high_watermark_is_since_entry_including_before_arming(self):
        position=dict(entry=100,stop_price=99.5,peak=110)
        row=dict(open_time=0,close_time=STEP-1,open=101.5,high=102,low=101,close=101.8)
        result=exits.walk(position,row,[branch()],0,0)
        self.assertEqual(result['raw_price'],101.5)

    def test_net_activation_includes_fees_and_slippage(self):
        pos=dict(entry=100.02,stop_price=99.6)
        target=exits.trigger_price(pos,1,.0004,.0002)
        self.assertGreater(target,101)
        liquidation=target*(1-.0002)*(1-.0004)/(100.02*(1+.0004))-1
        self.assertAlmostEqual(liquidation,.01)

    def test_hard_stop_remains_active_while_waiting_for_profit(self):
        p=source([(100,100.1,99.9,100),(100,100.2,99,99.2)])
        t=a.analyze(p,config(branch(profit=5)))['trades'][0]
        self.assertEqual(t['exit_reason'],'HARD_STOP')
        self.assertAlmostEqual(t['net_pct'],-.5)

    def test_settings_validate_and_round_trip(self):
        c=config();self.assertEqual(a.validate_config(copy.deepcopy(c)),c)
        c['branches'][1]['trail']['distance_pct']=0
        with self.assertRaises(ValueError):a.validate_config(c)
        c=config();c['branches'][0].update(action='TRAILING_SELL',trail=dict(distance_pct=.5,activation_profit_pct=1))
        with self.assertRaises(ValueError):a.validate_config(c)

    def test_month_and_monday_week_boundaries(self):
        stamp=lambda s:int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()*1000)
        self.assertEqual(end(stamp('2024-02-01'),'1M'),stamp('2024-03-01'))
        self.assertEqual(latest_closed(stamp('2024-03-01'),'1M'),stamp('2024-02-01'))
        self.assertEqual(latest_closed(stamp('2024-03-06'),'1w'),stamp('2024-02-26'))
        p=source([(100,101,99.8,100),(100,101,99.8,100)])
        p['timeframe']='1M';p['candles'][0].update(open_time=stamp('2024-01-01'),close_time=stamp('2024-02-01')-1)
        p['candles'][1].update(open_time=stamp('2024-02-01'),close_time=stamp('2024-03-01')-1);p['observed_as_of']=stamp('2024-03-01')
        memory=a.Memory(p);self.assertTrue(memory.price_valid(1));self.assertEqual(memory.value(1,'price.close',1),(100,None))


if __name__=='__main__':unittest.main()
