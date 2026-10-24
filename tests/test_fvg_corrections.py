import unittest
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import runtime as rt


def bar(i,close=11,low=10,high=12):
    return dict(open_time=i*60000,close_time=(i+1)*60000-1,open=close,close=close,high=high,low=low,volume=10)


def seeded(side,*,scores=(0,),lows=(10,)):
    engine=Engine('ETHUSDT','1m',{'atrLen':1,'fvgZoneDistanceATR':100})
    engine.step(bar(0));engine.step(bar(1))
    for low,score in zip(lows,scores):
        values={'Low':low,'High':low+2,'Strength':2,'Reaction':0.,'Status':1,'CreatedBar':0,'Age':0,
                'ReactionCount':0,'LastReactionBar':rt.NA,'ReactionActive':False,'LastReactionType':0,'ReactionScore':score}
        for key,value in values.items():engine.context.persistent['fvg'+side+key].append(value)
    return engine


class FVGCorrections(unittest.TestCase):
    def test_both_directions_count_one_continuous_touch_then_allow_a_new_reaction(self):
        for side in ('Bull','Bear'):
            with self.subTest(side=side):
                engine=seeded(side);p=engine.context.persistent
                for i in (2,3):
                    engine.step(bar(i));self.assertEqual(p['fvg'+side+'ReactionCount'][0],1)
                    self.assertIs(p['fvg'+side+'ReactionActive'][0],True)
                engine.step(bar(4,14,13,15) if side=='Bull' else bar(4,8,7,9))
                self.assertIs(p['fvg'+side+'ReactionActive'][0],False)
                self.assertEqual(p['fvg'+side+'ReactionScore'][0],2)
                engine.step(bar(5))
                self.assertEqual(p['fvg'+side+'ReactionCount'][0],2)
                self.assertEqual(p['fvg'+side+'Status'][0],3)

    def test_bear_normalization_uses_its_own_bounds_and_higher_quality_scores_higher(self):
        engine=seeded('Bear',scores=(2,8),lows=(10,13))
        # Bull scores are deliberately unrelated to the bear population.
        engine.context.persistent['fvgBullReactionScore'][:]=[99]
        first=engine.step(bar(2))
        self.assertEqual(first['nearest_bear_fvg_reaction_score_normalized'],0.)
        self.assertEqual(engine.context['minBearFVGReactionScore'],2)
        self.assertEqual(engine.context['maxBearFVGReactionScore'],8)
        second=engine.step(bar(3,14,13,15))
        self.assertEqual(second['nearest_bear_fvg_reaction_score_normalized'],1.)

    def test_runtime_zero_atr_and_reverse_removal_remain_safe(self):
        self.assertTrue(rt.is_na(rt.binary('/',1,0)))
        self.assertFalse(rt.truth(rt.NA));self.assertFalse(rt.binary('<=',1,rt.NA))
        values=[0,1,2,3];visited=[]
        for i in rt.inclusive(len(values)-1,0):visited.append(values[i]);rt.arr_remove(values,i)
        self.assertEqual(visited,[3,2,1,0]);self.assertEqual(values,[])
