"""Real SQLite strategy isolation, sparse events, lifecycle and HTTP boundaries."""
from dataclasses import replace
import hashlib
import json
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from Section_13_Development.tests import test_di_decisions as fixtures
SETUP=fixtures.SETUP
di=fixtures.di
from Section_1_Global_Core import data_admin, strategy_management as manager
from Section_1_Global_Core.memory_storage.Storage import adcn_store, strategy_store as store, features_store, db, klines_store
from Section_8_Decision_Engine import processor, strategy_worker, strategy_registry as registry
from Section_11_UI_UX.server import alerts, strategy_routes


class StrategyLifecycle(unittest.TestCase):
    setUp=fixtures.DiMemoryTests.setUp
    seed=fixtures.DiMemoryTests.seed

    def prepare(self):
        self.stack.enter_context(patch.object(data_admin,'catalog',return_value={'approved':[{'symbol':s} for s in ('ETHUSDT','BTCUSDT','ENAUSDT')]}))

    def enable(self,version=3,*,symbol='ETHUSDT',interval='1m',start_at=0,select=True):
        return manager.change('enable',dict(symbol=symbol,interval=interval,strategy_id='di_turning_point',version=version,start_at=start_at,select=select))['instance_id']

    def reverse_version(self):
        original=registry.require('di_turning_point',3)
        def evaluate(previous,current):
            decision=original.module.evaluate(previous,current)
            if decision['signal_type']:
                side='SELL' if decision['signal_type']=='BUY' else 'BUY'
                return dict(signal_type=side,decision_state=side,trigger='TEST_VERSION_4')
            return decision
        module=SimpleNamespace(FIELDS=original.module.FIELDS,LOOKBACK=2,evaluate=evaluate)
        new=replace(original,version=4,name='Test reverse v4',module=module,fingerprint='test-version-4')
        self.stack.enter_context(patch.dict(registry.DEFINITIONS,{('di_turning_point',4):new}))

    def checkpoint(self,identity):
        with adcn_store.open_db() as conn:return store.checkpoint(conn,identity)

    def history(self,identity):return manager.history(identity)['events']

    def test_only_signals_are_stored_and_checkpoint_advances_through_wait_bars(self):
        self.prepare();self.seed([*SETUP,di(15,27),di(16,26)])
        identity=self.enable()
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),4)
        events=self.history(identity);self.assertEqual(len(events),1);self.assertEqual(events[0]['side'],'BUY')
        self.assertEqual(self.checkpoint(identity)['last_open_time'],180000)
        with adcn_store.open_db() as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],0)
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',180000))
        page=db.read_state_page('ETHUSDT','1m',4)
        self.assertTrue(page['bars'][-1]['decision_ready'])
        self.assertEqual(alerts.number(page['bars'][-1],'decision.buy'),0)
        self.assertEqual(page['bars'][2]['adcn']['strategy_instance_id'],identity)
        processor._CACHE.clear();self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.assertEqual(len(self.history(identity)),1)
        self.assertEqual(events[0]['payload']['strategy']['version'],3)
        self.assertEqual(events[0]['payload']['evidence']['current']['close'],101)

    def test_switch_keeps_both_calculating_but_only_selected_events_are_presented(self):
        self.prepare();self.reverse_version();self.seed()
        original=self.enable();replacement=self.enable(4)
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),6)
        self.assertEqual(self.history(original)[0]['side'],'BUY')
        self.assertEqual(self.history(replacement)[0]['side'],'SELL')
        bar=db.read_state_page('ETHUSDT','1m',1)['bars'][0]
        self.assertEqual(bar['momentum']['signal_type'],'SELL')
        self.assertEqual(alerts.number(bar,'decision.sell'),1)
        self.assertEqual(bar['adcn']['strategy_instance_id'],replacement)
        prior_revision=db.read_state_page('ETHUSDT','1m',1)['strategy_revision']
        manager.change('select',{'instance_id':original})
        switched=db.read_state_page('ETHUSDT','1m',1)
        self.assertGreater(switched['strategy_revision'],prior_revision)
        self.assertEqual(switched['bars'][0]['momentum']['signal_type'],'BUY')
        with adcn_store.open_db() as conn:self.assertTrue(all(item['enabled'] for item in store.instances(conn)))
        self.assertNotEqual(json.loads(self.checkpoint(original)['state'])['last_signal'],json.loads(self.checkpoint(replacement)['state'])['last_signal'])

    def test_inactive_selected_strategy_does_not_write_or_recover_legacy_evidence(self):
        from Section_1_Global_Core import decision_evidence
        self.prepare();self.seed();identity=self.enable();processor.catch_up('ETHUSDT','1m')
        manager.change('deactivate',{'instance_id':identity})
        before=self.checkpoint(identity)
        self.seed([*SETUP,di(15,27),di(16,26)])
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.assertEqual(decision_evidence.recover_one('ETHUSDT','1m'),0)
        self.assertEqual(self.checkpoint(identity),before)
        page=db.read_state_page('ETHUSDT','1m',4)
        self.assertTrue(all(bar['momentum'] is None and bar['adcn'] is None for bar in page['bars']))
        self.assertEqual(alerts.number(page['bars'][-1],'decision.buy'),0)
        self.assertEqual(len(self.history(identity)),1)
        self.assertFalse(processor.pending_history('ETHUSDT',['1m']))

    def test_resume_skips_paused_candles_and_preserves_last_direction(self):
        self.prepare();self.seed();identity=self.enable();processor.catch_up('ETHUSDT','1m')
        manager.change('deactivate',{'instance_id':identity})
        self.seed([*SETUP,di(15,27),*SETUP,di(15,27)])
        self.enable()
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        state=json.loads(self.checkpoint(identity)['state'])
        self.assertEqual(state['last_signal'],'BUY')
        self.assertEqual(len(self.history(identity)),1)

    def test_delete_requires_pause_exact_preview_and_leaves_other_pairs_and_market_data(self):
        self.prepare();self.seed();self.seed(symbol='BTCUSDT')
        identity=self.enable();other=self.enable(symbol='BTCUSDT')
        processor.catch_up('ETHUSDT','1m');processor.catch_up('BTCUSDT','1m')
        before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (klines_store.DB_PATH,features_store.DB_PATH)]
        with self.assertRaisesRegex(ValueError,'Deactivate'):manager.change('preview_delete',{'instance_id':identity})
        manager.change('deactivate',{'instance_id':identity})
        plan=manager.change('preview_delete',{'instance_id':identity})
        with self.assertRaises(ValueError):manager.change('delete',plan)
        manager.change('delete',{**plan,'confirmation':plan['required_confirmation']})
        with adcn_store.open_db() as conn:
            self.assertIsNone(store.instance(conn,identity));self.assertIsNone(store.checkpoint(conn,identity))
            self.assertEqual(store.events(conn,identity),[])
            self.assertIsNotNone(store.pair(conn,'ETHUSDT','1m'))
        self.assertEqual(len(self.history(other)),1)
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.assertEqual(before,[hashlib.sha256(p.read_bytes()).hexdigest() for p in (klines_store.DB_PATH,features_store.DB_PATH)])
        new=self.enable();self.assertNotEqual(new,identity)

    def test_stale_delete_preview_does_not_delete_new_records(self):
        self.prepare();self.seed();identity=self.enable();processor.catch_up('ETHUSDT','1m')
        manager.change('deactivate',{'instance_id':identity});plan=manager.change('preview_delete',{'instance_id':identity})
        with adcn_store.open_db() as conn:conn.execute("INSERT INTO strategy_events VALUES (?,?,?,'SELL',1,'{}',1)",(identity,'test',999999))
        with self.assertRaises(ValueError):manager.change('delete',plan)
        self.assertEqual(len(self.history(identity)),2)

    def test_failed_checkpoint_rolls_back_events_and_restart_retries_once(self):
        self.prepare();self.seed();identity=self.enable()
        with adcn_store.open_db() as conn:conn.execute("CREATE TRIGGER reject_strategy_checkpoint BEFORE INSERT ON strategy_checkpoints BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):processor.catch_up('ETHUSDT','1m')
        self.assertEqual(self.history(identity),[]);self.assertIsNone(self.checkpoint(identity))
        with adcn_store.open_db() as conn:conn.execute('DROP TRIGGER reject_strategy_checkpoint')
        processor.catch_up('ETHUSDT','1m');processor.catch_up('ETHUSDT','1m')
        self.assertEqual(len(self.history(identity)),1)

    def test_disable_during_calculation_cannot_commit_a_late_event(self):
        self.prepare();self.seed();identity=self.enable();original=store.commit
        def disable(*args,**kwargs):
            manager.change('deactivate',{'instance_id':identity});return original(*args,**kwargs)
        with patch.object(store,'commit',side_effect=disable):self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.assertEqual(self.history(identity),[]);self.assertIsNone(self.checkpoint(identity))

    def test_epoch_changes_keep_old_history_in_a_separate_generation(self):
        self.prepare();self.seed();identity=self.enable();processor.catch_up('ETHUSDT','1m')
        with patch.object(features_store,'decision_generation',return_value=99):
            processor.catch_up('ETHUSDT','1m')
            self.assertEqual(db.read_adcn('ETHUSDT','1m',120000)['strategy_instance_id'],identity)
        self.assertEqual(len(self.history(identity)),2)
        self.assertEqual(len({event['epoch'] for event in self.history(identity)}),2)

    def test_pause_unmanaged_pair_prevents_legacy_calculation_and_markers(self):
        self.prepare();self.seed();manager.change('pause_pair',{'symbol':'ETHUSDT','interval':'1m'})
        self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        self.assertTrue(all(b['momentum'] is None for b in db.read_state_page('ETHUSDT','1m',3)['bars']))

    def test_two_coins_and_timeframes_keep_independent_histories(self):
        self.prepare();identities=[]
        for symbol,interval in [('ENAUSDT','1m'),('ENAUSDT','5m'),('BTCUSDT','1m')]:
            self.seed(symbol=symbol,interval=interval);identity=self.enable(symbol=symbol,interval=interval)
            processor.catch_up(symbol,interval);identities.append(identity)
            self.assertEqual(db.read_adcn(symbol,interval,120000)['strategy_instance_id'],identity)
        self.assertEqual(len(set(identities)),3)
        self.assertTrue(all(len(self.history(identity))==1 for identity in identities))

    def test_unknown_strategy_or_unregistered_pair_is_rejected(self):
        self.prepare()
        for overrides in ({'version':99},{'symbol':'FAKEUSDT'},{'interval':'0m'},{'start_at':True}):
            data=dict(symbol='ETHUSDT',interval='1m',strategy_id='di_turning_point',version=3,start_at=0,**{})
            data.update(overrides)
            with self.assertRaises(ValueError):manager.change('enable',data)

    def test_admin_and_origin_checks_precede_any_mutation(self):
        self.prepare();server=SimpleNamespace(headers={'Host':'127.0.0.1:8000','Origin':'https://evil.invalid'})
        for role,expected in [('guest',401),('user',403),('admin',403)]:
            with patch.object(strategy_routes.admin_routes,'user',return_value={'role':role}):
                self.assertEqual(strategy_routes.dispatch(strategy_routes.PATH,'',server,body='{}')[0],expected)
        self.assertFalse(adcn_store.DB_PATH.exists())
        server.headers['Origin']='http://127.0.0.1:8000'
        with patch.object(strategy_routes.admin_routes,'user',return_value={'role':'admin'}):
            data=dict(action='enable',symbol='ETHUSDT',interval='1m',strategy_id='di_turning_point',version=3,start_at=0)
            code,response=strategy_routes.dispatch(strategy_routes.PATH,'',server,body=json.dumps(data))
            self.assertEqual(code,200);self.assertIn('instance_id',response)
            self.assertEqual(strategy_routes.dispatch(strategy_routes.PATH,'',server)[0],200)

    def test_wrong_pair_binding_cannot_display_another_coins_events(self):
        self.prepare();self.seed();self.seed(symbol='BTCUSDT')
        own=self.enable();other=self.enable(symbol='BTCUSDT')
        processor.catch_up('ETHUSDT','1m');processor.catch_up('BTCUSDT','1m')
        with adcn_store.open_db() as conn:conn.execute("UPDATE strategy_pairs SET selected_id=? WHERE symbol='ETHUSDT'",(other,))
        self.assertIsNone(db.read_adcn('ETHUSDT','1m',120000))
        self.assertIsNotNone(db.read_adcn('BTCUSDT','1m',120000))

    def test_replaced_code_fails_closed_without_overwriting_history(self):
        self.prepare();self.seed();identity=self.enable()
        definition=registry.require('di_turning_point',3)
        with patch.dict(registry.DEFINITIONS,{('di_turning_point',3):replace(definition,fingerprint='changed')}):
            self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
            self.assertFalse(manager.catalog()['instances'][0]['source_available'])
        self.assertEqual(self.history(identity),[])

    def test_general_pair_deletion_also_clears_strategy_history_and_leaves_it_paused(self):
        self.prepare();self.seed();identity=self.enable();processor.catch_up('ETHUSDT','1m')
        result=data_admin.delete_data(interval='1m')
        self.assertEqual(result['decisions'],1)
        self.assertEqual(self.history(identity),[])
        with adcn_store.open_db() as conn:
            self.assertFalse(store.instance(conn,identity)['enabled'])
            self.assertIsNone(store.pair(conn,'ETHUSDT','1m')['selected_id'])

    def test_chart_reads_are_read_only_and_take_selection_and_events_from_one_snapshot(self):
        self.prepare();self.seed();identity=self.enable();processor.catch_up('ETHUSDT','1m')
        before=hashlib.sha256(adcn_store.DB_PATH.read_bytes()).hexdigest()
        page=db.read_state_page('ETHUSDT','1m',3)
        self.assertEqual(page['bars'][-1]['strategy_instance_id'],identity)
        self.assertEqual(page['bars'][-1]['adcn']['strategy_instance_id'],identity)
        self.assertEqual(before,hashlib.sha256(adcn_store.DB_PATH.read_bytes()).hexdigest())

    def test_legacy_recalculation_clears_stale_signal_without_erasing_archived_scores(self):
        from Section_1_Global_Core import data_policy
        self.seed();processor.catch_up('ETHUSDT','1m')
        db.write_adcn([dict(symbol='ETHUSDT',interval='1m',open_time=120000,signal_type='BUY',trigger='DI_TURNING_POINT_V3',scalp_score=77)])
        self.seed([*SETUP,di(15,40)])
        data_policy.write(dict(timeframes={},paused_coins=[],epochs={'symbol:ETHUSDT':1}))
        processor.catch_up('ETHUSDT','1m')
        result=db.read_adcn('ETHUSDT','1m',120000)
        self.assertIsNone(result['signal_type']);self.assertEqual(result['scalp_score'],77)

    def test_registered_strategy_can_consume_features_beyond_di_without_reading_stale_replay(self):
        self.prepare();self.seed()
        for opened in (0,60000,120000):db.write_features([dict(symbol='ETHUSDT',interval='1m',open_time=opened,formula_version=3,rsi=60)])
        original=registry.require('di_turning_point',3)
        def evaluate(previous,current):
            side='BUY' if current.get('rsi',0)>50 else None
            return dict(signal_type=side,decision_state=side or 'WAIT',trigger='TEST_RSI' if side else None)
        definition=replace(original,version=4,module=SimpleNamespace(FIELDS=('rsi','close'),LOOKBACK=0,evaluate=evaluate),fingerprint='test-rsi')
        with patch.dict(registry.DEFINITIONS,{('di_turning_point',4):definition}):
            identity=self.enable(4)
            with features_store.open_db() as conn:
                conn.execute('INSERT INTO feature_replay_jobs VALUES (?,?,?,?,?,?,?,?)',('ETHUSDT','1m','test',120000,60000,'[]',None,'["rsi"]'))
            self.assertEqual(processor.catch_up('ETHUSDT','1m'),2)
            self.assertEqual(self.checkpoint(identity)['last_open_time'],60000)
            self.assertEqual(len(self.history(identity)),1)
            with features_store.open_db() as conn:conn.execute('DELETE FROM feature_replay_jobs')
            self.assertEqual(processor.catch_up('ETHUSDT','1m'),1)
            self.assertEqual(json.loads(self.checkpoint(identity)['state'])['previous'],[])

    def test_first_switch_from_legacy_keeps_the_original_rule_running(self):
        self.prepare();self.reverse_version();self.seed();processor.catch_up('ETHUSDT','1m')
        replacement=self.enable(4)
        with adcn_store.open_db() as conn:
            instances=store.instances(conn,'ETHUSDT','1m')
            self.assertEqual(len(instances),2)
            old=next(item for item in instances if item['version']==3)
            self.assertTrue(old['enabled']);self.assertFalse(old['selected'])
            self.assertEqual(store.checkpoint(conn,old['id'])['last_open_time'],120000)
        sell=[di(30,10,adx=20,close=103),di(35,11,adx=21,close=102),di(27,15)]
        self.seed([*SETUP,di(15,27),*sell]);processor.catch_up('ETHUSDT','1m')
        self.assertEqual(self.history(old['id'])[-1]['side'],'SELL')
        self.assertEqual(db.read_adcn('ETHUSDT','1m',300000)['strategy_instance_id'],replacement)

    def test_start_now_can_emit_on_the_next_close_of_the_currently_forming_candle(self):
        self.prepare();opened=1795000020000;times=[opened-120000,opened-60000,opened]
        self.seed(times=times)
        with patch.object(manager.time,'time',return_value=(opened+10000)/1000):
            identity=manager.change('enable',dict(symbol='ETHUSDT',interval='1m',strategy_id='di_turning_point',version=3))['instance_id']
            self.assertEqual(processor.catch_up('ETHUSDT','1m'),0)
        with patch.object(strategy_worker.time,'time',return_value=(opened+60001)/1000):
            self.assertEqual(processor.catch_up('ETHUSDT','1m'),1)
        self.assertEqual(self.history(identity)[0]['open_time'],opened)
        self.assertEqual(self.history(identity)[0]['side'],'BUY')

    def test_deleting_history_does_not_allow_reusing_a_version_for_different_code(self):
        self.prepare();self.reverse_version();identity=self.enable(4)
        manager.change('deactivate',{'instance_id':identity})
        plan=manager.change('preview_delete',{'instance_id':identity})
        manager.change('delete',{**plan,'confirmation':plan['required_confirmation']})
        old=registry.require('di_turning_point',4)
        with patch.dict(registry.DEFINITIONS,{('di_turning_point',4):replace(old,fingerprint='different-code')}):
            with self.assertRaisesRegex(ValueError,'another fingerprint'):self.enable(4)
