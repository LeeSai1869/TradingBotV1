"""Gross fills, causal routing and protection order for the breakout experiment."""
import unittest
from Section_12_Research.reports.DI50_breakout_exit_routing_v1 import study as s


def position():
    p=dict(entry=100*(1+s.SLIP),entry_open=100)
    p['stop_price']=s.exits.trigger_price(p,-.5,s.FEE,s.SLIP)
    return p


def bar(t,o,h,l,c,step=60000):
    return dict(open_time=t,close_time=t+step-1,open=o,high=h,low=l,close=c)


def five_rows():
    rows=[]
    for i in range(14):
        r=bar(i*s.STEP5,100,100.1,99.9,100,s.STEP5)
        r.update(feature_valid=True,features=dict(measurement_config_id='same',relative_volume=2,candle_range_atr=2))
        rows.append(r)
    rows[-1].update(open=100,high=100.8,low=99.9,close=100.75)
    return rows


class ExitRouting(unittest.TestCase):
    def test_gross_target_fill_and_net_costs(self):
        for gross in (.5,1):
            p=position();target=s.exits.trigger_price(p,s.net_equivalent(gross),s.FEE,s.SLIP)
            self.assertAlmostEqual(target,100*(1+gross/100))
            self.assertAlmostEqual(s.net_return(target,p['entry']),s.net_equivalent(gross))
            self.assertLess(s.net_equivalent(gross),gross)

    def test_gate_only_after_closed_five_minute_bar_and_holds_level(self):
        rows=five_rows();obs=s.Observations(rows,0,'same');known=rows[-1]['close_time']+1
        self.assertFalse(obs.gate('volume_breakout',known-1,100.75,{})[0])
        self.assertTrue(obs.gate('volume_breakout',known,100.75,{})[0])
        self.assertFalse(obs.gate('volume_breakout',known,99.8,{})[0])
        self.assertFalse(obs.gate('volume_breakout',known+s.STEP5,100.75,{})[0])
        prefix=s.Observations(rows[:-1],0,'same')
        self.assertEqual(prefix.at(known-1),obs.at(known-1))

    def test_missing_or_incompatible_features_cannot_fire(self):
        rows=five_rows();known=rows[-1]['close_time']+1
        self.assertFalse(s.Observations(rows,0,'different').gate('volume_breakout',known,101,{})[0])
        rows[-1]['feature_valid']=False
        self.assertFalse(s.Observations(rows,0,'same').gate('volume_breakout',known,101,{})[0])

    def test_initial_stop_before_any_rebound_is_retained(self):
        p=position();result=s.protect_walk(p,bar(0,100,100.6,99.5,100.2),[],'low_first')
        self.assertEqual(result['reason'],'HARD_STOP');self.assertFalse(p.get('protected',False))
        self.assertAlmostEqual(s.net_return(result['raw_price'],p['entry']),-.5)

    def test_protection_requires_actual_crossing_then_can_exit_same_bar(self):
        p=position();result=s.protect_walk(p,bar(0,100,100.6,99.5,100.2),[],'high_first')
        self.assertTrue(p['protected']);self.assertEqual(s.net_return(result['raw_price'],p['entry']),0)
        self.assertEqual(result['precision'],'WITHIN_CANDLE_UNKNOWN')
        q=position();self.assertIsNone(s.protect_walk(q,bar(0,100,100.49,99.8,100.2),[],'high_first'))
        self.assertFalse(q.get('protected',False));self.assertAlmostEqual(q['stop_price'],position()['stop_price'])

    def test_adverse_gap_is_not_clipped_to_breakeven(self):
        p=position();self.assertIsNone(s.protect_walk(p,bar(0,100,100.6,100,100.4),[],'low_first'))
        result=s.protect_walk(p,bar(60000,99,99.5,98.9,99.2),[],'low_first')
        self.assertEqual(result['raw_price'],99);self.assertLess(s.net_return(result['raw_price'],p['entry']),-.5)

    def test_future_breakout_cannot_cancel_already_filled_quick_exit(self):
        start=900000;rows=[bar(0,100,100,100,100,900000),bar(start,100,101,99.9,100.6,900000)]
        rows[0]['context']={'REGIME':dict(data_quality='VALID',classification=dict(direction='BEARISH'))}
        class Execution:
            until=start+119999
            def bars(self,opened,tf):
                yield [start,start+59999,100,100.6,99.9,100.4]
                yield [start+60000,start+119999,100.4,102,100.3,101.8]
        class Future:
            def gate(self,name,t,price,info):return t>start,dict(known=start+60000)
        trace=s.simulate(rows,0,Execution(),Future(),{},s.Policy('test',target=.5,gate='volume_breakout'),'low_first','1m')
        self.assertEqual(trace['reason'],'TAKE_PROFIT');self.assertFalse(trace['selected_breakout'])
        self.assertAlmostEqual(trace['gross_reference_pct'],.5)

    def test_post_stop_fallback_does_not_hide_missing_initial_minutes(self):
        class Execution:
            until=3600000
            def bars(self,start,tf):
                if tf=='1m':return
                step=300000 if tf=='5m' else 900000
                for t in range(start,self.until,step):yield [t,t+step-1,100,102,99,101]
        r=s.post_stop(Execution(),dict(exit_time_upper=60000,execution_tf='1m',entry_open=100),horizon=30)
        self.assertFalse(r['horizons']['15']['complete']);self.assertGreater(r['initial_missing_minutes'],0)


if __name__=='__main__':unittest.main()
