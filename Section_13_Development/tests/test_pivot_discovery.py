"""Native labels, context-matched controls, compact inputs and 15m risk execution."""
import copy
import unittest

from Section_8_Decision_Engine import pivot_discovery as d, strategy_analyzer as a
from Section_8_Decision_Engine.pivot_candle_source import unpack
from Section_12_Research.cli.strategy_analyzer_workspace import field_catalog

STEP = 900000


def source():
    rows = []
    for i in range(14):
        start = i * STEP
        ctx = {n: dict(candle_open_time=start, candle_close_time=start+STEP-1, as_of=start+STEP,
                       data_quality='VALID', coverage=1., classification=c) for n, c in (
            ('REGIME', dict(primary='TRANSITIONAL', direction='BEARISH')),
            ('TREND', dict(direction='BEARISH')), ('STRUCTURE', dict(direction='BEARISH')))}
        rows.append(dict(open_time=start, close_time=start+STEP-1, open=100., high=100.5, low=99.5, close=100.,
                         volume=10., feature_valid=True, context=ctx,
                         features=dict(di_plus=10., di_minus=50. if i == 2 else 15., rsi=15. if i == 2 else 50.,
                                       adx=30., ema50=101., measurement_gap=False, buy=1 if i==0 else 0, sell=1 if i==10 else 0)))
    rows[2]['low'] = 98.
    rows[7]['low'] = 100.
    rows[11]['low'] = 99.
    events = [dict(id=f'{i:064x}', type=kind, origin_time=i*STEP, confirmation_time=(i+2)*STEP,
                   known_time=(i+3)*STEP, price=rows[i]['low' if kind=='PIVOT_LOW' else 'high'])
              for i, kind in [(2,'PIVOT_LOW'),(5,'PIVOT_HIGH'),(7,'PIVOT_LOW'),(9,'PIVOT_HIGH'),(11,'PIVOT_LOW')]]
    return dict(version='pivot-candle-source-v1', source_id='fixture', symbol='SUIUSDT', timeframe='15m',
                observed_as_of=14*STEP, candles=rows, native_pivots=events, engine_history={})


def packed(p):
    result = copy.deepcopy(p)
    rows = result.pop('candles')
    columns = sorted(rows[0]['features'])
    result['exported_feature_columns'] = columns
    result['context_table'] = []
    result['packed_candles'] = []
    for r in rows:
        refs = []
        for name in ('STRUCTURE','TREND','REGIME'):
            payload = {k:r['context'][name][k] for k in ('classification','data_quality','coverage')}
            if payload not in result['context_table']:
                result['context_table'].append(payload)
            refs.append(result['context_table'].index(payload))
        result['packed_candles'].append([*(r[k] for k in ('open_time','close_time','open','high','low','close','volume')),
                                         [r['features'].get(k) for k in columns], refs])
    return result


def config():
    return dict(version=a.VERSION, id='15m fixture', execution=dict(fee_bps_per_side=4., slippage_bps_per_side=2.), branches=[
        dict(id='buy', side='BUY', when=dict(field='feature.buy',op='eq',value=1)),
        dict(id='sell', side='SELL', when=dict(field='feature.sell',op='eq',value=1))])


class PivotDiscovery(unittest.TestCase):
    def test_immediate_opposite_endpoint_not_number_of_strategy_entries(self):
        dataset = d.Dataset(source())
        result = dataset.compare(side='BUY',control='failed_pivots')
        self.assertEqual(result['native_pivots'],5)
        self.assertEqual(result['labels'],{'GE_1':1,'LT_1':1,'CENSORED':1})
        self.assertEqual(result['matched_pairs'],1)
        self.assertAlmostEqual(dataset.cases[0]['move_pct'],100*(100.5/98-1))
        row = next(f for f in result['overlap'] if f['feature']=='di_minus' and f['threshold']==40)
        self.assertEqual(row['pivot']['pct'],100)
        self.assertEqual(row['control']['pct'],0)

    def test_price_mismatch_rejected_and_gap_censored(self):
        p = source();p['native_pivots'][0]['price'] += 1
        self.assertEqual(d.Dataset(p).invalid_labels,1)
        p = source();del p['candles'][4]
        dataset = d.Dataset(p)
        self.assertEqual(dataset.cases[0]['status'],'CENSORED')

    def test_matching_does_not_borrow_other_context_or_year(self):
        p = source()
        for r in p['candles']:
            if r['open_time'] != 2*STEP:
                r['context']['REGIME']['classification']['direction']='BULLISH'
        result = d.Dataset(p).compare()
        self.assertEqual(result['matched_pairs'],0)
        self.assertEqual(result['unmatched_targets'],1)

    def test_next_candle_offset_uses_next_candle_features_and_context(self):
        result = d.Dataset(source()).compare(control='failed_pivots',offset=1)
        row = next(f for f in result['overlap'] if f['feature']=='di_minus' and f['threshold']==40)
        self.assertEqual(row['pivot']['pct'],0)
        self.assertEqual(result['cases'][-1]['observation_time'],3*STEP)

    def test_compact_rows_preserve_values_context_catalog_and_comparison(self):
        p = source();q = packed(p)
        self.assertEqual(unpack(q)['candles'][2],p['candles'][2])
        self.assertEqual(d.Dataset(q).compare(),d.Dataset(p).compare())
        catalog = field_catalog(q)
        self.assertEqual((catalog['symbol'],catalog['timeframe']),('SUIUSDT','15m'))
        self.assertIn('context.15m.REGIME.direction',{f['id'] for f in catalog['fields']})
        memory = a.Memory(q)
        self.assertEqual(memory.value(2,'feature.di_minus',1),(15.,None))
        self.assertEqual(memory.value(2,'context.15m.REGIME.direction'),('BEARISH',None))
        self.assertTrue(memory.price_valid(2))

    def test_invalid_measurement_is_not_zero_in_compact_fast_path(self):
        p = source();p['candles'][2]['features']['measurement_gap']=True
        result = d.Dataset(packed(p)).compare(control='failed_pivots')
        f = next(f for f in result['features'] if f['feature']=='di_minus')
        self.assertEqual(f['pivot']['n'],0)

    def test_signed_ema_distance_does_not_use_legacy_absolute_distance(self):
        p = source()
        for row in p['candles']:
            row['features']['ema50_distance_pct'] = 99.
        dataset = d.Dataset(packed(p))
        self.assertAlmostEqual(dataset.values('close_to_ema50_pct')[2],100*(100/101-1))

    def test_period_filters_observation_candles_without_restarting_context(self):
        dataset = d.Dataset(source())
        result = dataset.compare(since=6*STEP,until=10*STEP)
        self.assertEqual(result['labels'],{'LT_1':1})
        with self.assertRaises(ValueError):
            dataset.compare(since=10,until=1)

    def test_15m_replay_applies_cost_adjusted_half_percent_stop(self):
        result = a.analyze(packed(source()),config())
        trade = result['trades'][0]
        self.assertEqual(trade['sell_branch'],'RISK_STOP')
        self.assertAlmostEqual(trade['net_pct'],-.5)
        self.assertEqual(trade['entry_time'],STEP)
        self.assertEqual(trade['exit_time_precision'],'WITHIN_CANDLE_UNKNOWN')

    def test_adverse_open_is_not_clipped_to_stop_budget(self):
        p = source();p['candles'][1].update(open=90., high=90.5, low=89.8,close=90.)
        p['candles'][2].update(open=80.,high=90.,low=79.,close=80.)
        result = a.analyze(p,config())
        trade = result['trades'][0]
        self.assertLess(trade['net_pct'],-10)
        self.assertEqual(trade['exit_time'],2*STEP)

    def test_costs_cannot_exhaust_loss_budget_before_entry(self):
        c = config();c['execution']['fee_bps_per_side'] = 30.
        with self.assertRaisesRegex(ValueError,'exhaust'):
            a.analyze(source(),c)


if __name__=='__main__':
    unittest.main()
