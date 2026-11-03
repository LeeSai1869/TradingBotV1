"""Hand-calculated measurements, causal ranks, gaps and real feature integration."""
import copy
import math
import unittest
from Section_4_Features.features import shared_measurements as m
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import checkpoint
from Section_4_Features.execution.components import catalog,desired_parameters


def bar(i,close=100.):
    return dict(symbol='BTCUSDT',interval='1m',open_time=i*60000,close_time=(i+1)*60000-1,
                open=close,high=close+1,low=close-1,close=close,volume=100.)

SMALL={**m.DEFAULTS,**{k:3 for k in m.DEFAULTS if k!='measurementBBMultiplier'},'measurementMACDFast':2,'measurementMACDSlow':3}

def step(state,i,close=100.,config=SMALL,**kwargs):
    return m.calculate(state,bar(i,close),kwargs.get('plus',30.),kwargs.get('minus',10.),
        kwargs.get('atr',2.),close,close,close,kwargs.get('volume_ma',100.),config)

class SharedMeasurements(unittest.TestCase):
    def test_hand_calculated_path_bands_returns_slopes_and_units(self):
        state={}
        for i,p in enumerate((100.,102.,101.,104.)):out=step(state,i,p)
        self.assertAlmostEqual(out['efficiency_ratio'],4/6)
        self.assertEqual(out['di_signed_dominance'],.5)
        self.assertEqual(out['roc_pct'],4.)
        self.assertEqual(out['momentum_atr'],2.)
        self.assertEqual(out['ema50_slope_atr'],2.)
        self.assertAlmostEqual(out['natr_pct'],200/104)
        self.assertAlmostEqual(out['bb_middle'],307/3)
        sd=math.sqrt(sum((x-307/3)**2 for x in (102,101,104))/3)
        self.assertAlmostEqual(out['bb_stddev'],sd)
        self.assertAlmostEqual(out['bb_upper'],307/3+2*sd)
        self.assertAlmostEqual(out['bb_width_fraction'],4*sd/(307/3))
        self.assertEqual(out['positive_return_fraction'],2/3)
        returns=[math.log(102/100),math.log(101/102),math.log(104/101)];avg=sum(returns)/3
        self.assertAlmostEqual(out['realized_volatility'],math.sqrt(sum((x-avg)**2 for x in returns)/3))

    def test_rank_excludes_current_requires_full_baseline_and_midrank_ties(self):
        state={}
        for value in (1.,2.,2.):self.assertIsNone(m.rank(state,'x',value,3)[0])
        self.assertEqual(m.rank(state,'x',2.,3),(100*2/3,3,False))
        self.assertEqual(m.rank({},'x',None,3),(None,0,None))
        state={}
        for _ in range(3):m.rank(state,'x',7.,3)
        self.assertEqual(m.rank(state,'x',7.,3),(50.,3,True))
        self.assertEqual(m.rank(state,'x',None,3),(None,0,None))
        self.assertEqual(m.rank(state,'x',7.,3),(None,0,None))

    def test_flat_zero_atr_missing_data_and_gap_rewarm_are_distinct(self):
        state={}
        for i in range(8):out=step(state,i,atr=0.,plus=0.,minus=0.)
        self.assertEqual(out['efficiency_ratio'],0);self.assertTrue(out['zero_price_movement'])
        self.assertEqual(out['natr_pct'],0);self.assertEqual(out['natr_percentile'],50)
        self.assertTrue(out['natr_baseline_degenerate']);self.assertIsNone(out['momentum_atr'])
        out=step(state,8,plus=None,volume_ma=0)
        self.assertIsNone(out['di_signed_dominance']);self.assertFalse(out['relative_volume_valid']);self.assertIsNone(out['relative_volume'])
        out=step(state,10);self.assertTrue(out['measurement_gap']);self.assertEqual(out['measurement_contiguous_bars'],1)
        self.assertIsNone(out['efficiency_ratio']);self.assertIsNone(out['natr_percentile'])
        with self.assertRaises(ValueError):step(state,10)
        invalid=bar(11);invalid['close']=0
        out=m.calculate(state,invalid,30,10,2,1,1,1,100,SMALL)
        self.assertEqual(out['measurement_contiguous_bars'],0);self.assertIsNone(out['natr_pct'])

    def test_config_validation_and_config_change_rewarms(self):
        for bad in ({'measurementERLength':True},{'measurementBBMultiplier':0},{'measurementMACDFast':30}):
            with self.assertRaises(ValueError):m.validate(m.DEFAULTS|bad)
        state={}
        for i in range(7):old=step(state,i)
        out=step(state,7,config=SMALL|{'measurementBBMultiplier':3.})
        self.assertNotEqual(old['measurement_config_id'],out['measurement_config_id']);self.assertIsNone(out['bb_width_fraction'])

    def test_engine_checkpoint_preview_prefix_and_independent_pairs(self):
        engine=Engine('BTCUSDT','1m',SMALL);rows=[]
        for i in range(45):rows.append(engine.step(bar(i,100+math.sin(i/3))))
        saved=checkpoint.dump(engine,('test',));restored=checkpoint.restore('BTCUSDT','1m',saved,('test',))
        clone=copy.deepcopy(engine);clone.step(bar(45,999),is_confirmed=False)
        self.assertEqual(checkpoint.dump(engine,('test',)),saved)
        for i in range(45,52):
            expected=engine.step(bar(i,100+math.sin(i/3)))
            self.assertEqual(expected,restored.step(bar(i,100+math.sin(i/3))))
        other=Engine('ETHUSDT','1m',SMALL)
        self.assertEqual(other.step(dict(bar(0),symbol='ETHUSDT'))['measurement_contiguous_bars'],1)
        prefix=Engine('BTCUSDT','1m',SMALL)
        for i in range(45):self.assertEqual(rows[i],prefix.step(bar(i,100+math.sin(i/3))))

    def test_new_group_and_parameter_replay_do_not_change_legacy_outputs(self):
        c=catalog();params=desired_parameters();old={k:v for k,v in c.source.items() if '.shared_measurements:' not in k}
        plan=c.plan(c.changed(old,params,params))
        self.assertEqual(plan.columns,set(m.EXPORTS))
        plan=c.plan(c.changed(c.source,params,params|{'measurementERLength':30}))
        self.assertEqual(plan.columns,set(m.EXPORTS))
        self.assertFalse(any(x in plan.columns for x in ('rsi','atr','di_plus','regime_state','ema50')))

if __name__=='__main__':unittest.main()
