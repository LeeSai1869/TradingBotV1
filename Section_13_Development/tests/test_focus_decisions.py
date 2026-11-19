"""Non-owner live service must not become a second historical decision writer."""
import unittest
from unittest.mock import patch
import test_di_decisions as fixtures
from Section_8_Decision_Engine import processor


class FocusDecisionMemory(unittest.TestCase):
    setUp=fixtures.DiMemoryTests.setUp
    seed=fixtures.DiMemoryTests.seed

    def test_large_turn_allowance_respects_the_public_reader_page_limit(self):
        self.seed()
        self.assertEqual(processor._advance('ETHUSDT','1m',limit=100000),1)
        self.assertFalse(processor.pending_history('ETHUSDT',['1m']))

    def test_long_tail_waits_for_bulk_owner_and_checkpoint_completion_is_readable(self):
        self.seed()
        self.assertTrue(processor.pending_history('ETHUSDT',['1m']))
        processor._advance('ETHUSDT','1m')
        self.assertFalse(processor.pending_history('ETHUSDT',['1m']))
        self.seed([fixtures.di(20,25)]*20,times=[i*60000 for i in range(3,23)])
        prior=processor._load('ETHUSDT','1m')['last']
        self.assertEqual(processor._advance('ETHUSDT','1m',recent_only=True),0)
        self.assertEqual(processor._advance('ETHUSDT','1m',limit=5,recent_only=True),0)
        self.assertEqual(processor._load('ETHUSDT','1m')['last'],prior)
        self.assertTrue(processor.pending_history('ETHUSDT',['1m']))
        self.assertEqual(processor._advance('ETHUSDT','1m'),20)
        self.assertFalse(processor.pending_history('ETHUSDT',['1m']))

    def test_owner_gets_its_own_rotation_after_bounded_recent_service(self):
        seen=[];clock=[0.]
        def advance(s,t,*args,**kwargs):
            seen.append((s,t,kwargs.get('recent_only',False)))
            if kwargs.get('recent_only'):clock[0]+=.3
            return 0
        with patch.object(processor,'_cursor',7),patch.object(processor,'_bulk_cursor',0),patch.object(processor.time,'monotonic',side_effect=lambda:clock[0]),patch.object(processor,'_advance',side_effect=advance),patch('Section_1_Global_Core.global_packet.recover_decision_evidence'):
            processor.maintenance(['BTC','ETH','SUI'],['1h'],bulk_symbol='BTC',time_budget=1)
        self.assertEqual(seen,[('SUI','1h',True),('BTC','1h',False)])

    def test_small_recent_tail_still_advances_while_another_coin_owns_history(self):
        self.seed();processor._advance('ETHUSDT','1m')
        self.seed([fixtures.di(20,25)]*2,times=[180000,240000])
        self.assertEqual(processor._advance('ETHUSDT','1m',recent_only=True),2)
        self.assertFalse(processor.pending_history('ETHUSDT',['1m']))

    def test_recent_interruption_longer_than_twelve_bars_recovers_without_bulk_ownership(self):
        self.seed();processor._advance('ETHUSDT','1m')
        self.seed([fixtures.di(20,25)]*20,times=[i*60000 for i in range(3,23)])
        with patch.object(processor.time,'time',return_value=24*60):
            self.assertEqual(processor._advance('ETHUSDT','1m',recent_only=True),20)
        self.assertFalse(processor.pending_history('ETHUSDT',['1m']))


if __name__=='__main__':unittest.main()
