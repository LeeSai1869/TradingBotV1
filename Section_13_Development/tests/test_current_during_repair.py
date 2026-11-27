"""Current valid indicators must progress independently of recursive pivot repair."""
from contextlib import closing
import json
import copy
import gzip
from pathlib import Path
import unittest
from unittest.mock import patch
import test_selective_features as fixtures
from test_complete_conversion import bar
from Section_4_Features import processor
from Section_4_Features.execution import components,selective
from Section_4_Features.execution.engine import Engine
from Section_1_Global_Core.memory_storage.Storage import db,features_store

class CurrentRepair(unittest.TestCase):
    setUp=fixtures.SelectiveFeatures.setUp
    config=fixtures.SelectiveFeatures.config
    finish=fixtures.SelectiveFeatures.finish
    raw_features=fixtures.SelectiveFeatures.raw_features
    def test_live_rows_continue_then_repair_merges_at_moving_cursor(self):
        params=self.config(rsiLen=11)
        processor._prepare_engine('ETHUSDT','1m',processor._load('ETHUSDT','1m',(0,0)),(0,0))
        with closing(features_store.open_db()) as conn:
            job=selective.read_job(conn,'ETHUSDT','1m')
            self.assertIsNotNone(job)
        # Resume a job that has already made historical progress.
        self.assertEqual(processor._advance('ETHUSDT','1m',10),50)
        processor._ENGINES.clear()
        clients=[bar(i,110+(i%9)) for i in range(220,225)]
        db.write_klines(clients)
        expected=[self.engine.step(c) for c in clients]
        self.assertEqual(processor._advance('ETHUSDT','1m',recent_only=True),5)
        with closing(features_store.open_db()) as conn:
            job=selective.read_job(conn,'ETHUSDT','1m')
            self.assertEqual(job['target'],clients[-1]['open_time'])
        from Section_1_Global_Core.pipeline_scheduler import pending_sources
        required=features_store.decision_fields()+['c','close']
        self.assertEqual(pending_sources(['ETHUSDT'],['1m'],require_history=False),[('ETHUSDT','1m')])
        self.assertEqual(pending_sources(['ETHUSDT'],['1m'],require_history=False,required_columns=required),[])
        with closing(features_store.open_db()) as conn,conn:
            conn.execute('UPDATE feature_replay_jobs SET signature=?',('stale-signature',))
        self.assertEqual(pending_sources(['ETHUSDT'],['1m'],require_history=False,required_columns=required),[('ETHUSDT','1m')])
        with closing(features_store.open_db()) as conn,conn:
            conn.execute('UPDATE feature_replay_jobs SET signature=?',(job['signature'],))
        rows=self.raw_features()[-5:]
        for row,wanted in zip(rows,expected):
            for field in ('ema50','di_plus','di_minus','adx','atr','volume_ma'):
                self.assertEqual(row[field],wanted[field],field)
            self.assertIsNone(row['rsi'])
        processor._ENGINES.clear()
        self.finish()
        fresh=Engine('ETHUSDT','1m',params)
        all_expected=[fresh.step(c) for c in self.clients+clients]
        for row,wanted in zip(self.raw_features(),all_expected):
            for field in ('ema50','di_plus','rsi'):
                self.assertEqual(row[field],wanted[field],field)
        next_client=bar(225,115)
        db.write_klines([next_client]);processor.catch_up('ETHUSDT','1m')
        wanted=fresh.step(next_client);row=self.raw_features()[-1]
        for field in ('ema50','di_plus','rsi'):self.assertEqual(row[field],wanted[field],field)

    def test_actual_legacy_pivot_repair_keeps_current_indicators_and_preview_live(self):
        from Section_4_Features.execution import checkpoint
        fixture=json.loads(gzip.decompress((Path(__file__).with_name('fixtures')/'legacy-pivot-checkpoint.json.gz').read_bytes()))
        from Section_1_Global_Core.memory_storage.Storage import klines_store
        with closing(klines_store.open_db()) as conn,conn:conn.execute('DELETE FROM klines')
        with closing(features_store.open_db()) as conn,conn:
            conn.execute('DELETE FROM features');conn.execute('DELETE FROM feature_engine_state')
            conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('ETHUSDT','1m',fixture['clients'][-1]['open_time'],fixture['state']))
        db.write_klines(fixture['clients']);db.write_features(fixture['features']);processor._ENGINES.clear()
        old=checkpoint.restore('ETHUSDT','1m',fixture['state'],(0,0))
        processor._prepare_engine('ETHUSDT','1m',processor._load('ETHUSDT','1m',(0,0)),(0,0))
        clients=[dict(fixture['clients'][-1],open_time=i*60000,close_time=(i+1)*60000-1,close=110+i%5) for i in range(150,153)]
        db.write_klines(clients)
        wanted=[old.step(c) for c in clients]
        self.assertEqual(processor._advance('ETHUSDT','1m',recent_only=True),3)
        stable=components.catalog().unaffected_plan(frozenset(selective.changed(processor._load('ETHUSDT','1m',(0,0))))).columns
        for actual,expected in zip(self.raw_features()[-3:],wanted):
            for field in sorted(stable & expected.keys() & actual.keys()):
                if isinstance(actual[field],float) and isinstance(expected[field],float):
                    self.assertAlmostEqual(actual[field],expected[field],places=10,msg=field)
                else:self.assertEqual(actual[field],expected[field],field)
            self.assertIsNone(actual['pivot_rules_version'])
        current=dict(clients[-1],open_time=153*60000,close_time=154*60000-1)
        preview=processor.preview('ETHUSDT','1m',current)
        full_preview=copy.deepcopy(old).step(current,is_confirmed=False,is_realtime=True)
        for field in ('ema50','rsi','di_plus'):self.assertEqual(preview[field],full_preview[field],field)
        self.assertIsNone(preview['pivot_rules_version'])
        processor._ENGINES.clear();self.finish()
        full=Engine('ETHUSDT','1m')
        expected=[full.step(c) for c in fixture['clients']+clients]
        for actual,wanted in zip(self.raw_features(),expected):
            for field in ('ema50','rsi','di_plus','pivot_rules_version','pivot_reference_range','structure_events'):
                self.assertEqual(actual[field],wanted[field],field)

    def test_current_commit_failure_keeps_checkpoint_and_rows_unchanged(self):
        self.config(rsiLen=11)
        client=bar(220,114);db.write_klines([client])
        from Section_1_Global_Core.memory_storage.Storage import atr_slope_reads
        with closing(features_store.open_db()) as conn:
            before=conn.execute('SELECT last_open_time FROM feature_engine_state').fetchone()[0]
        with patch.object(atr_slope_reads,'retire_written',side_effect=ValueError('injected failure')):
            with self.assertRaisesRegex(ValueError,'injected failure'):
                processor._advance('ETHUSDT','1m',recent_only=True)
        with closing(features_store.open_db()) as conn:
            self.assertEqual(conn.execute('SELECT last_open_time FROM feature_engine_state').fetchone()[0],before)
            self.assertFalse(features_store.has_row(conn,'ETHUSDT','1m',client['open_time']))
        self.assertEqual(processor._advance('ETHUSDT','1m',recent_only=True),1)

    def test_current_repair_never_skips_a_missing_raw_candle(self):
        self.config(rsiLen=11)
        clients=[bar(i,112) for i in (220,222)]
        db.write_klines(clients)
        self.assertEqual(processor._advance('ETHUSDT','1m',recent_only=True),1)
        self.assertEqual(processor._advance('ETHUSDT','1m',recent_only=True),0)
        with closing(features_store.open_db()) as conn:
            self.assertEqual(conn.execute('SELECT last_open_time FROM feature_engine_state').fetchone()[0],clients[0]['open_time'])
            self.assertFalse(features_store.has_row(conn,'ETHUSDT','1m',clients[1]['open_time']))

    def test_decisions_wait_when_repair_affects_their_inputs(self):
        self.config(adxLen=12)
        processor._prepare_engine('ETHUSDT','1m',processor._load('ETHUSDT','1m',(0,0)),(0,0))
        from Section_1_Global_Core.pipeline_scheduler import pending_sources
        self.assertEqual(pending_sources(['ETHUSDT'],['1m'],require_history=False,required_columns=features_store.decision_fields()+['c','close']),[('ETHUSDT','1m')])
