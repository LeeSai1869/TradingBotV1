import unittest
from Section_8_Decision_Engine import btc_sell_rules as rules
from Section_8_Decision_Engine.btc_research import context


def ctx(plus,minus):return context(dict(di_plus=plus,di_minus=minus))


class ControlledSellRules(unittest.TestCase):
    def setUp(self):self.state=rules.initial_state(ctx(10,40));self.config=rules.SellConfig()

    def test_early_peak_arms_only_and_never_disarms(self):
        state,notes,exit=rules.evaluate(self.state,ctx(30,20),ctx(35,20),True,self.config)
        self.assertIsNone(exit);self.assertTrue(state['trailing_armed'])
        self.assertEqual([n['type'] for n in notes if n['rule_id']==rules.EARLY_TRAIL],['EARLY_SELL_SETUP','TRAIL_ARMED'])
        later,notes,exit=rules.evaluate(state,ctx(40,20),ctx(30,20),False,self.config)
        self.assertTrue(later['trailing_armed']);self.assertIsNone(exit)
        self.assertFalse(self.state['trailing_armed']) # pure, caller input unchanged

    def test_strict_40_boundary_then_any_decrease_without_three_bar_delay(self):
        state,_,exit=rules.evaluate(self.state,ctx(50,10),ctx(49,10),False,self.config)
        self.assertFalse(state['spread_mature']);self.assertIsNone(exit)
        state,notes,exit=rules.evaluate(state,ctx(51,10),ctx(50,10),False,self.config)
        self.assertTrue(state['spread_mature']);self.assertIsNone(exit)
        state,_,exit=rules.evaluate(state,ctx(51,10),ctx(51,10),False,self.config)
        self.assertIsNone(exit) # plateau
        state,notes,exit=rules.evaluate(state,ctx(50.999,10),ctx(51,10),False,self.config)
        self.assertEqual(exit,rules.MATURITY)
        self.assertTrue(any(n['type']=='BULLISH_SPREAD_DECREASE' for n in notes))

    def test_bearish_spread_is_not_bullish_maturity(self):
        state,notes,exit=rules.evaluate(self.state,ctx(10,60),ctx(10,61),False,self.config)
        self.assertFalse(state['spread_mature']);self.assertIsNone(exit)
        state,notes,exit=rules.evaluate(state,ctx(55,10),ctx(10,60),False,self.config)
        self.assertTrue(state['spread_mature']);self.assertIsNone(exit) # new maturity, not old bearish decline

    def test_control_loss_requires_actual_gain_after_below_both_entry(self):
        state,_,exit=rules.evaluate(self.state,ctx(11,35),ctx(10,40),False,self.config)
        self.assertFalse(state['control_gained']);self.assertIsNone(exit)
        state,_,_=rules.evaluate(state,ctx(30,20),ctx(11,35),False,self.config)
        self.assertTrue(state['control_gained'])
        state,notes,exit=rules.evaluate(state,ctx(20,21),ctx(30,20),False,self.config)
        self.assertEqual(exit,rules.CONTROL)
        self.assertEqual(next(n for n in notes if n['type']=='BUYER_CONTROL_LOST')['crossed'],['DI_MINUS'])

    def test_other_entry_scenario_has_no_accidental_control_exit(self):
        state=rules.initial_state(ctx(20,30))
        state,_,_=rules.evaluate(state,ctx(30,20),ctx(20,30),False,self.config)
        state,_,exit=rules.evaluate(state,ctx(20,30),ctx(30,20),False,self.config)
        self.assertEqual(state['entry_scenario'],'OTHER');self.assertIsNone(exit)

    def test_all_matching_evidence_retained_with_fixed_priority(self):
        state=dict(self.state,spread_mature=True,control_gained=True)
        state,notes,exit=rules.evaluate(state,ctx(20,21),ctx(60,10),False,self.config)
        self.assertEqual(exit,rules.MATURITY)
        self.assertEqual({n['rule_id'] for n in notes if n['action']=='EXIT'},{rules.MATURITY,rules.CONTROL})

    def test_each_rule_can_be_disabled_for_controlled_comparisons(self):
        config=rules.SellConfig(enabled=())
        state,notes,exit=rules.evaluate(self.state,ctx(60,10),ctx(65,10),True,config)
        self.assertFalse(notes);self.assertIsNone(exit);self.assertEqual(state,self.state)
        with self.assertRaises(ValueError):rules.SellConfig(enabled=('invented',))
