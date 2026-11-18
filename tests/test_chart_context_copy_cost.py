"""Optimized page lifecycles preserve reference results and frozen snapshots."""
import copy
import random
import unittest
from unittest.mock import patch
from Section_1_Global_Core import analysis
from Section_10_Opportunity_Engine import context
from test_analysis_context import bar,f


class ChartContextCopies(unittest.TestCase):
    def test_full_page_matches_immutable_reference_with_gaps_and_missing_features(self):
        for history in (False,True):
            rows=[bar(i,100+(i%11),('BUY' if i%80==0 else 'SELL' if i%80==40 else None)) for i in range(240)]
            rows[20]['features']={'formula_version':1}
            rows[90]['open_time']+=1
            expected=copy.deepcopy(rows)
            with patch.object(analysis,'advance',context.advance):
                analysis.annotate(expected,now_ms=10**9,context_history=history)
            analysis.annotate(rows,now_ms=10**9,context_history=history)
            self.assertEqual(rows,expected)

    def test_owned_lifecycle_matches_reference_after_stop_and_target_transitions(self):
        seed=context.anchor(analysis.opportunity(100,f()),side='BUY',open_time=0)
        for pattern in ('rise','fall','flat'):
            expected=copy.deepcopy(seed);actual=copy.deepcopy(seed)
            for i in range(1,160):
                price=100+i/5 if pattern=='rise' else 100-i/5 if pattern=='fall' else 100
                candle=bar(i,price)
                expected=context.advance(expected,candle)
                actual=context._advance_owned(actual,candle)
                self.assertEqual(actual,expected)

    def test_retained_snapshots_and_seed_remain_deeply_independent(self):
        rows=[bar(0,100,'BUY'),bar(1,101),bar(2,102),bar(3,103)]
        analysis.annotate(rows,now_ms=10**9,context_history=True)
        first=copy.deepcopy(rows[0]['signal_context'])
        rows[-1]['signal_context']['plan']['targets'].append({'price':999})
        rows[-1]['signal_context']['area_map'].clear()
        self.assertEqual(rows[0]['signal_context'],first)
        seed=copy.deepcopy(first);original=copy.deepcopy(seed)
        analysis.annotate([bar(4,110),bar(5,120)],seed=seed,now_ms=10**9)
        self.assertEqual(seed,original)
