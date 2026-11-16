"""Real loopback workspace: configuration, input uploads, replay and persisted reports."""
import base64
import gzip
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from test_strategy_analyzer import source, config
from strategy_analyzer_workspace import Workspace, make_server, field_catalog


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.input=self.root/'source.json.gz'
        self.input.write_bytes(gzip.compress(json.dumps(source()).encode()))
        self.workspace=Workspace(self.root/'workspace',self.input)
        self.server=make_server(self.workspace,0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.base=f'http://127.0.0.1:{self.server.server_port}'

    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)

    def request(self,path,body=None,headers=None):
        request=Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with urlopen(request,timeout=20) as response:return response.status,response.headers,response.read()
        except HTTPError as response:return response.code,response.headers,response.read()

    def json(self,path,body=None,headers=None):
        status,_,raw=self.request(path,body,headers)
        return status,json.loads(raw)

    def wait(self,key):
        until=time.monotonic()+10
        while time.monotonic()<until:
            _,job=self.json('/api/job?id='+key)
            if job['state']!='running':return job
            time.sleep(.01)
        self.fail('Replay did not finish')

    def test_catalog_and_field_metadata_follow_selected_input(self):
        status,catalog=self.json('/api/catalog');self.assertEqual(status,200)
        self.assertEqual(catalog['default_input'],'selected-input')
        status,metadata=self.json('/api/input?id=selected-input');self.assertEqual(status,200)
        fields={f['id']:f for f in metadata['fields']}
        self.assertEqual(fields['feature.rsi']['kind'],'number')
        self.assertEqual(fields['event.di_plus_peak']['kind'],'boolean')
        self.assertIn('context.1d.REGIME.primary',fields)
        self.assertEqual(metadata['candles'],8)
        self.assertEqual(self.request('/assets/builder.js')[0],200)
        self.assertEqual(self.request('/assets/../../.git/config')[0],404)

    def test_compact_15m_input_chart_discovery_and_stop_replay(self):
        from test_pivot_discovery import source as spot_source, packed, config as spot_config
        raw = gzip.compress(json.dumps(packed(spot_source())).encode())
        status, uploaded = self.json('/api/upload', {'data':base64.b64encode(raw).decode(), 'name':'SUI 15m'})
        self.assertEqual(status,200)
        key = uploaded['id']
        status, meta = self.json('/api/input?id='+key)
        self.assertEqual((status,meta['symbol'],meta['timeframe'],meta['risk_budget_pct']),(200,'SUIUSDT','15m',.5))
        status, chart = self.json('/api/chart?id='+key+'&center=1800000&feature=di_minus')
        self.assertEqual(status,200)
        self.assertEqual(len(chart['bars']),14)
        self.assertEqual(chart['bars'][2]['feature'],50.)
        self.assertEqual(len(chart['markers']),5)
        status, comparison = self.json('/api/discovery?id='+key+'&control=failed_pivots')
        self.assertEqual(status,200)
        self.assertEqual(comparison['labels'],{'GE_1':1,'LT_1':1,'CENSORED':1})
        self.assertEqual(self.json('/api/chart?id='+key+'&feature=not_a_feature')[0],400)
        status, job = self.json('/api/run', {'input_id':key,'config':spot_config()})
        self.assertEqual(status,202)
        done = self.wait(job['id']);self.assertEqual(done['state'],'complete',done)
        _, result = self.json('/api/report?id='+done['report_id'])
        self.assertAlmostEqual(result['trades'][0]['net_pct'],-.5)
        self.assertEqual(self.request('/assets/pivot.js')[0],200)
        self.assertEqual(self.request('/assets/lightweight-charts.js')[0],200)

    def test_memory_batch_runs_coins_independently_and_persists_reports(self):
        from test_strategy_memory import StrategyMemory
        from test_strategy_trailing import config as trailing_config
        fixture=StrategyMemory();fixture.setUp();self.addCleanup(fixture.doCleanups)
        status,catalog=self.json('/api/catalog');self.assertEqual(status,200)
        self.assertIn('memory:BTCUSDT:1m',{i['id'] for i in catalog['inputs']})
        status,meta=self.json('/api/input?id=memory:BTCUSDT:1m');self.assertEqual(status,200)
        self.assertEqual(meta['mode'],'memory')
        self.assertIn('adcn.scalp_score',{f['id'] for f in meta['fields']})
        status,chart=self.json('/api/chart?id=memory:BTCUSDT:1m&feature=rsi');self.assertEqual(status,200)
        self.assertGreater(len(chart['bars']),0)
        c=trailing_config();c['branches'][0]['when']={'field':'price.close','op':'available'}
        status,job=self.json('/api/run',{'input_id':'memory:BTCUSDT:1m','symbols':['BTCUSDT','SUIUSDT'],'config':c})
        self.assertEqual(status,202);done=self.wait(job['id']);self.assertEqual(done['state'],'complete',done)
        self.assertEqual([r['symbol'] for r in done['coins']],['BTCUSDT','SUIUSDT'])
        reports=[]
        for row in done['coins']:
            self.assertEqual(row['state'],'complete',row)
            status,report=self.json('/api/report?id='+row['report_id']);self.assertEqual(status,200)
            self.assertEqual(report['contract']['symbol'],row['symbol']);reports.append(report)
        self.assertNotEqual(reports[0]['contract']['memory_digest'],reports[1]['contract']['memory_digest'])
        self.assertEqual(reports[0]['contract']['execution']['initial_capital'],reports[1]['contract']['execution']['initial_capital'])
        summary=json.loads((self.workspace.directory/'runs'/job['id']/'batch_summary.json').read_text())
        self.assertIn('market_cutoff',summary)
        self.assertTrue(all(r['contract']['observed_as_of']<=summary['market_cutoff'] for r in reports))
        self.assertEqual(self.json('/api/run',{'input_id':'memory:BTCUSDT:1m','symbols':['MISSINGUSDT'],'config':c})[0],400)

    def test_configuration_save_preserves_versions_and_restart(self):
        first=config();status,saved=self.json('/api/config',{'config':first});self.assertEqual(status,200)
        second=config();second['branches'][0]['when']['value']=0
        status,other=self.json('/api/config',{'config':second});self.assertEqual(status,200)
        self.assertNotEqual(saved['key'],other['key'])
        restarted=Workspace(self.root/'workspace',self.input)
        keys={c['key'] for c in restarted.configurations()}
        self.assertIn(saved['key'],keys);self.assertIn(other['key'],keys)
        self.assertEqual(self.json('/api/config',{'config':{'id':'bad'}})[0],400)

    def test_new_input_upload_changes_metadata_and_is_reusable(self):
        data=source();data['candles']=data['candles'][:5];data['observed_as_of']=5*3600000
        data['candles'][0]['features']['new_indicator']=12
        raw=gzip.compress(json.dumps(data).encode())
        status,uploaded=self.json('/api/upload',{'data':base64.b64encode(raw).decode()});self.assertEqual(status,200)
        status,metadata=self.json('/api/input?id='+uploaded['id'])
        self.assertEqual(metadata['candles'],5)
        self.assertIn('feature.new_indicator',[f['id'] for f in metadata['fields']])
        restarted=Workspace(self.root/'workspace',self.input)
        self.assertIn(uploaded['id'],restarted.input_paths)
        self.assertEqual(self.json('/api/upload',{'data':'not base64'})[0],400)
        self.assertEqual(self.json('/api/upload',{'data':base64.b64encode(b'{"version":"report"}').decode()})[0],400)

    def test_full_replay_persists_rich_report_and_same_cost_baseline(self):
        original=self.input.read_bytes();c=config();baseline=config();baseline['execution']['fee_bps_per_side']=20
        status,job=self.json('/api/run',{'input_id':'selected-input','config':c,'baseline_config':baseline,'report_fields':['feature.rsi']})
        self.assertEqual(status,202);done=self.wait(job['id']);self.assertEqual(done['state'],'complete',done)
        status,result=self.json('/api/report?id='+done['report_id']);self.assertEqual(status,200)
        self.assertEqual(result['summary']['closed'],2)
        self.assertEqual(result['comparison']['counts']['success_preserved'],1)
        self.assertEqual(result['comparison']['baseline_config']['execution']['fee_bps_per_side'],0)
        self.assertEqual(result['trades'][0]['buy_inputs']['feature.rsi@lag0']['value'],50)
        self.assertEqual(result['workspace']['input_id'],'selected-input')
        status,headers,raw=self.request('/api/download?id='+job['id'])
        self.assertEqual(status,200);self.assertEqual(json.loads(gzip.decompress(raw))['run_id'],result['run_id'])
        self.assertIn('attachment',headers['Content-Disposition'])
        status,_,html=self.request('/api/download?id='+job['id']+'&format=html')
        self.assertEqual(status,200);self.assertIn(b'Configure your report',html)
        self.assertEqual(self.input.read_bytes(),original)
        restarted=Workspace(self.root/'workspace',self.input)
        self.assertIn(job['id'],restarted.report_paths())

    def test_windows_apply_to_replay_not_just_report_filters(self):
        status,job=self.json('/api/run',{'input_id':'selected-input','config':config(),'since':3*3600000,'until':5*3600000})
        self.assertEqual(status,202);self.assertEqual(self.wait(job['id'])['state'],'complete')
        _,result=self.json('/api/report?id='+job['id'])
        self.assertEqual(result['candles_scanned'],2)
        self.assertEqual(result['contract']['since'],3*3600000)
        self.assertEqual(self.json('/api/run',{'input_id':'selected-input','config':config(),'since':5,'until':1})[0],400)

    def test_cross_origin_and_host_checks_reject_mutations(self):
        self.assertEqual(self.json('/api/config',{'config':config()},headers={'Origin':'https://example.com'})[0],403)
        self.assertEqual(self.json('/api/catalog',headers={'Host':'example.com'})[0],403)
        self.assertEqual(self.request('/api/config',{'config':config()},headers={'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.json('/api/report?id=../../.git/config')[0],400)
        self.assertEqual(self.json('/api/run',{'input_id':'missing','config':config()})[0],400)

    def test_one_running_replay_and_failed_jobs_report_errors(self):
        entered=threading.Event();release=threading.Event()
        def blocked(*args,**kwargs):
            entered.set();release.wait(5);raise ValueError('Injected source mismatch')
        with patch('strategy_analyzer_workspace.analyzer.analyze',side_effect=blocked):
            _,job=self.json('/api/run',{'input_id':'selected-input','config':config()})
            self.assertTrue(entered.wait(3))
            self.assertEqual(self.json('/api/run',{'input_id':'selected-input','config':config()})[0],409)
            release.set();done=self.wait(job['id'])
            self.assertEqual(done['state'],'failed');self.assertIn('source mismatch',done['error'])


if __name__=='__main__':unittest.main()
