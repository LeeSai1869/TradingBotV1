"""Approved rule parity, restart and real legacy-checkpoint selective repair."""
from contextlib import ExitStack,closing,nullcontext
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_4_Features.features import pivot_rules,market_structure
from Section_4_Features.execution import checkpoint,selective,components
from Section_4_Features.execution.engine import Engine
from Section_4_Features import processor
from Section_1_Global_Core.memory_storage.Storage import features_store,klines_store,adcn_store,db
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader

ROOT=Path(__file__).resolve().parents[2]


class ProductionRules(unittest.TestCase):
    def test_production_matches_all_528_approved_trial_confirmations_and_restarts(self):
        spec=importlib.util.spec_from_file_location('trial',ROOT/'Section_12_Research/experiments/pivot_confirmation/trial.py')
        trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)
        source=json.loads(gzip.decompress((ROOT/'Section_12_Research/reports/pivot_debug/ENAUSDT-15m-20261126/stored-pivots.json.gz').read_bytes()))
        first=source['candles'][0];s=trial.seed_from_row(first)
        state=pivot_rules.seed([float(p) for p in s['pair']],s['direction'],float(s['candidate']['price']),s['candidate']['origin'],0,first['close'],first['close_time'])
        actual=[]
        for i,row in enumerate(source['candles'][1:],1):
            if i%137==0:state=json.loads(json.dumps(state))
            event=pivot_rules.advance(state,row,i)
            if event:actual.append(event)
        keys=('type','price','origin_time','confirmation_time','known_time','reference_range','threshold','reverse_closes')
        expected=trial.simulate(source['candles'])['events']
        self.assertEqual(len(actual),528)
        self.assertEqual([{k:e[k] for k in keys} for e in actual],[{k:e[k] for k in keys} for e in expected])
    def test_new_rule_survives_structure_reset_and_exports_observable_reference(self):
        e=Engine('BTCUSDT','15m')
        import math
        for i in range(100):
            c=100+math.sin(i/5)*10
            e.step(dict(symbol='BTCUSDT',interval='15m',open_time=i*900000,close_time=(i+1)*900000-1,open=c,high=c+2,low=c-2,close=c,volume=10))
        self.assertIn('swingPivotRulesState',e.context.persistent)
        saved=copy.deepcopy(e.context.persistent['swingPivotRulesState'])
        e.context.persistent['activeBOS']=2;e.context.persistent['activeBOSType']='bearishBOS'
        i=100;row=e.step(dict(symbol='BTCUSDT',interval='15m',open_time=i*900000,close_time=(i+1)*900000-1,open=110,high=112,low=108,close=110,volume=10))
        self.assertEqual(row['pivot_rules_version'],'confirmed-pair-v1')
        self.assertEqual(e.context.persistent['swingPivotRulesState']['version'],saved['version'])
        self.assertGreater(row['pivot_reference_range'],0)
        self.assertNotEqual(row['candidate_pivot'],0)
    def test_hourly_and_four_hour_rules_and_checkpoint_parity(self):
        import math
        results=[]
        for interval,duration in [('1h',3600000),('4h',14400000)]:
            engine=Engine('ENAUSDT',interval);restored=None;events=[]
            for i in range(160):
                c=100+math.sin(i/5)*10
                row=dict(symbol='ENAUSDT',interval=interval,open_time=i*duration,close_time=(i+1)*duration-1,open=c,high=c+1,low=c-1,close=c,volume=10)
                packet=engine.step(row)
                if restored:
                    other=restored.step(row)
                    keys=[k for k in packet if any(word in k for word in ('pivot','swing','structure','protected'))]
                    self.assertEqual({k:packet[k] for k in keys},{k:other[k] for k in keys})
                if i==79:restored=checkpoint.restore('ENAUSDT',interval,checkpoint.dump(engine,(0,0)),(0,0))
                events.extend((e['type'],e['price']) for e in json.loads(packet['structure_events']) if e['type'].startswith('PIVOT_'))
            results.append(events)
        self.assertGreater(len(results[0]),4);self.assertEqual(results[0],results[1])
    def test_conversion_override_retains_native_rule_and_is_idempotent(self):
        from Section_4_Features.conversion.pivot_override import apply
        source=Path(market_structure.__file__).read_text()
        self.assertEqual(apply(source),source)
        helper=(ROOT/'Section_4_Features/conversion/overrides/confirmed_pair_swings.py.inc').read_text()
        self.assertTrue(source.endswith(helper))


class LegacyRuleRepair(unittest.TestCase):
    def test_old_checkpoint_repair_matches_fresh_engine_and_preserves_unrelated_values(self):
        fixture=json.loads(gzip.decompress((Path(__file__).with_name('fixtures')/'legacy-pivot-checkpoint.json.gz').read_bytes()))
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            for store,name in ((features_store,'features'),(klines_store,'klines'),(adcn_store,'ADCN'),(downloader,'klines')):
                stack.enter_context(patch.object(store,'DB_PATH',Path(directory)/(name+'.db')))
            stack.enter_context(patch.object(processor,'_epoch',return_value=(0,0)))
            stack.enter_context(patch.object(processor.data_policy,'enabled',return_value=True))
            stack.enter_context(patch.object(processor.data_policy,'locked',side_effect=nullcontext))
            downloader.open_db().close();processor._ENGINES.clear();db.write_klines(fixture['clients']);db.write_features(fixture['features'])
            fields=('ema7','ema50','rsi','di_plus','di_minus','adx','atr','vp_poc','volume_ma')
            with closing(features_store.open_db()) as conn,conn:
                conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('ETHUSDT','1m',fixture['clients'][-1]['open_time'],fixture['state']))
                before=conn.execute('SELECT '+','.join(fields)+' FROM features ORDER BY open_time').fetchall()
                engine=checkpoint.restore('ETHUSDT','1m',fixture['state'],(0,0));selective.prepare(conn,engine,(0,0))
                job=conn.execute('SELECT changed,columns FROM feature_replay_jobs').fetchone();columns=json.loads(job[1])
                self.assertFalse(set(fields)&set(columns));self.assertIn('pivot_reference_range',columns)
                self.assertIn('swingPivotRulesState',components.catalog().plan(json.loads(job[0])).state_writes)
            for _ in range(10):
                processor.catch_up('ETHUSDT','1m')
                with closing(features_store.open_db()) as conn:
                    if not selective.read_job(conn,'ETHUSDT','1m'):break
                processor._ENGINES.clear()
            else:self.fail('Bounded repair did not finish')
            full=Engine('ETHUSDT','1m');expected=[full.step(c) for c in fixture['clients']]
            with closing(features_store.open_db()) as conn:
                actual=features_store.read_range(conn,'ETHUSDT','1m',0,10**12,mask_pending=False)
                self.assertEqual(before,conn.execute('SELECT '+','.join(fields)+' FROM features ORDER BY open_time').fetchall())
                self.assertEqual(conn.execute('SELECT generation FROM feature_calculation_versions').fetchone()[0],0)
                for row,wanted in zip(actual,expected):
                    for name in columns:
                        a,b=row.get(name),wanted.get(name)
                        if isinstance(a,str) and isinstance(b,(int,float)):self.assertEqual(a,str(b))
                        else:self.assertEqual(a,b,(row['open_time'],name))
                state=checkpoint.restore('ETHUSDT','1m',conn.execute('SELECT state FROM feature_engine_state').fetchone()[0],(0,0))
                self.assertEqual(state.context.persistent['swingPivotRulesState'],full.context.persistent['swingPivotRulesState'])
