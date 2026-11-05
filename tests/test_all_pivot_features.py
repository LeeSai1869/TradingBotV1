import copy
import json
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
try:
    import numpy as np
except ImportError:
    raise unittest.SkipTest('Optional all-pivot research requires NumPy')
import test_pivot_research as fixtures
from Section_1_Global_Core import pivot_feature_comparison as compare,pivot_research,regime_inputs
from compare_pivot_features import visual
from study_btc_pivots import commands,FRAMES

class NumericTrajectories(unittest.TestCase):
    def test_exact_offsets_do_not_bridge_missing_candles(self):
        times=np.array([0,60000,180000]);idx,valid=compare.exact_indices(times,[60000],[-1,0,1,2],60000)
        self.assertEqual(valid.tolist(),[[True,True,False,True]])
        values=np.array([[1.],[3.],[7.]])
        groups={('BUY_SIDE','HIT','ALL'):[0]};stats=compare.aggregate(values,idx,valid,groups)[0]
        self.assertEqual(stats['count'],[[1],[1],[0],[1]])
        self.assertTrue(np.isnan(stats['mean'][2][0]));self.assertEqual(stats['mean'][3][0],7)

    def test_missing_values_and_population_moments(self):
        values=np.array([[2.,np.nan],[4.,8.]])
        out=compare.aggregate(values,np.array([[0],[1]]),np.array([[True],[True]]),{('BUY_SIDE','HIT','ALL'):[0,1]})[0]
        self.assertEqual(out['count'],[[2,1]]);self.assertEqual(out['mean'],[[3.,8.]])
        self.assertEqual(out['stddev'],[[1.,0.]])

    def test_lower_benchmark_uses_extrema_without_inventing_hit_time(self):
        cases=[dict(id='a',origin=dict(max_favorable_pct=1.2,complete=False)),dict(id='b',origin=dict(max_favorable_pct=.9,complete=True)),dict(id='c',origin=dict(max_favorable_pct=.8,complete=False))]
        report=dict(version='pivot-moves-v1',config=dict(horizon_bars=None),cases=cases);old=copy.deepcopy(report)
        self.assertEqual(compare.outcomes(report),dict(a='HIT',b='NO_HIT',c='CENSORED'));self.assertEqual(old,report)

    def test_five_frame_batch_forces_one_percent_and_every_cohort_before_comparison(self):
        args=Namespace(timeframes=list(FRAMES),output_dir=Path('research_reports/test'),before_bars=12,after_bars=24,until='2026-11-05',push_report=True)
        result=list(commands(args));self.assertEqual([x[0] for x in result],['15m','30m','1h','4h','1d'])
        for frame,scan,compare_cmd in result:
            self.assertEqual(scan[scan.index('--threshold-pct')+1],'1');self.assertIn('--push-report',scan);self.assertIn('--push-report',compare_cmd)
            self.assertNotIn('--max-bars',scan)

class FeatureHistory(unittest.TestCase):
    def setUp(self):fixtures.PivotCohort.setUp(self)
    def test_real_history_checks_every_pivot_all_numeric_fields_and_zero_offset(self):
        report=pivot_research.scan('BTCUSDT','1m',threshold=1,now_ms=10**9);conn=regime_inputs.open_sources()
        try:result=compare.compare(conn,report,before=2,after=3,batch_size=24)
        finally:conn.close()
        self.assertEqual(result['pivots'],3);self.assertEqual(sum(result['origin_outcomes'].values()),3)
        self.assertIn('ema200',result['features']);self.assertIn('lower_wick_fraction',result['features'])
        self.assertIn('atr_pct_of_close',result['features'])
        for groups in result['features'].values():
            keys=[(g['side'],g['outcome'],g['year']) for g in groups]
            self.assertEqual(len(keys),len(set(keys)))
        pct=result['features']['atr_pct_of_close'];fraction=result['features']['atr_percent']
        for actual,legacy in zip(pct,fraction):
            for a,b in zip(actual['mean'],legacy['mean']):
                if a is not None and b is not None:self.assertAlmostEqual(a,b*100)
        self.assertEqual(result['offsets'],[-2,-1,0,1,2,3]);json.dumps(result,allow_nan=False)
        cohorts=[g for g in result['features']['raw_low'] if g['year']=='ALL']
        self.assertEqual(sum(g['pivots'] for g in cohorts),3)
        self.assertIn('independent',result['interpretation'].lower())
        page=visual(result);self.assertIn('1% benchmark',page);self.assertIn('di_minus',page)
        self.packet=result
    def test_cli_writes_full_comparison_and_visual_without_changing_stores(self):
        import contextlib,gzip,hashlib,io
        import compare_pivot_features as cli
        from Section_1_Global_Core.memory_storage.Storage import klines_store,features_store
        report=pivot_research.scan('BTCUSDT','1m',threshold=1,now_ms=10**9)
        path=self.root/'cohort.json.gz';path.write_bytes(gzip.compress(json.dumps(report).encode()))
        output=self.root/'features.json.gz'
        sources=(klines_store.DB_PATH,features_store.DB_PATH)
        digest=lambda:[hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
        before=digest()
        with patch('sys.argv',['compare_pivot_features.py','--report',str(path),'--output',str(output),'--before-bars','2','--after-bars','3']),patch('os.nice',return_value=0,create=True),contextlib.redirect_stdout(io.StringIO()):cli.main()
        packet=json.loads(gzip.decompress(output.read_bytes()));self.assertEqual(packet['pivots'],3)
        self.assertTrue(output.with_suffix('').with_suffix('.html').is_file())
        self.assertEqual(sum(g['origin_price_matches_raw'] for g in packet['timing']),3)
        self.assertEqual(before,digest())
        self.assertTrue(packet['engine_context']['groups'])

    def test_four_hour_and_daily_context_use_correct_detection_candle(self):
        for frame,step in [('4h',14400000),('1d',86400000)]:
            pivot_research.validate('BTCUSDT',frame);self.assertEqual(pivot_research.DURATIONS[frame],step)
    def test_real_four_hour_and_daily_scan_and_context(self):
        from Section_1_Global_Core.memory_storage.Storage import klines_store,features_store
        old_frame='1m';old_step=60000
        for frame,step in [('4h',14400000),('1d',86400000)]:
            raw=klines_store.open_db()
            with raw:raw.execute('UPDATE klines SET interval=?,open_time=CAST(open_time/? AS INTEGER)*?,close_time=(CAST(open_time/? AS INTEGER)+1)*?-1 WHERE symbol=? AND interval=?',(frame,old_step,step,old_step,step,'BTCUSDT',old_frame))
            raw.close();source=features_store.open_db()
            with source:
                source.execute('UPDATE features SET interval=?,open_time=CAST(open_time/? AS INTEGER)*?,structure_events=? WHERE symbol=? AND interval=?',(frame,old_step,step,'[]','BTCUSDT',old_frame))
                source.execute('UPDATE feature_engine_state SET interval=?,last_open_time=CAST(last_open_time/? AS INTEGER)*? WHERE symbol=? AND interval=?',(frame,old_step,step,'BTCUSDT',old_frame))
                source.execute('UPDATE feature_calculation_versions SET interval=? WHERE symbol=? AND interval=?',(frame,'BTCUSDT',old_frame))
                for original in self.pivots:
                    event={**original,**{key:original[key]//60000*step for key in ('origin_time','confirmation_time','known_time')}}
                    source.execute('UPDATE features SET structure_events=? WHERE symbol=? AND interval=? AND open_time=?',(json.dumps([event]),'BTCUSDT',frame,event['confirmation_time']))
            source.close()
            report=pivot_research.scan('BTCUSDT',frame,threshold=1,now_ms=10**12)
            self.assertEqual(report['summary']['pivots'],3)
            case=report['cases'][0]
            context=pivot_research.case_context('BTCUSDT',frame,case['id'],case['pivot']['known_time'],source_id=report['source_id'],as_of=report['observed_as_of'])
            self.assertTrue(any(row['client']['open_time']==case['pivot']['confirmation_time'] for row in context['bars']))
            old_frame,old_step=frame,step

    def test_reject_different_benchmark_and_generation(self):
        report=pivot_research.scan('BTCUSDT','1m',threshold=2,now_ms=10**9);conn=regime_inputs.open_sources()
        try:
            with self.assertRaises(ValueError):compare.compare(conn,report)
            report['config']['threshold_pct']=1;report['source_id']='changed'
            with self.assertRaises(ValueError):compare.compare(conn,report)
        finally:conn.close()
