"""Candle-wide rules, strict alternation, causal fills and revision diagnostics."""
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from Section_8_Decision_Engine import strategy_analyzer as a


def predicate(field, value):
    return dict(field=field, op='eq', value=value)


def config():
    return dict(version=a.VERSION, id='fixture', execution=dict(fee_bps_per_side=0, slippage_bps_per_side=0, initial_capital=100), branches=[
        dict(id='buy', side='BUY', when=predicate('feature.buy', 1)),
        dict(id='sell', side='SELL', when=predicate('feature.sell', 1))])


def source():
    rows = []
    for i, (price, buy, sell) in enumerate(zip([100, 110, 120, 90, 95, 105, 108, 109], [1, 1, 0, 1, 0, 0, 0, 0], [1, 0, 1, 1, 1, 0, 0, 0])):
        rows.append(dict(open_time=i*a.STEP, close_time=(i+1)*a.STEP-1, open=price, high=price+2,
                         low=price-2, close=price, volume=1, feature_valid=True,
                         features=dict(buy=buy, sell=sell, di_plus=20., di_minus=10., adx=20., rsi=50., measurement_gap=False)))
    return dict(version='btc-hour-sequence-source-v1', source_id='fixture-source', symbol='BTCUSDT', timeframe='1h',
                observed_as_of=8*a.STEP, candles=rows, engine_history={}, pivots=[])


class StrategyAnalyzer(unittest.TestCase):
    def test_oldest_signals_alternate_and_start_buy_despite_simultaneous_sell(self):
        p=source();before=copy.deepcopy(p);result=a.analyze(p,config())
        self.assertEqual([(s['side'],s['candle_open_time']//a.STEP) for s in result['signals']], [('BUY',0),('SELL',2),('BUY',3),('SELL',4)])
        self.assertEqual(result['branch_diagnostics']['buy']['same_side_suppressed'],1)
        self.assertEqual(result['trades'][0]['entry'],110)
        self.assertEqual(result['trades'][0]['exit'],90)
        self.assertEqual(result['trades'][1]['entry'],95)
        self.assertEqual(result['trades'][1]['exit'],105)
        self.assertEqual(result['trades'][0]['buy_inputs']['feature.buy@lag0']['value'],1)
        self.assertEqual(result['trades'][0]['sell_inputs']['feature.sell@lag0']['value'],1)
        self.assertEqual(result['summary']['wins'],1)
        self.assertEqual(result['summary']['losses'],1)
        self.assertAlmostEqual(result['summary']['closed_trade_max_drawdown_pct'],100*(1-90/110))
        self.assertEqual(p,before)

    def test_all_candles_not_native_pivots_and_multiple_branch_ties(self):
        c=config();c['branches'].insert(1,dict(id='another_buy',side='BUY',when=predicate('feature.buy',1)))
        p=source();p['pivots']=[{'irrelevant':'future labels'}]
        result=a.analyze(p,c)
        self.assertEqual(result['signals'][0]['matched_branches'],['buy','another_buy'])
        self.assertEqual(result['signals'][0]['branch_id'],'buy')
        self.assertEqual(result['branch_diagnostics']['another_buy']['accepted'],0)
        self.assertEqual(result['candles_evaluated'],8)

    def test_three_valued_and_or_not_with_explicit_missing_checks(self):
        memory=a.Memory(source());unknown=predicate('feature.absent',1)
        yes=predicate('feature.buy',1);no=predicate('feature.buy',0)
        missing=set()
        self.assertIsNone(memory.evaluate(unknown,0,missing))
        self.assertTrue(memory.evaluate({'any':[unknown,yes]},0,set()))
        self.assertFalse(memory.evaluate({'all':[unknown,no]},0,set()))
        self.assertIsNone(memory.evaluate({'not':unknown},0,set()))
        self.assertTrue(memory.evaluate({'field':'feature.absent','op':'missing'},0,set()))
        self.assertFalse(memory.evaluate(predicate('feature.buy',True),0,set()))
        self.assertIn('feature.absent:MISSING_VALUE',missing)
        p=source();p['candles'][0]['features']['buy']=float('nan')
        self.assertIsNone(a.Memory(p).evaluate(yes,0,set()))

    def test_lags_require_contiguous_past_and_future_lags_rejected(self):
        node=dict(field='feature.di_plus',op='gte',other_field='feature.di_plus',other_lag=1)
        c=config();c['branches'][0]['when']=node
        memory=a.Memory(source())
        self.assertIsNone(memory.evaluate(node,0,set()));self.assertTrue(memory.evaluate(node,1,set()))
        p=source();del p['candles'][1]
        self.assertIsNone(a.Memory(p).evaluate(node,1,set()))
        c['branches'][0]['when']['lag']=-1
        with self.assertRaises(ValueError):a.validate_config(c)

    def test_exact_closed_context_unknown_quality_and_no_current_replacement(self):
        p=source();payload=dict(candle_open_time=0,candle_close_time=4*a.STEP-1,as_of=4*a.STEP,
                               data_quality='PARTIAL',classification=dict(direction='BULLISH'))
        p['engine_history']={'4h:TREND':dict(results={'0':payload})}
        field='context.4h.TREND.direction';memory=a.Memory(p)
        self.assertIsNone(memory.value(2,field)[0]);self.assertEqual(memory.value(3,field)[0],'BULLISH')
        self.assertIsNone(memory.value(7,field)[0])
        payload['candle_open_time']=4*a.STEP
        self.assertEqual(a.Memory(p).value(3,field)[1],'INVALID_CONTEXT_TIME')
        payload['candle_open_time']=0;payload['classification']['direction']='UNKNOWN'
        self.assertEqual(a.Memory(p).value(3,field)[1],'UNKNOWN_CLASSIFICATION')
        payload['data_quality']='INVALID'
        self.assertEqual(a.Memory(p).value(3,field)[1],'INVALID_CONTEXT_QUALITY')

    def test_costs_apply_to_next_open_not_signal_close(self):
        c=config();c['execution'].update(fee_bps_per_side=4,slippage_bps_per_side=2)
        trade=a.analyze(source(),c)['trades'][0]
        self.assertAlmostEqual(trade['net_pct'],100*((90*.9998*.9996)/(110*1.0002*1.0004)-1))
        p=source();p['candles'][0]['close']=101
        self.assertEqual(trade['entry'],a.analyze(p,c)['trades'][0]['entry'])

    def test_tail_and_open_positions_not_invented_sales(self):
        p=source()
        for r in p['candles']:r['features'].update(buy=0,sell=0)
        p['candles'][-1]['features']['buy']=1
        result=a.analyze(p,config())
        self.assertEqual(result['signals'][0]['fill_status'],'UNFILLED_TAIL')
        self.assertEqual(result['trades'][0]['status'],'CENSORED');self.assertEqual(result['summary']['closed'],0)
        p['candles'][0]['features']['buy']=1;p['candles'][-1]['features']['buy']=0
        result=a.analyze(p,config())
        self.assertEqual(result['summary']['open'],1);self.assertEqual(result['summary']['closed'],0)

    def test_gaps_censor_positions_without_breaking_signal_alternation(self):
        p=source();del p['candles'][2]
        p['candles'][2]['features'].update(buy=0,sell=1)
        p['candles'][3]['features'].update(buy=1,sell=0)
        p['candles'][4]['features'].update(buy=0,sell=1)
        result=a.analyze(p,config())
        self.assertEqual([s['side'] for s in result['signals']],['BUY','SELL','BUY','SELL'])
        self.assertEqual(result['trades'][0]['status'],'CENSORED');self.assertIsNone(result['trades'][0]['net_pct'])
        p=source();del p['candles'][1]
        result=a.analyze(p,config())
        self.assertEqual(result['signals'][0]['fill_status'],'CENSORED')
        self.assertEqual(result['trades'][0]['status'],'CENSORED')

    def test_invalid_price_cannot_fill_or_trigger_signal(self):
        p=source();p['candles'][1]['high']=1
        result=a.analyze(p,config())
        self.assertEqual(result['invalid_price_candles'],1)
        self.assertIsNone(result['trades'][0]['entry']);self.assertEqual(result['trades'][0]['status'],'CENSORED')

    def test_shortened_historical_candle_is_explicit_invalid_not_a_complete_hour(self):
        p=source();p['candles'][1]['close_time']=p['candles'][1]['open_time']+1000
        result=a.analyze(p,config())
        self.assertEqual(result['invalid_price_candles'],1)
        self.assertEqual(result['candles_scanned'],8);self.assertEqual(result['candles_evaluated'],7)
        self.assertEqual(result['trades'][0]['status'],'CENSORED')
        self.assertEqual(result['signals'][0]['fill_status'],'CENSORED')

    def test_missing_features_reported_and_or_can_use_available_memory(self):
        c=config();c['branches'][0]['when']={'any':[predicate('feature.never_exported',1),predicate('feature.buy',1)]}
        result=a.analyze(source(),c)
        self.assertEqual(result['unavailable_feature_fields'],['feature.never_exported'])
        self.assertEqual(result['signals'][0]['candle_open_time'],0)
        self.assertEqual(result['branch_diagnostics']['buy']['unknown'],5)

    def test_prefix_signals_unchanged_by_future_data_and_labels(self):
        p=source();first=a.analyze(p,config())
        p['candles'][5]['features'].update(buy=1,sell=1);p['candles'][6]['open']=107;p['pivots']=[{'future':'not an input'}]
        second=a.analyze(p,config())
        self.assertEqual([s for s in first['signals'] if s['known_time']<=5*a.STEP], [s for s in second['signals'] if s['known_time']<=5*a.STEP])
        prefix=source();prefix['candles']=prefix['candles'][:5];prefix['observed_as_of']=5*a.STEP
        report=a.analyze(prefix,config())
        self.assertEqual([(s['side'],s['known_time']) for s in report['signals']],[(s['side'],s['known_time']) for s in first['signals'] if s['known_time']<=5*a.STEP])

    def test_comparison_full_replay_distinguishes_corrected_removed_and_lost(self):
        p=source();baseline=a.analyze(p,config())
        c=config();c['id']='later-exit';c['branches'][1]['when']=dict(field='price.open',op='lt',value=100)
        revision=a.analyze(p,c);comparison=a.compare(baseline,revision)
        self.assertEqual(sum(comparison['counts'][key] for key in ('failure_corrected','failure_removed','failure_persisted','failure_unresolved')),1)
        self.assertEqual(sum(comparison['counts'][key] for key in ('success_preserved','success_lost','success_unresolved')),1)
        self.assertEqual(comparison['counts']['failure_persisted'],1)
        self.assertEqual(comparison['counts']['success_lost'],1)
        c=config();c['branches'][0]['when']=dict(field='price.open',op='lt',value=100)
        removed=a.compare(baseline,a.analyze(p,c))
        self.assertEqual(removed['counts']['failure_removed'],1)
        self.assertEqual(removed['counts']['failure_corrected'],0)
        c=config();c['branches'][1]['when']=dict(field='price.open',op='gte',value=108)
        corrected=a.compare(baseline,a.analyze(p,c))
        self.assertEqual(corrected['counts']['failure_corrected'],1)

    def test_comparison_rejects_changed_source_window_and_costs(self):
        p=source();baseline=a.analyze(p,config())
        c=config();c['execution']['fee_bps_per_side']=1
        with self.assertRaises(ValueError):a.compare(baseline,a.analyze(p,c))
        with self.assertRaises(ValueError):a.compare(baseline,a.analyze(p,config(),since=2*a.STEP))
        p['candles'][0]['features']['unused']=5
        with self.assertRaises(ValueError):a.compare(baseline,a.analyze(p,config()))

    def test_window_and_empty_selection_respect_terminal_boundary(self):
        result=a.analyze(source(),config(),until=3*a.STEP)
        self.assertEqual(len(result['signals']),1);self.assertEqual(result['summary']['open'],1)
        empty=a.analyze(source(),config(),since=9*a.STEP)
        self.assertEqual(empty['candles_evaluated'],0);self.assertEqual(empty['summary']['entries'],0)
        p=source();p['candles'].reverse()
        with self.assertRaises(ValueError):a.analyze(p,config())

    def test_no_year_reset_or_lookahead_outcome_predicates(self):
        p=source();shift=1735689600000-2*a.STEP
        for r in p['candles']:r['open_time']+=shift;r['close_time']+=shift
        p['observed_as_of']+=shift
        result=a.analyze(p,config())
        self.assertEqual([y['year'] for y in result['yearly']],['2024','2025'])
        self.assertEqual(result['yearly'][0]['closed'],0);self.assertEqual(result['yearly'][1]['closed'],2)
        for field in ('result.net_pct','future.close','feature.foo.__class__'):
            c=config();c['branches'][0]['when']=predicate(field,1)
            with self.assertRaises(ValueError):a.validate_config(c)

    def test_cli_runs_full_baseline_comparison_without_touching_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);inp=root/'source.json.gz';inp.write_bytes(gzip.compress(json.dumps(source()).encode()));before=inp.read_bytes()
            conf=root/'config.json';conf.write_text(json.dumps(config()))
            completed=subprocess.run([sys.executable,'analyze_btc_hour_strategy.py','--input',str(inp),'--config',str(conf),'--baseline-config',str(conf),'--output-dir',str(root/'out')],capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            result=json.loads(gzip.decompress((root/'out/strategy_analysis.json.gz').read_bytes()))
            self.assertEqual(result['comparison']['counts']['success_preserved'],1)
            self.assertEqual(result['comparison']['counts']['failure_persisted'],1)
            self.assertTrue((root/'out/strategy_analysis.html').is_file());self.assertEqual(before,inp.read_bytes())

    def test_report_inputs_and_progress_do_not_change_trading_results(self):
        p=source();plain=a.analyze(p,config());progress=[]
        rich=a.analyze(p,config(),report_fields=['feature.rsi','feature.absent'],progress=progress.append)
        self.assertEqual(rich['summary'],plain['summary'])
        self.assertEqual(rich['run_id'],plain['run_id'])
        self.assertEqual([(s['side'],s['known_time']) for s in rich['signals']],[(s['side'],s['known_time']) for s in plain['signals']])
        self.assertEqual(rich['trades'][0]['buy_inputs']['feature.rsi@lag0']['value'],50)
        self.assertIsNone(rich['trades'][0]['buy_inputs']['feature.absent@lag0']['value'])
        self.assertEqual(progress[-1]['complete'],8)
        with self.assertRaises(ValueError):a.analyze(p,config(),report_fields=['future.price'])


if __name__=='__main__':unittest.main()
