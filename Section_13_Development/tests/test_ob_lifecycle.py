import copy
import json
import unittest
from Section_4_Features.execution.ob_lifecycle import advance
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import checkpoint,components
from Section_4_Features.features import order_blocks
from test_complete_conversion import bar

class OBLifecycleTests(unittest.TestCase):
    def test_birth_return_promotion_and_terminal_history(self):
        birth=[(False,'bull',True,10.,12.,True,1.5)]
        zones,events=advance({},0,0,9,14,13,birth)
        identity=next(iter(zones));self.assertFalse(zones[identity]['mitigated'])
        zones,events=advance(zones,1,60,11,14,13,[])
        self.assertEqual(zones[identity]['mitigated_bar'],1)
        zones,events=advance(zones,2,120,8,13,9,[])
        terminal=next(e['terminal'] for e in json.loads(events) if e.get('removed'))
        self.assertEqual(terminal['invalidated_bar'],2)
        breaker=zones[identity+':breaker']
        self.assertTrue(breaker['origin_mitigated']);self.assertFalse(breaker['mitigated'])
        zones,events=advance(zones,3,180,10,14,13,[])
        self.assertEqual(zones,{})
        terminal=json.loads(events)[0]['terminal']
        self.assertEqual(terminal['mitigated_bar'],3);self.assertEqual(terminal['invalidated_bar'],3)

    def test_newer_blocks_do_not_replace_older_valid_blocks_and_inputs_not_mutated(self):
        zones,_=advance({},0,0,10,14,13,[(False,'bull',True,10,12,False,1)])
        saved=copy.deepcopy(zones)
        zones,_=advance(zones,1,60,13,16,15,[(False,'bull',True,13,14,False,2)])
        self.assertEqual(len(zones),2);self.assertEqual(saved['normal:bull:0']['mitigated'],False)
        unchanged,events=advance(zones,2,120,15,17,16,[])
        self.assertEqual(events,'[]');self.assertEqual(unchanged,zones)

    def test_strict_identity_and_checkpoint_roundtrip(self):
        e=Engine('ETHUSDT','1m')
        for i in range(30):e.step(bar(i,100+i%3))
        restored=checkpoint.restore('ETHUSDT','1m',checkpoint.dump(e,(0,0)),(0,0))
        actual=e.step(bar(30,104));restarted=restored.step(bar(30,104))
        self.assertEqual({k:v for k,v in actual.items() if 'ob_' in k or 'breaker' in k},{k:v for k,v in restarted.items() if 'ob_' in k or 'breaker' in k})
        zones,_=advance({},0,0,1,4,3,[(False,'bull',True,1,2,False,1),(True,'bull',True,1,2,False,1)])
        self.assertEqual(len(zones),2)

    def test_scalar_creation_and_promotion_are_not_return_touches(self):
        from Section_4_Features.execution.context import Context
        e=Context('ETHUSDT','1m')
        e.values.update(bar_index=10,directionalDisplacement=1,prevBearCandle=True,prevBullCandle=False,
            c=14,o=11,h1=13,l1=10,o1=12,l=11,h=15,displacementATR=1.5,
            candleEfficiency=.8,volumeRatio=2,prevPivotHigh=13,prevPivotLow=8,bullFVG=True,bearFVG=False,atr=2)
        order_blocks.update(e)
        self.assertTrue(e['bullOBEvent']);self.assertFalse(e['bullOBMitigated']);self.assertFalse(e['strictBullOBMitigated'])
        e.values.update(bar_index=11,directionalDisplacement=0,prevBearCandle=False,c=9,l=8,h=13)
        order_blocks.update(e)
        self.assertTrue(e['bearBreakerActive']);self.assertFalse(e['bearBreakerMitigated'])
        self.assertTrue(__import__('math').isnan(e['bullOBAge']))

    def test_ledger_repair_does_not_recompute_unrelated_formulas(self):
        c=components.Catalog()
        old={k:v for k,v in c.source.items() if 'obDisplayZones' not in k}
        plan=c.plan(c.changed(old,components.desired_parameters(),components.desired_parameters()))
        self.assertIn('ob_zone_events',plan.columns)
        self.assertNotIn('ema50',plan.columns);self.assertNotIn('adx',plan.columns);self.assertNotIn('vp_poc',plan.columns)

    def test_boolean_optimization_matches_reference_on_missing_bounds_and_promotions(self):
        import random
        from Section_4_Features.execution import fast,runtime as rt
        from Section_4_Features.execution.context import Context
        rng=random.Random(19)
        original=Context('ETHUSDT','1m');optimized=copy.deepcopy(original)
        for i in range(300):
            values=dict(bar_index=i,directionalDisplacement=rng.choice([-2,0,2,rt.NA]),
                prevBearCandle=rng.choice([True,False]),prevBullCandle=rng.choice([True,False]),
                c=rng.uniform(7,17),o=12,h1=13,l1=10,o1=12,l=8,h=16,displacementATR=1.5,
                candleEfficiency=.8,volumeRatio=2,prevPivotHigh=13,prevPivotLow=8,bullFVG=True,bearFVG=False,atr=2)
            original.values.update(values);optimized.values.update(values)
            order_blocks.update(original);fast.resolve(order_blocks,'update')(optimized)
            self.assertEqual(rt.clean(original.values),rt.clean(optimized.values))
            self.assertEqual(rt.clean(original.persistent),rt.clean(optimized.persistent))
