"""v2 production parity and safe repair of real confirmed-pair-v1 checkpoints."""
import unittest
from Section_4_Features.features import pivot_rules
import test_confirmed_pair_production as prior

class V1CheckpointRepair(prior.LegacyRuleRepair):
    fixture_name='confirmed-pair-v1-checkpoint.json.gz'

class CurrentMoveRules(unittest.TestCase):
    def test_exact_requested_geometry(self):
        state=pivot_rules.seed([.5818,.1302],1,.4802,0,0,.4802,899999)
        self.assertEqual(pivot_rules.level(state),(.3927,.35))
        first=dict(open_time=900000,close_time=1799999,high=.44,low=.42,close=.43)
        second=dict(open_time=1800000,close_time=2699999,high=.40,low=.37,close=.38)
        self.assertIsNone(pivot_rules.advance(state,first,1))
        event=pivot_rules.advance(state,second,2)
        self.assertEqual(event['price'],.4802)
        self.assertEqual(event['threshold'],.3927)
        self.assertEqual(event['reverse_closes'],2)
    def test_old_state_cannot_be_reinterpreted_without_repair(self):
        state=pivot_rules.seed([100,80],1,100,0,0,100,899999);state['version']=1
        with self.assertRaisesRegex(ValueError,'historical repair'):
            pivot_rules.advance(state,dict(open_time=900000,close_time=1799999,high=99,low=95,close=97),1)
