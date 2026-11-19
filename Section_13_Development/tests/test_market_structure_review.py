import unittest
from test_complete_conversion import bar
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import memory

class MarketStructureReview(unittest.TestCase):
    def test_first_swings_confirm_without_inventing_opposite_confirmed_pivot(self):
        e=Engine('ETHUSDT','1m')
        e.step(bar(0,10,high=11,low=9))
        p=e.step(bar(1,12,high=13,low=11))
        self.assertIsNone(p['latest_confirmed_pivot_low'])
        self.assertEqual(e.context.persistent['swingHighPriceArray'],[])
        e.step(bar(2,10,high=12,low=9))
        self.assertEqual(e.context.persistent['swingHighPriceArray'],[13])
        self.assertEqual(e.context.persistent['swingLowPriceArray'],[])
        e.step(bar(3,12,high=13,low=10))
        self.assertEqual(e.context.persistent['swingLowPriceArray'],[9])
        self.assertEqual(e.context.persistent['swingHighPriceArray'],[13])

    def test_foundations_seed_once_while_waiting_for_structure(self):
        e=Engine('ETHUSDT','1m');memory.update(e.context)
        for side,values in [('High',[15,16]),('Low',[5,6])]:
            for field,items in [('Price',values),('Bar',[0,1]),('Time',[0,60000])]:
                e.context.persistent['swing'+side+field+'Array'][:]=items
        for i in range(12):e.step(bar(i,10,high=11,low=9))
        self.assertEqual(len(e.context.persistent['structurePivotHigh']),2)
        self.assertEqual(len(e.context.persistent['structurePivotLow']),2)

    def test_bos_completion_resets_and_does_not_increment_every_bar(self):
        e=Engine('ETHUSDT','1m');e.step(bar(0,10,high=11,low=9))
        e.context.persistent['activeBOS']=2;e.context.persistent['activeBOSType']='bullishBOS'
        e.step(bar(1,10,high=11,low=9))
        self.assertEqual(e.context.persistent['bullBOSCount'],1)
        self.assertEqual(e.context.persistent['activeBOS'],0)
        for i in range(2,8):e.step(bar(i,10,high=11,low=9))
        self.assertEqual(e.context.persistent['bullBOSCount'],1)

    def test_actual_swings_establish_bull_bear_and_range_without_duplicate_pivots(self):
        import math
        observed=set()
        for trend in (0,.2,-.2):
            e=Engine('ETHUSDT','1m')
            for i in range(500):
                p=e.step(bar(i,300+math.sin(i/9)*14+i*trend));observed.add(p['current_structure'])
                for side in ('High','Low'):
                    indices=e.context.persistent['structurePivot'+side+'Bar']
                    self.assertEqual(len(indices),len(set(indices)))
        self.assertLessEqual({'STRUCTURE_BULL','STRUCTURE_BEAR','STRUCTURE_RANGE'},observed)

    def test_invalid_pivot_transition_confirms_from_actual_swings(self):
        import ast,inspect
        from Section_4_Features.features import market_structure
        from Section_4_Features.execution import runtime as rt
        tree=ast.parse(inspect.getsource(market_structure.update))
        blocks=[n for n in tree.body[0].body if isinstance(n,ast.If) and "e['activeTransition']" in ast.unparse(n.test) and 'confirmedHighIndex' in ast.unparse(n)]
        self.assertEqual(len(blocks),1)
        e=dict(activeTransition=1,validPivotHigh=False,validPivotLow=False,lastConfirmedPivotType=1,
               swingHighBarArray=[2],structurePivotHighBar=[0],candidateTransitionHighBar=2,
               candidateTransitionHigh=15,structureTransition=[],activeTransitionType='bullishTransition')
        exec(compile(ast.fix_missing_locations(ast.Module(body=blocks,type_ignores=[])),'transition-confirmation','exec'),{'e':e,'rt':rt})
        self.assertEqual(e['structureTransition'],['bullishTransition'])
        self.assertEqual(e['activeTransition'],0)
