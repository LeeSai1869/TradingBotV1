import ast
import json
import unittest
from Section_4_Features.features import support_resistance as sr
from Section_4_Features.execution import zone_lifecycle as zones
from Section_4_Features.execution import runtime as rt
from Section_4_Features.execution.components import Catalog,desired_parameters
from Section_4_Features.execution.context import Context
from Section_4_Features.execution import memory

class SRLifecycleTests(unittest.TestCase):
    def test_changes_record_only_changed_zones_and_reversible_removals(self):
        a={'side':'support','low':1,'high':2,'institutional':False}
        self.assertEqual(zones.changes({'a':a},{'a':a}),'[]')
        self.assertEqual(json.loads(zones.changes({'a':a},{})),[dict(id='a',removed=True,before=a)])
        changed={**a,'low':.5}
        event=json.loads(zones.changes({'a':a},{'a':changed}))[0]
        self.assertEqual(event['before'],a);self.assertEqual(event['low'],.5)

    def test_institutional_bounds_use_dynamic_identity_not_institutional_index(self):
        e=Context('ETHUSDT','1m');memory.update(e)
        for side in ('support','resistance'):
            e[side+'ZoneIDArray']=[side+'-other',side+'-a']
            e[side+'LowArray']=[1,10]
            e[side+'HighArray']=[2,12]
            e['inst'+side.title()+'ZoneIDArray']=[side+'-a']
            e['nearestInst'+side.title()+'ZoneID']=side+'-a'
        zones.update(e)
        self.assertEqual(e['instSupportZoneLow'],10)
        self.assertEqual(e['instResistanceZoneHigh'],12)
        self.assertEqual(len(json.loads(e['srZoneEvents'])),4)
        zones.update(e);self.assertEqual(e['srZoneEvents'],'[]')

    def test_removal_loops_descend_and_parallel_arrays_stay_aligned(self):
        import inspect
        tree=ast.parse(inspect.getsource(sr))
        loops=[n for n in ast.walk(tree) if isinstance(n,ast.For) and any(isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr=='arr_remove' for c in ast.walk(n))]
        # The invalidation loops remove the current i. Merge loops remove a
        # fixed latest index after scanning and need not descend.
        for node in loops:
            if "e['i']"==ast.unparse(node.target) and any('LowArray' in ast.unparse(c) and "e['i']" in ast.unparse(c) for c in ast.walk(node) if isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr=='arr_remove'):
                self.assertIn('arr_size',ast.unparse(node.iter.args[0]))
                self.assertEqual(ast.literal_eval(node.iter.args[1]),0)
        arrays=[[1,2,3,4],['a','b','c','d']]
        for i in rt.inclusive(len(arrays[0])-1,0):
            for a in arrays:rt.arr_remove(a,i)
        self.assertEqual(arrays,[[],[]])
        self.assertTrue(rt.is_na(rt.normalize(rt.NA,0,1)))
        self.assertTrue(rt.is_na(rt.normalize(1,rt.NA,rt.NA)))

    def test_new_display_export_does_not_invalidate_other_formulas(self):
        c=Catalog();old={k:v for k,v in c.source.items() if '.zone_lifecycle:' not in k}
        p=c.plan(c.changed(old,desired_parameters(),desired_parameters()))
        self.assertEqual(p.columns,{'sr_zone_events','inst_support_zone_low','inst_support_zone_high','inst_resistance_zone_low','inst_resistance_zone_high'})
        self.assertNotIn('ema50',p.columns);self.assertNotIn('adx',p.columns)

    def test_institutional_touch_normalization_uses_selected_institutional_id(self):
        import inspect
        tree=ast.parse(inspect.getsource(sr.update))
        assignments=[n for n in tree.body[0].body if isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='rt.normalize' and any(ast.unparse(t) in {f"e['inst{s}{k}Normalized']" for s in ('Support','Resistance') for k in ('WT','ST')} for t in n.targets)]
        self.assertEqual(len(assignments),4)
        e={'normalizationPower':1}
        for side in ('Support','Resistance'):
            low=side.lower()
            e.update({low+'ZoneIDArray':['dynamic','institutional'],low+'TouchArray':[100,8],low+'StrongRejectArray':[90,3],
                      'nearestInst'+side+'ZoneID':'institutional','nearest'+side+'WeakTouches':10,'nearest'+side+'StrongTouches':90,
                      'minInst'+side+'WeakTouches':0,'maxInst'+side+'WeakTouches':10,'minInst'+side+'StrongTouches':0,'maxInst'+side+'StrongTouches':6})
        exec(compile(ast.fix_missing_locations(ast.Module(body=assignments,type_ignores=[])),'institutional-normalization','exec'),{'e':e,'rt':rt})
        for side in ('Support','Resistance'):
            self.assertEqual(e['inst'+side+'WTNormalized'],.5)
            self.assertEqual(e['inst'+side+'STNormalized'],.5)

    def test_selective_plan_compilation_is_reused_without_changing_formula_sources(self):
        c=Catalog();sources=dict(c.source)
        dirty={u.id for u in c.units if u.module.endswith('.zone_lifecycle')}
        first=c.plan(dirty);second=c.plan(set(dirty))
        self.assertIs(first,second)
        self.assertIsNot(first,Catalog().plan(dirty))
        self.assertEqual(sources,c.source)
