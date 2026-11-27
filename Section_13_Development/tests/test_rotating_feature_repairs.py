"""A permanently unfinished analytical owner must not starve another repair."""
import json
import sqlite3
import unittest
from unittest.mock import patch
import test_fair_service as fixtures
from Section_4_Features import processor
from Section_1_Global_Core import work_priority,feature_runtime

class RotatingRepairs(unittest.TestCase):
    setUp=fixtures.FairService.setUp

    def turns(self,state,count,*,priority=None,fail=None):
        clock=[0.];calls=[]
        def advance(symbol,interval,cap,deadline):
            calls.append((symbol,interval));clock[0]+=.6
            if symbol==fail:raise ValueError('injected broken checkpoint')
            return 1  # Every pair remains pending forever.
        runtime=dict(time_budget=.5,max_bars=1000,priority=priority)
        with patch.object(processor,'_recover_runtime_format_job'),patch.object(processor,'_advance',side_effect=advance),patch.object(processor,'reset_pair'),patch.object(processor.time,'monotonic',side_effect=lambda:clock[0]),patch.object(feature_runtime,'read',return_value=runtime),patch.object(work_priority,'work_symbol',side_effect=AssertionError('analytical owner must not select feature turns')):
            for _ in range(count):
                processor.maintenance(['BTC','ENA','SUI'],['1m','15m'],rotation=state)
        return calls

    def test_every_coin_and_timeframe_gets_a_turn_while_owner_never_finishes(self):
        with patch.object(work_priority,'pending_feature_pair',return_value=True):
            state={};calls=self.turns(state,12)
        cycle=[(s,t) for s in ('BTC','ENA','SUI') for t in ('1m','15m')]
        self.assertEqual(calls,cycle*2)
        self.assertEqual(state['__feature_rotation__'],['SUI','15m'])

    def test_saved_cursor_survives_restart_and_policy_removal(self):
        with patch.object(work_priority,'pending_feature_pair',return_value=True):
            state={};first=self.turns(state,3)
            restored=json.loads(json.dumps(state));rest=self.turns(restored,3)
            self.assertEqual(first+rest,[(s,t) for s in ('BTC','ENA','SUI') for t in ('1m','15m')])
            restored['__feature_rotation__']=['REMOVED','1m']
            self.assertEqual(self.turns(restored,1),[('BTC','1m')])

    def test_failed_pair_does_not_retake_next_turn(self):
        with patch.object(work_priority,'pending_feature_pair',return_value=True):
            calls=self.turns({},4,fail='BTC')
        self.assertEqual(calls,[('BTC','1m'),('BTC','15m'),('ENA','1m'),('ENA','15m')])

    def test_operator_preference_does_not_replace_fair_queue(self):
        with patch.object(work_priority,'pending_feature_pair',return_value=True):
            calls=self.turns({},12,priority=dict(symbol='BTC',timeframe='1m'))
        self.assertEqual(calls[::2],[(s,t) for s in ('BTC','ENA','SUI') for t in ('1m','15m')])
        self.assertEqual(calls[1::2],[('BTC','1m')]*6)

    def test_actual_replay_job_selected_outside_owner_and_complete_pairs_skipped(self):
        from Section_4_Features.execution.components import current_signature
        with sqlite3.connect(self.features) as conn:
            conn.execute('CREATE TABLE feature_replay_jobs(symbol,interval)')
            conn.execute("INSERT INTO feature_replay_jobs VALUES ('ENA','1m')")
            conn.execute('CREATE TABLE feature_calculation_versions(symbol,interval,signature)')
            conn.executemany('INSERT INTO feature_calculation_versions VALUES (?,?,?)',[(s,'1m',current_signature()) for s in ('BTC','ENA','SUI')])
            conn.execute('UPDATE feature_engine_state SET last_open_time=4')
        calls=[]
        with patch.object(processor,'_recover_runtime_format_job'),patch.object(processor,'_advance',side_effect=lambda s,t,*a:calls.append((s,t)) or 1000),patch.object(work_priority,'_bulk_symbol','BTC'):
            processor.maintenance(['BTC','ENA','SUI'],['1m'],max_bars=1000,time_budget=5,rotation={})
        self.assertEqual(calls,[('ENA','1m')])

    def test_empty_universe_and_exhausted_budget_do_no_work(self):
        with patch.object(processor,'_advance') as advance:
            self.assertEqual(processor.maintenance([],['1m'],rotation={}),0)
            self.assertEqual(processor.maintenance(['BTC'],['1m'],time_budget=0,rotation={}),0)
            advance.assert_not_called()

class RealRepairRotation(unittest.TestCase):
    def raw_features(self):
        import test_selective_features as fixtures
        return fixtures.SelectiveFeatures.raw_features(self)

    def test_two_real_jobs_advance_and_resume_without_owner_completion(self):
        from contextlib import closing
        import test_selective_features as selective_fixtures
        from Section_4_Features.execution import checkpoint,selective
        from Section_4_Features.execution.engine import Engine
        from Section_1_Global_Core.memory_storage.Storage import db,features_store
        # Reuse isolated stores and a real committed 220-candle checkpoint.
        selective_fixtures.SelectiveFeatures.setUp(self)
        selective_fixtures.SelectiveFeatures.config(self,rsiLen=11)
        clients=[dict(c,symbol='ENAUSDT') for c in self.clients]
        other=Engine('ENAUSDT','1m');packets=[other.step(c) for c in clients]
        db.write_klines(clients);db.write_features(packets)
        with closing(features_store.open_db()) as conn,conn:
            conn.execute('INSERT INTO feature_engine_state VALUES (?,?,?,?)',('ENAUSDT','1m',clients[-1]['open_time'],checkpoint.dump(other,(0,0))))
        for symbol in ('ETHUSDT','ENAUSDT'):
            processor._prepare_engine(symbol,'1m',processor._load(symbol,'1m',(0,0)),(0,0))
        real_advance=processor._advance;clock=[0.];state={}
        def batch(*args,**kwargs):
            result=real_advance(*args,**kwargs);clock[0]+=.6;return result
        with patch.object(processor,'_advance',side_effect=batch),patch.object(processor.time,'monotonic',side_effect=lambda:clock[0]),patch.object(work_priority,'_bulk_symbol','ETHUSDT'):
            for _ in range(2):
                self.assertEqual(processor.maintenance(['ETHUSDT','ENAUSDT'],['1m'],max_bars=10,time_budget=.5,rotation=state),50)
            with closing(features_store.open_db()) as conn:
                for symbol in ('ETHUSDT','ENAUSDT'):
                    job=selective.read_job(conn,symbol,'1m')
                    self.assertEqual(job['last_time'],self.clients[49]['open_time'])
                    self.assertLess(job['last_time'],job['target'])
            processor._ENGINES.clear();state=json.loads(json.dumps(state))
            self.assertEqual(processor.maintenance(['ETHUSDT','ENAUSDT'],['1m'],max_bars=10,time_budget=.5,rotation=state),50)
            with closing(features_store.open_db()) as conn:
                self.assertEqual(selective.read_job(conn,'ETHUSDT','1m')['last_time'],self.clients[99]['open_time'])
                self.assertEqual(selective.read_job(conn,'ENAUSDT','1m')['last_time'],self.clients[49]['open_time'])
