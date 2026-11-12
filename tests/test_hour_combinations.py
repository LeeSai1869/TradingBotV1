"""Research-only conjunctions, causal context joins and explicit denominators."""
import copy
import json
from datetime import datetime,timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from study_btc_hour_sequences import (combination_analysis,combination_state,
    default_combination_filters,validate_combination_filters,combination_visual)


def fixture():
    packet=dict(version='btc-hour-pivot-sequences-v1',source_id='test',symbol='BTCUSDT',timeframe='1h',counts={},snapshots={},context_pool={},cases=[],candidate_observations=[])
    # Three chronological years; zero matching samples in the last year.
    for i,(year,spread,quality) in enumerate(((2024,12,'VALID'),(2025,9,'VALID'),(2026,20,'INVALID'))):
        known=int(datetime(year,6,1,12,tzinfo=timezone.utc).timestamp()*1000)
        snap=dict(known_time=known,di=dict(abs_spread=spread,dominant='MINUS'),engine_refs={})
        for frame,engine in (('1h','REGIME'),('1h','TREND'),('4h','TREND'),('1d','TREND')):
            step={'1h':3600000,'4h':14400000,'1d':86400000}[frame];opened=known//step*step-step
            ref=f'{frame}:{engine}:{opened}';snap['engine_refs'][f'{frame}:{engine}']=ref
            packet['context_pool'][ref]=dict(candle_open_time=opened,candle_close_time=opened+step-1,as_of=opened+step,data_quality=quality,
                classification=dict(primary='TRENDING',direction='BULLISH'))
        packet['snapshots'][str(i)]=snap
        packet['cases'].append(dict(id=f'pivot-{i}',side='BUY',origin_time=known-3600000,
            stages=dict(candidate_start=i,final_extreme_first_recorded=i,origin_close=i,native_confirmation=i),outcome=dict(status='HIT' if i==0 else 'NO_HIT')))
        packet['candidate_observations'].append(dict(index=i,snapshot=i,side='BUY',future={'12':dict(status='COMPLETE' if i<2 else 'CENSORED',complete=i<2,
            close_return_pct=2 if i==0 else -1 if i==1 else None,up_1pct=i==0,down_1pct=i==1)}))
    return packet


class Combinations(unittest.TestCase):
    def group(self,result,**criteria):
        keys=dict(filter_id='buy_context_5',cohort='candidate_next_open_12h',stage='active_candidate',year='ALL')|criteria
        return next(g for g in result['groups'] if all(g[k]==v for k,v in keys.items()))

    def test_all_denominators_baselines_missing_and_zero_years(self):
        p=fixture();before=copy.deepcopy(p);result=combination_analysis(p);g=self.group(result)
        self.assertEqual((g['n'],g['eligible'],g['matched_n'],g['not_matched'],g['missing_excluded']),(3,2,1,1,1))
        self.assertEqual(g['matched']['mean_directional_close_return_pct'],2)
        self.assertEqual(g['eligible_baseline']['mean_directional_close_return_pct'],.5)
        self.assertEqual(g['baseline']['CENSORED'],1)
        self.assertEqual(g['matched']['COMPLETE'],1)
        self.assertEqual(g['missing_by_field']['1h:REGIME:primary'],1)
        self.assertEqual(self.group(result,year='2024')['matched_n'],1)
        zero=self.group(result,year='2026');self.assertEqual(zero['matched_n'],0)
        self.assertIsNone(zero['matched']['mean_directional_close_return_pct'])
        native=self.group(result,cohort='native_pivot',stage='origin_close')
        self.assertEqual(native['matched']['hit_rate_pct'],100)
        self.assertIsNone(native['matched']['mean_directional_close_return_pct'])
        self.assertEqual(p,before);json.dumps(result,allow_nan=False)

    def test_fifth_condition_adds_regime_without_changing_four_gate_result(self):
        p=fixture();snap=p['snapshots']['0'];ref=snap['engine_refs']['1h:REGIME']
        p['context_pool'][ref]['classification']['primary']='RANGING'
        result=combination_analysis(p)
        self.assertEqual(self.group(result,filter_id='buy_context_4')['matched_n'],1)
        self.assertEqual(self.group(result)['matched_n'],0)

    def test_missing_checked_even_when_spread_fails(self):
        p=fixture();snap=p['snapshots']['1'];snap['engine_refs']['1d:TREND']='UNAVAILABLE:MISSING_EXACT_CLOSED_CANDLE'
        state,missing=combination_state(p,snap,default_combination_filters()[1])
        self.assertEqual(state,'MISSING');self.assertIn('1d:TREND:direction',missing)
        g=self.group(combination_analysis(p));self.assertEqual(g['not_matched'],0);self.assertEqual(g['missing_excluded'],2)

    def test_last_closed_only_never_stale_or_future_context(self):
        for frame in ('1h','4h','1d'):
            for defect in ('future','stale','wrong_close','wrong_as_of','unknown'):
                with self.subTest(frame=frame,defect=defect):
                    p=fixture();snap=p['snapshots']['0'];scope=f'{frame}:TREND';ref=snap['engine_refs'][scope];value=p['context_pool'][ref]
                    if defect=='future':value['candle_open_time']=snap['known_time']
                    elif defect=='stale':snap['engine_refs'][scope]=scope+':0';p['context_pool'][scope+':0']=value
                    elif defect=='wrong_close':value['candle_close_time']+=1
                    elif defect=='wrong_as_of':value['as_of']+=1
                    else:value['classification']['direction']='UNKNOWN'
                    self.assertEqual(combination_state(p,snap,default_combination_filters()[1])[0],'MISSING')
        p=fixture();ref=p['snapshots']['0']['engine_refs']['4h:TREND'];p['context_pool'][ref]['data_quality']='PARTIAL'
        self.assertEqual(combination_state(p,p['snapshots']['0'],default_combination_filters()[1])[0],'MATCHED')

    def test_no_future_changes_to_earlier_selection_and_chronological_membership(self):
        p=fixture();first=combination_analysis(p);p['snapshots']['2']['di']['abs_spread']=0
        second=combination_analysis(p)
        self.assertEqual(self.group(first,year='2024'),self.group(second,year='2024'))
        records=first['memberships'][1]['records'];self.assertEqual(records,sorted(records,key=lambda r:(r['known_time'],r['cohort'],r['stage'],r['id'])))
        self.assertTrue(any(r['cohort']=='candidate_next_open_12h' for r in records))
        # Candidate membership does not depend on eventual native-pivot membership.
        p['cases']=[];self.assertEqual(self.group(first)['matched_n'],self.group(combination_analysis(p))['matched_n'])

    def test_sell_direction_and_censored_windows_do_not_become_resolved_results(self):
        p=fixture();p['cases']=[];p['candidate_observations']=p['candidate_observations'][:1]
        r=p['candidate_observations'][0];r['side']='SELL';r['future']['12']['close_return_pct']=-2
        snap=p['snapshots']['0'];snap['di']['dominant']='PLUS'
        for ref in snap['engine_refs'].values():p['context_pool'][ref]['classification']['direction']='BEARISH'
        result=combination_analysis(p);g=self.group(result,filter_id='sell_context_5')
        self.assertEqual(g['matched']['mean_directional_close_return_pct'],2)
        r['future']['12'].update(status='CENSORED',complete=False,close_return_pct=None)
        g=self.group(combination_analysis(p),filter_id='sell_context_5')
        self.assertEqual(g['matched']['CENSORED'],1);self.assertIsNone(g['matched']['mean_directional_close_return_pct'])

    def test_custom_bounds_missing_stage_and_invalid_configs(self):
        p=fixture();spec=copy.deepcopy(default_combination_filters()[:1]);term=spec[0]['conditions'][0]['all'][0];term.update(min=12,max=20)
        self.assertEqual(combination_state(p,p['snapshots']['0'],spec[0])[0],'MATCHED')
        p['snapshots']['0']['di']['abs_spread']=20
        self.assertEqual(combination_state(p,p['snapshots']['0'],spec[0])[0],'NOT_MATCHED')
        self.assertEqual(combination_state(p,None,spec[0])[0],'MISSING')
        for bad in ([],spec+spec,[dict(spec[0],side='LONG')],[dict(spec[0],conditions=spec[0]['conditions'][:3])]):
            with self.assertRaises(ValueError):validate_combination_filters(bad)

    def test_cli_analysis_reuse_preserves_input_and_writes_separate_dimension(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'analysis.json';source.write_text(json.dumps(fixture()));before=source.read_bytes()
            result=subprocess.run([sys.executable,'study_btc_hour_sequences.py','--analysis-input',str(source),'--output-dir',str(root/'out')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads((root/'out/combinations_v1.json').read_text())
            self.assertEqual(report['groups'][0]['dimension'],'combination_filter')
            self.assertTrue((root/'out/combinations_v1.html').is_file());self.assertEqual(source.read_bytes(),before)
            self.assertFalse((root/'out/analysis_v1.json.gz').exists())
            self.assertIn('Chronological results',combination_visual(report))


if __name__=='__main__':unittest.main()
