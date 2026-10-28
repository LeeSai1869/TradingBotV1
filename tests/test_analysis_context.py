"""Point-in-time evidence is independent of decision labels and later outcomes."""
import ast
import copy
import inspect
import unittest
from Section_1_Global_Core.analysis import annotate
from Section_9_Confidence_Engine import engine as confidence
from Section_10_Opportunity_Engine import engine as opportunity
from Section_10_Opportunity_Engine.context import anchor,advance


def f(price=100):
    return dict(formula_version=3,atr=2,ema50=price-4,ema200=price-6,vwap=price-2,rsi=80,
        di_plus=20,di_minus=15,adx=30,current_structure='STRUCTURE_BULL',
        atr_ma_ratio=1,support_zone_low=price-6,support_zone_high=price-5,
        resistance_zone_low=price+4,resistance_zone_high=price+6,protected_high=price+15)


def bar(i,price,signal=None,features=None,**ohlc):
    return dict(open_time=i*60000,client=dict(close_time=(i+1)*60000-1,open=price+.1,high=price+.2,low=price-.2,close=price,**ohlc),
        features=features or f(price),momentum={'signal_type':signal})


class ContextTests(unittest.TestCase):
    def test_countertrend_reversal_is_not_scored_as_trend_continuation(self):
        features=f(102);features.update(ema50=98,di_plus=20)
        result=confidence.evaluate(102,features,previous=dict(close=108,rsi=88,di_plus=35,di_minus=20),
            candle=dict(open=108,high=110,low=100))
        self.assertEqual(result['sell_mode'],'reversal')
        self.assertGreater(result['sell_score'],75)
        self.assertLess(result['continuation']['sell_score'],50)
        self.assertEqual(result['preference'],'not a decision')

    def test_decision_label_cannot_change_point_confidence(self):
        a=[bar(0,100),bar(1,101,'BUY')];b=copy.deepcopy(a);b[1]['momentum']['signal_type']='SELL'
        annotate(a,now_ms=200000);annotate(b,now_ms=200000)
        self.assertEqual(a[1]['confidence'],b[1]['confidence'])
        self.assertEqual(a[1]['opportunity'],b[1]['opportunity'])

    def test_anchor_is_fixed_while_current_price_and_features_move(self):
        entry=f(81000);entry.update(atr=1000,support_zone_low=78000,support_zone_high=79000,
            resistance_zone_low=90000,resistance_zone_high=91000,protected_high=95000,ema50=80000,ema200=79000,vwap=80500)
        rows=[bar(0,81000,'BUY',entry),bar(1,85000,features={**entry,'resistance_zone_low':96000,'resistance_zone_high':97000})]
        annotate(rows,now_ms=200000)
        original=copy.deepcopy(rows[0]['signal_context']);context=rows[1]['signal_context']
        self.assertEqual(context['entry'],81000);self.assertEqual(context['plan'],original['plan'])
        self.assertEqual(context['confidence'],original['confidence'])
        self.assertEqual(rows[1]['opportunity']['entry'],85000)
        self.assertEqual(rows[0]['signal_context'],original)

    def test_opposite_signal_above_previous_entry_is_reported_not_suppressed(self):
        rows=[bar(0,100,'SELL'),bar(1,110,'BUY')];annotate(rows,now_ms=200000)
        self.assertEqual(rows[1]['momentum']['signal_type'],'BUY')
        self.assertEqual(rows[1]['signal_context']['entry_relationship'],'above previous entry')

    def test_ohlc_target_stop_order_is_not_invented(self):
        packet=opportunity.evaluate(100,f());state=anchor(packet,side='BUY',open_time=0)
        candle=bar(1,101);candle['client'].update(high=120,low=80)
        result=advance(state,candle)
        self.assertEqual(result['state'],'ambiguous intrabar')
        self.assertEqual(result['targets_touched'],[]);self.assertEqual(state['state'],'active')

    def test_missing_candles_clear_context_not_the_decision(self):
        rows=[bar(0,100,'BUY'),bar(3,101)];annotate(rows,now_ms=300000)
        self.assertIsNone(rows[1]['signal_context']);self.assertEqual(rows[0]['momentum']['signal_type'],'BUY')

    def test_engine_boundaries_do_not_import_each_other_or_storage(self):
        for module,forbidden in ((confidence,'Section_10_Opportunity_Engine'),(opportunity,'Section_9_Confidence_Engine')):
            source=inspect.getsource(module)
            imports=[n.module or '' for n in ast.walk(ast.parse(source)) if isinstance(n,ast.ImportFrom)]
            self.assertFalse(any(forbidden in name or 'memory_storage' in name for name in imports))

class PointIndependenceTests(unittest.TestCase):
    def test_later_success_or_failure_does_not_rewrite_entry_evidence(self):
        from Section_1_Global_Core.global_packet import evaluate_price_point
        point=bar(0,100,'SELL');expected=evaluate_price_point(point['client'],point['features'])
        for outcome in (60,150):
            rows=[copy.deepcopy(point),bar(1,outcome)]
            annotate(rows,now_ms=200000)
            self.assertEqual(rows[0]['confidence'],expected['confidence'])
            self.assertEqual(rows[0]['opportunity'],expected['opportunity'])
