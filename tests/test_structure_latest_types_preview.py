"""Demonstrate the stale-label defect and validate a staged correction, without replaying live features."""
import ast
import inspect
from pathlib import Path
import unittest
from Section_4_Features.features import market_structure
from Section_4_Features.execution import runtime as rt

class LatestStructureTypes(unittest.TestCase):
    def classify(self,count,high,low,*,corrected):
        source=inspect.getsource(market_structure.update)
        if corrected:
            for name in ('highPivotCount','lowPivotCount'):
                old=f"rt.binary('==', e['{name}'], 2)"
                self.assertEqual(source.count(old),1)
                source=source.replace(old,f"rt.binary('>=', e['{name}'], 2)")
        tree=ast.parse(source);body=tree.body[0].body
        start=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and "e['highPivotCount']"==ast.unparse(n.targets[0]))
        end=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and "e['newStructureEstablished']"==ast.unparse(n.targets[0]))
        env=dict(structureHighsCount=list(range(count)),structureLowsCount=list(range(count)),
                 structureHighType=['HH']*(count-1)+[high],structureLowType=['HL']*(count-1)+[low],structureState=['STRUCTURE_BULL'])
        exec(compile(ast.fix_missing_locations(ast.Module(body=body[start:end+1],type_ignores=[])),'actual-structure-classifier','exec'),dict(e=env,rt=rt))
        return env
    def test_third_and_later_swings_previously_could_not_refresh_structure(self):
        for count in (3,4,20):
            old=self.classify(count,'LH','LL',corrected=False)
            self.assertFalse(old['newStructureEstablished'])
            new=self.classify(count,'LH','LL',corrected=True)
            self.assertTrue(new['newStructureEstablished']);self.assertEqual(new['structureEstablished'],'STRUCTURE_BEAR')
    def test_two_pivot_foundation_and_bull_range_behavior_preserved(self):
        for count in (2,3,7):
            for high,low,label in [('HH','HL','STRUCTURE_BULL'),('LH','LL','STRUCTURE_BEAR'),('EH','EL','STRUCTURE_RANGE')]:
                self.assertEqual(self.classify(count,high,low,corrected=True)['structureEstablished'],label)
        self.assertEqual(self.classify(2,'LH','LL',corrected=False)['structureEstablished'],'STRUCTURE_BEAR')
    def test_correction_is_staged_not_installed_in_feature_producer(self):
        patch=Path('research_fixes/structure_latest_types.patch').read_text()
        self.assertEqual(patch.count("+    if rt.truth(rt.binary('>=',"),2)
        self.assertIn("rt.binary('==', e['highPivotCount'], 2)",inspect.getsource(market_structure.update))
