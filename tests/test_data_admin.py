"""Role enforcement, runner policy, rollback and re-download on isolated stores."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_1_Global_Core import data_admin, data_policy, orchestrator
from Section_1_Global_Core.Symbols import symbols
from Section_1_Global_Core.memory_storage.Storage import db, klines_store, features_store, adcn_store
from Section_1_Global_Core.memory_storage.market_data import download_binance_history as downloader, update_klines as updater
from Section_11_UI_UX.server import auth, admin_routes


class DataAdminTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        stack = ExitStack(); self.addCleanup(stack.close)
        for module, attr, name in [(data_policy,'POLICY_FILE','policy.json'),(data_policy,'LOCK_FILE','lock'),
                (data_admin,'REGISTRY_FILE','symbols.json'),(symbols,'_SYMBOLS_JSON','symbols.json'),
                (auth,'USERS_FILE','users.json'),(orchestrator,'STATE_FILE','state.json'),
                (klines_store,'DB_PATH','klines.db'),(downloader,'DB_PATH','klines.db'),(updater,'DB_PATH','klines.db'),
                (features_store,'DB_PATH','features.db'),(adcn_store,'DB_PATH','decisions.db')]:
            stack.enter_context(patch.object(module, attr, self.root / name))
        self.registry = dict(schema_version=2, active_cap=50,
            approved=[dict(symbol='BTCUSDT'),dict(symbol='SUIUSDT')],
            top50=[dict(symbol='BTCUSDT'),dict(symbol='SUIUSDT'),dict(symbol='NEWUSDT')],
            disapproved=[dict(symbol='DOGEUSDT',reason='auto:meme')],pending=[dict(symbol='NEWUSDT')],staged=[])
        (self.root/'symbols.json').write_text(json.dumps(self.registry)); symbols.reload(); self.addCleanup(symbols.reload)
        updater._LAST_UPDATE_MS.clear()
        auth.SESSIONS.clear(); auth.ATTEMPTS.clear()
        downloader.open_db().close()
        self.rows = [dict(symbol=s,interval=iv,open_time=60000,close_time=119999,open=10,high=12,low=9,close=11,volume=5)
                     for s in ['BTCUSDT','SUIUSDT'] for iv in ['1m','3m']]
        db.write_klines(self.rows)
        db.write_features([dict(symbol=r['symbol'], interval=r['interval'], open_time=60000,ema50=10) for r in self.rows])
        db.write_adcn([dict(symbol=r['symbol'],interval=r['interval'],open_time=60000,signal_type='BUY') for r in self.rows])

    def server(self, role='guest', origin=None):
        class Request: pass
        server=Request(); server.headers={'Host':'127.0.0.1:8000'}
        if role!='guest':
            import time
            auth.SESSIONS[role]=(role,role,time.time()+100)
            server.headers['Cookie']=f'{auth.COOKIE}={role}'
        if origin: server.headers['Origin']=origin
        return server

    def test_delete_scope_preserves_other_data_and_registry_and_pauses(self):
        before=(self.root/'symbols.json').read_text()
        counts=data_admin.delete_data(interval='1m')
        self.assertEqual(counts,dict(candles=2,features=2,decisions=2))
        self.assertFalse(data_policy.enabled('BTCUSDT','1m'))
        self.assertTrue(data_policy.enabled('BTCUSDT','3m'))
        self.assertIsNone(db.last_kline_time('BTCUSDT','1m'))
        self.assertEqual(db.last_kline_time('BTCUSDT','3m'),60000)
        self.assertEqual((self.root/'symbols.json').read_text(),before)
        self.assertEqual(data_policy.read()['epochs']['interval:1m'],1)

    def test_coin_delete_is_scoped_and_inactive_retains_data(self):
        data_admin.set_coin('BTCUSDT','inactive')
        self.assertEqual(db.last_kline_time('BTCUSDT','1m'),60000)
        self.assertNotIn('BTCUSDT',data_policy.active_symbols())
        data_admin.set_coin('BTCUSDT','active')
        self.assertIn('BTCUSDT',data_policy.active_symbols())
        self.assertEqual(data_admin.delete_data(symbol='BTCUSDT')['candles'],2)
        self.assertEqual(db.last_kline_time('SUIUSDT','1m'),60000)
        self.assertIn('BTCUSDT',symbols.get_approved_symbols())

    def test_atomic_rollback_if_one_memory_rejects_deletion(self):
        conn=adcn_store.open_db()
        conn.execute("CREATE TRIGGER reject_delete BEFORE DELETE ON decisions BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        conn.commit();conn.close()
        import sqlite3
        with self.assertRaises(sqlite3.Error): data_admin.delete_data(interval='1m')
        self.assertEqual(db.last_kline_time('BTCUSDT','1m'),60000)
        self.assertEqual(db.last_feature_time('BTCUSDT','1m'),60000)
        self.assertFalse(data_policy.enabled('BTCUSDT','1m'))

    def test_roles_and_confirmation_cannot_be_bypassed_via_api(self):
        body=json.dumps(dict(interval='1m',confirmation='DELETE 1m'))
        for role,status in [('guest',401),('user',403)]:
            self.assertEqual(admin_routes.handle_post('/api/settings/delete',body,self.server(role))[0],status)
        self.assertEqual(admin_routes.handle_post('/api/settings/delete','{"interval":"1m"}',self.server('admin'))[0],400)
        self.assertEqual(admin_routes.handle_post('/api/settings/delete',body,self.server('admin','https://evil.example'))[0],403)
        self.assertEqual(db.last_kline_time('BTCUSDT','1m'),60000)
        self.assertEqual(admin_routes.handle_post('/api/settings/timeframes','{"interval":"3m","status":"inactive"}',self.server('user'))[0],403)
        self.assertEqual(admin_routes.handle_post('/api/settings/coins','{"symbol":"BTCUSDT","action":"disapprove"}',self.server('user'))[0],403)
        self.assertEqual(admin_routes.handle_post('/api/settings/delete',body,self.server('admin'))[0],200)

    def test_both_admin_settings_endpoints_reject_normal_users(self):
        from Section_11_UI_UX.server import routes
        for path in ['/api/settings/timeframes','/api/settings/coins']:
            self.assertEqual(routes.handle_get(path,'',self.server('user'))[0],403)
            self.assertEqual(routes.handle_get(path,'',self.server('guest'))[0],401)
            self.assertEqual(routes.handle_get(path,'',self.server('admin'))[0],200)

    def test_bulk_status_changes_report_eligibility_failures_and_require_admin(self):
        body=json.dumps({'symbols':['NEWUSDT','DOGEUSDT'],'action':'approve'})
        from Section_11_UI_UX.server import admin_routes
        self.assertEqual(admin_routes.handle_post('/api/settings/coins/batch',body,self.server('user'))[0],403)
        status,packet=admin_routes.handle_post('/api/settings/coins/batch',body,self.server('admin'))
        self.assertEqual(status,200)
        self.assertEqual([row['ok'] for row in packet['results']],[True,False])
        self.assertIn('NEWUSDT',symbols.get_active_symbols())
        self.assertIn('DOGEUSDT',symbols.get_disapproved_symbols())

    def test_registry_actions_preserve_entries_and_enforce_eligibility(self):
        data_admin.set_coin('NEWUSDT','approve')
        self.assertIn('NEWUSDT',symbols.get_active_symbols())
        data_admin.set_coin('NEWUSDT','disapprove')
        self.assertIn('NEWUSDT',symbols.get_disapproved_symbols())
        self.assertNotIn('NEWUSDT',data_policy.active_symbols())
        with self.assertRaises(ValueError): data_admin.set_coin('DOGEUSDT','approve')
        with self.assertRaises(ValueError): data_admin.set_coin('NEWUSDT','pending')

    def test_reactivate_deleted_pair_bootstraps_history_and_does_not_write_when_paused(self):
        data_admin.delete_data(interval='1m'); data_admin.set_timeframe('1m','active')
        page=[[120000,'10','12','9','11','5',179999]]
        conn=updater._open_db()
        try:
            with patch.object(updater,'_fetch',return_value=page) as fetch:
                self.assertEqual(updater.update_one('BTCUSDT','1m',conn),1)
                self.assertEqual(fetch.call_args.args[2],downloader.FALLBACK_START_MS)
            updater._LAST_UPDATE_MS.clear()
            def pause(*args):
                data_admin.set_timeframe('1m','inactive')
                return [[180000,'10','12','9','11','5',239999]]
            with patch.object(updater,'_fetch',side_effect=pause):
                self.assertEqual(updater.update_one('BTCUSDT','1m',conn),0)
            self.assertEqual(db.last_kline_time('BTCUSDT','1m'),120000)
        finally: conn.close()

    def test_newly_approved_coin_bootstraps_without_runner_restart(self):
        data_admin.set_coin('NEWUSDT','approve')
        self.assertIn('NEWUSDT', data_policy.active_symbols())
        page=[[120000,'10','12','9','11','5',179999]]
        conn=updater._open_db()
        try:
            with patch.object(updater,'_fetch',return_value=page) as fetch:
                self.assertEqual(updater.update_one('NEWUSDT','1m',conn),1)
                self.assertEqual(fetch.call_args.args[2],downloader.FALLBACK_START_MS)
            self.assertEqual(db.last_kline_time('NEWUSDT','1m'),120000)
        finally:
            conn.close()

    def test_backlog_full_page_continues_without_waiting_whole_interval(self):
        page=[[120000+i*60000,'10','12','9','11','5',179999+i*60000] for i in range(1000)]
        conn=updater._open_db()
        try:
            with patch.object(updater,'_fetch',return_value=page):
                self.assertEqual(updater.update_one('BTCUSDT','1m',conn),1000)
            self.assertNotIn(('BTCUSDT','1m'),updater._LAST_UPDATE_MS)
        finally: conn.close()

    def test_auth_passwords_and_session_roles(self):
        salt='12'*16
        auth.USERS_FILE.write_text(json.dumps({'admin':dict(role='admin',salt=salt,hash=auth.digest('long-password-example',salt))}))
        with self.assertRaises(ValueError): auth.login('admin','wrong')
        token=auth.login('admin','long-password-example')
        self.assertEqual(auth.identity(token)['role'],'admin')
        self.assertEqual(auth.identity('invented')['role'],'guest')

    def test_catchup_cannot_repopulate_data_deleted_during_calculation(self):
        from Section_4_Features import processor
        from types import SimpleNamespace
        conn=features_store.open_db()
        conn.execute("DELETE FROM features WHERE symbol='BTCUSDT' AND interval='1m'")
        conn.commit();conn.close()
        def delete_during_compute(**kwargs):
            data_admin.delete_data(interval='1m')
            return SimpleNamespace(valid=True,features={'ema50':10})
        with patch.object(processor,'build_feature_packet',side_effect=delete_during_compute):
            with self.assertRaises(RuntimeError): processor.catch_up('BTCUSDT','1m')
        self.assertIsNone(db.last_feature_time('BTCUSDT','1m'))
        self.assertIsNone(db.last_kline_time('BTCUSDT','1m'))

    def test_runner_replays_deleted_pair_after_reactivation_and_calculates_features(self):
        from Section_4_Features import processor
        orch=orchestrator.GlobalCoreOrchestrator()
        orch._state={'BTCUSDT|1m':60000}
        data_admin.delete_data(interval='1m');data_admin.set_timeframe('1m','active')
        page=[[120000+i*60000,'10','12','9',str(11+i*.1),'5',179999+i*60000] for i in range(20)]
        def ingest():
            conn=updater._open_db()
            try: return updater.update_one('BTCUSDT','1m',conn)
            finally: conn.close()
        with patch.object(updater,'_fetch',return_value=page),patch.object(orchestrator,'update_klines_all',side_effect=ingest),patch.object(data_policy,'active_symbols',return_value=['BTCUSDT']),patch.object(data_policy,'active_intervals',return_value=['1m']):
            orch.cycle()
        self.assertEqual(db.last_feature_time('BTCUSDT','1m'),page[-1][0])
        self.assertEqual(orch._state['BTCUSDT|1m'],page[-1][0])
        self.assertEqual(orch._state['__epochs__']['BTCUSDT|1m'],[0,1])

    def test_local_account_setup_creates_two_hashed_private_accounts(self):
        with patch('getpass.getpass',side_effect=['admin-secret-long','admin-secret-long','user-secret-long','user-secret-long']):
            auth.main()
        records=json.loads(auth.USERS_FILE.read_text())
        self.assertEqual(set(records),{'admin','user'})
        self.assertEqual(auth.USERS_FILE.stat().st_mode & 0o777,0o600)
        self.assertNotIn('admin-secret-long',auth.USERS_FILE.read_text())
        token=auth.login('user','user-secret-long')
        self.assertEqual(auth.identity(token)['role'],'user')
        auth.SESSIONS[token]=('user','user',0)
        self.assertEqual(auth.identity(token)['role'],'guest')

    def test_processor_failure_does_not_advance_watermark(self):
        orch=orchestrator.GlobalCoreOrchestrator()
        orch._state={'BTCUSDT|1m':0}
        def fail(ev): raise RuntimeError('expected test failure')
        orch._processors=[('test.processor',fail)]
        with patch.object(orchestrator,'update_klines_all',return_value=0),patch.object(data_policy,'active_symbols',return_value=['BTCUSDT']),patch.object(data_policy,'active_intervals',return_value=['1m']):
            orch.cycle()
        self.assertEqual(orch._state['BTCUSDT|1m'],0)
