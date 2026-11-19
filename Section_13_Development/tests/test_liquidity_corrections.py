"""Reviewed candle-proxy corrections, separate from observed order-book data."""
import ast
import inspect
import unittest
from Section_4_Features.features import liquidity
from Section_4_Features.execution import runtime as rt
from Section_4_Features.execution.context import Context
from Section_4_Features.execution.components import Catalog


def statements_for(name):
    tree=ast.parse(inspect.getsource(liquidity.update))
    return [node for node in tree.body[0].body if any(isinstance(n,ast.Subscript) and isinstance(n.ctx,ast.Store) and isinstance(n.slice,ast.Constant) and n.slice.value==name for n in ast.walk(node))]


def execute(nodes,values):
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'liquidity-corrections','exec'),{'e':values,'rt':rt})


class LiquidityCorrections(unittest.TestCase):
    def test_nearest_side_uses_comparable_percentages(self):
        for low,high,expected in [(1,4,'SELL_SIDE_NEAR'),(4,1,'BUY_SIDE_NEAR'),(1,1,'MID_RANGE'),(rt.NA,1,'UNKNOWN')]:
            e=dict(externalLowDistancePct=low,externalHighDistancePct=high);execute(statements_for('liquiditySide'),e)
            self.assertEqual(e['liquiditySide'],expected)

    def test_low_importance_checks_the_percentage_it_consumes(self):
        nodes=[n for n in statements_for('lowLiquidityImportance') if isinstance(n,ast.If) and 'externalLowDistancePct' in ast.unparse(n.test)]
        self.assertEqual(len(nodes),1)
        for absolute,pct,expected in [(0,rt.NA,0),(rt.NA,2,3)]:
            e=dict(externalLowDistance=absolute,externalLowDistancePct=pct,lowLiquidityImportance=0)
            execute(nodes,e);self.assertEqual(e['lowLiquidityImportance'],expected)

    def test_sweep_strength_guards_missing_zero_and_negative_atr(self):
        for atr in (None,rt.NA,0,-1,2):
            e=dict(atr=atr,bullSweepDetected=True,bearSweepDetected=True,prevLowLiquidity=100,prevHighLiquidity=110,l=98,h=112)
            execute(statements_for('bullSweepStrength')+statements_for('bearSweepStrength'),e)
            for key in ('bullSweepStrength','bearSweepStrength'):
                if atr==2:self.assertEqual(e[key],1)
                else:self.assertTrue(rt.is_na(e[key]))

    def test_percent_alias_is_compatible_and_zero_remains_exact(self):
        e=dict(internalLowLiquidity=90,c=100)
        execute(statements_for('internalLowDistancePct')+statements_for('internalLowDistance'),e)
        self.assertEqual(e['internalLowDistancePct'],10);self.assertEqual(e['internalLowDistance'],10)
        self.assertTrue(rt.is_na(rt.binary('/',1,0)))
        e.update(internalLowLiquidity=100)
        execute(statements_for('internalLowDistancePct')+statements_for('internalLowDistance'),e)
        self.assertEqual(e['internalLowDistance'],0)

    def test_lookback_is_initialized_validated_and_repair_is_scoped(self):
        self.assertGreater(Context('ENAUSDT','4h').parameters['liquidityLookback'],0)
        with self.assertRaises(ValueError):Context('ENAUSDT','4h',{'liquidityLookback':0})
        catalog=Catalog();plan=catalog.plan({u.id for u in catalog.units if u.module.endswith('.liquidity')})
        self.assertNotIn('ema50',plan.columns);self.assertNotIn('sr_zone_events',plan.columns)
        self.assertIn('liquidity_side',plan.columns)
