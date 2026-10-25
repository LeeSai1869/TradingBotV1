import ast
import copy
from collections import deque
import inspect
import random
import unittest
from unittest.mock import patch
from test_complete_conversion import bar
from Section_4_Features.execution import fast,runtime as rt,checkpoint
from Section_4_Features.execution.context import Context
from Section_4_Features.execution.engine import Engine
from Section_4_Features.features import liquidity,volume_profile

class FastExecutionTests(unittest.TestCase):
    def test_liquidity_loops_match_reference_with_missing_values_zero_prices_and_short_history(self):
        nodes=[n for n in ast.parse(inspect.getsource(liquidity.update)).body[0].body if isinstance(n,ast.For)]
        rng=random.Random(42)
        for _ in range(100):
            e=Context('ETHUSDT','1m');e.begin(bar(0,100));e.histories={'h':deque(rng.choice([None,rt.NA,99.,100.,101.]) for _ in range(rng.randrange(250))),
                'l':deque(rng.choice([None,rt.NA,99.,100.,101.]) for _ in range(rng.randrange(250)))}
            e.values.update(h=100.,l=100.,c=rng.choice([None,rt.NA,0.,100.,-2.]),externalHighLiquidity=rng.choice([None,rt.NA,100.]),
                externalLowLiquidity=rng.choice([None,rt.NA,100.]),liquidityClusterTolerance=.002,highClusterCount=0,lowClusterCount=0,
                externalLiquidityLookback=rng.choice([0,1,50,200]),highLiquidityAge=rng.choice([rt.NA,1]),lowLiquidityAge=rt.NA)
            for node,helper in zip(nodes,[fast.liquidity_clusters,fast.liquidity_ages]):
                original=copy.deepcopy(e);optimized=copy.deepcopy(e)
                exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'original-loop','exec'),{'e':original,'rt':rt})
                helper(optimized)
                self.assertEqual(rt.clean(original.values),rt.clean(optimized.values))

    def test_full_packets_scratch_values_and_checkpoint_match_original_execution(self):
        clients=[bar(i,100+(i%17)*.7+(i%3)*.2) for i in range(600)]
        reference=Engine('ETHUSDT','1m');original=[]
        with patch.object(fast,'resolve',side_effect=lambda module,name:getattr(module,name)):
            for client in clients:original.append((reference.step(client),rt.clean(reference.context.values)))
        optimized=Engine('ETHUSDT','1m')
        for client,(packet,values) in zip(clients,original):
            self.assertEqual(optimized.step(client),packet)
            self.assertEqual(rt.clean(optimized.context.values),values)
        self.assertEqual(checkpoint.dump(optimized,(0,0)),checkpoint.dump(reference,(0,0)))

    def test_modified_loop_does_not_match_fast_kernel(self):
        node=next(n for n in ast.parse(inspect.getsource(liquidity.update)).body[0].body if isinstance(n,ast.For))
        node.iter.args[1]=ast.Constant(49)
        optimized=fast.optimize([node],liquidity.__name__)
        self.assertIsInstance(optimized[0],ast.For)

    def test_global_helpers_remain_dynamic_after_compilation(self):
        compiled=fast.resolve(volume_profile,'update')
        with patch.object(volume_profile,'accumulate_histogram',side_effect=RuntimeError('updated helper')):
            e=Engine('ETHUSDT','1m')
            with self.assertRaisesRegex(RuntimeError,'updated helper'):e.step(bar(0,100))

    def test_vp_loops_match_reference_for_ties_missing_bins_and_ordered_sums(self):
        import hashlib
        from Section_4_Features.execution.components import stable_dump
        nodes={hashlib.sha256(stable_dump(n).encode()).hexdigest():n for n in ast.walk(ast.parse(inspect.getsource(volume_profile.update))) if isinstance(n,(ast.For,ast.While))}
        rng=random.Random(7)
        for _ in range(100):
            e=Context('ETHUSDT','1m');e.begin(bar(0,100))
            bins=[rng.choice([0.,1.,3.,None,rt.NA]) for _ in range(rng.randint(1,30))]
            e.values.update(vpVolumeBins=bins,vpBins=len(bins),maxVolume=0.,pocIndex=0,totalVPVolume=0.,
                vaLowIndex=0,vaHighIndex=0,accumulatedVolume=bins[0],valueTarget=5.,vpLow=90.,vpBinSize=.5,
                vpVALow=90.,vpVAHigh=90.5,hvnThreshold=2.,lvnThreshold=1.,
                vpHVNLow=rt.NA,vpHVNHigh=rt.NA,vpLVNLow=rt.NA,vpLVNHigh=rt.NA)
            for digest,node in nodes.items():
                name=fast.LOOPS.get(digest)
                if name not in ('_fast_poc','_fast_total','_fast_area','_fast_nodes'):continue
                original=copy.deepcopy(e);optimized=copy.deepcopy(e)
                exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'original-vp-loop','exec'),{'e':original,'rt':rt})
                fast.HELPERS[name](optimized)
                self.assertEqual(rt.clean(original.values),rt.clean(optimized.values),name)

    def test_runtime_semantics_change_falls_back_to_reviewed_loop(self):
        node=next(n for n in ast.parse(inspect.getsource(liquidity.update)).body[0].body if isinstance(n,ast.For))
        self.assertIsInstance(fast.optimize([node],liquidity.__name__)[0],ast.Expr)
        def changed_binary(op,a,b):return False
        with patch.object(rt,'binary',changed_binary):
            self.assertIsInstance(fast.optimize([node],liquidity.__name__)[0],ast.For)
