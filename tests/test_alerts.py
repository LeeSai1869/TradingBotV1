"""Stored/live alert conditions, isolation, deduplication and durable login."""
import json
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
import test_data_admin as fixtures
from Section_11_UI_UX.server import alerts, auth
from Section_1_Global_Core import data_admin, data_policy, orchestrator
from Section_1_Global_Core.memory_storage.Storage import db


class AlertTests(unittest.TestCase):
    def setUp(self): fixtures.DataAdminTests.setUp(self)

    def rule(self,**kwargs):
        return dict(name='My alert',symbol='BTCUSDT',interval='1m',field='features.adx',operator='crosses_above',value=25,target_field=None,repeat='once',sound='chime',notify=True,enabled=True,mode='closed') | kwargs

    def create(self,**kwargs):
        with patch.object(alerts.time,'time',return_value=120): return alerts.save('admin',self.rule(**kwargs))

    def add_bar(self,t,**features):
        row=dict(self.rows[0],open_time=t,close_time=t+59999)
        db.write_klines([row])
        if features: db.write_features([dict(symbol='BTCUSDT',interval='1m',open_time=t,**features)])

    def test_closed_cross_waits_for_features_and_fires_exactly_once(self):
        db.write_features([dict(symbol='BTCUSDT',interval='1m',open_time=60000,adx=20)])
        key=self.create()
        self.add_bar(120000)
        alerts.evaluate_once()
        self.assertEqual(alerts.list_rules('admin')[0]['status'],'Waiting for stored features')
        self.assertEqual(alerts.events('admin',0)['events'],[])
        db.write_features([dict(symbol='BTCUSDT',interval='1m',open_time=120000,adx=30)])
        alerts.evaluate_once();alerts.evaluate_once()
        events=alerts.events('admin',0)['events']
        self.assertEqual(len(events),1);self.assertEqual(events[0]['value'],30)
        self.assertFalse(alerts.list_rules('admin')[0]['enabled'])
        self.assertEqual(alerts.events('user',0)['events'],[])
        with self.assertRaises(ValueError): alerts.save('user',self.rule(id=key))
        alerts.delete('user',key)
        self.assertEqual(len(alerts.list_rules('admin')),1)

    def test_field_comparisons_and_signed_thresholds(self):
        self.create(field='features.di_direction',operator='below',value=-5,repeat='per_bar')
        self.add_bar(120000,di_direction=-8)
        alerts.evaluate_once();alerts.evaluate_once()
        self.add_bar(180000,di_direction=-9);alerts.evaluate_once()
        self.assertEqual(len(alerts.events('admin',0)['events']),2)
        self.create(field='features.di_plus',target_field='features.di_minus',operator='above')
        self.add_bar(240000,di_plus=35,di_minus=20);alerts.evaluate_once()
        self.assertEqual(len(alerts.events('admin',0)['events']),3)

    def test_live_cross_uses_observed_ticks_and_deduplicates_per_candle(self):
        self.create(field='client.close',mode='live',repeat='per_bar')
        bar=dict(symbol='BTCUSDT',interval='1m',open_time=180000,time=180,client=dict(close=20,high=21,low=19))
        with patch.object(alerts.live_candle,'get_snapshot',return_value={'bar':bar,'status':'live'}):
            alerts.evaluate_once();self.assertEqual(alerts.events('admin',0)['events'],[])
            bar['client']['close']=30;alerts.evaluate_once();alerts.evaluate_once()
            self.assertEqual(len(alerts.events('admin',0)['events']),1)
            bar['client']['close']=20;alerts.evaluate_once()
            bar['client']['close']=30;alerts.evaluate_once()
            self.assertEqual(len(alerts.events('admin',0)['events']),1)
            bar['open_time']=240000;bar['client']['close']=20;alerts.evaluate_once()
            bar['client']['close']=30;alerts.evaluate_once()
            self.assertEqual(len(alerts.events('admin',0)['events']),2)
        self.assertEqual(alerts.events('admin',None)['events'],[])
        self.assertEqual(len(alerts.events('admin',None)['history']),2)

    def test_inactive_live_rule_makes_no_upstream_request(self):
        self.create(field='client.high',operator='above',mode='live')
        data_admin.set_timeframe('1m','inactive')
        with patch.object(alerts.live_candle,'get_snapshot') as live:
            alerts.evaluate_once();live.assert_not_called()
        self.assertIn('Suspended',alerts.list_rules('admin')[0]['status'])

    def test_validation_allows_live_ema_rsi_but_rejects_other_features_and_nonfinite_thresholds(self):
        for kwargs in [dict(mode='live',field='features.adx'),dict(value=float('nan')),dict(field='adcn.score'),dict(target_field='adcn.signal'),dict(mode='live',field='client.close',target_field='features.di_plus')]:
            with self.assertRaises(ValueError): alerts.validate(self.rule(**kwargs))
        alerts.validate(self.rule(mode='live',field='features.rsi'))
        alerts.validate(self.rule(mode='live',field='features.ema50'))
        self.assertIn('features.rsi',alerts.FIELDS)
        self.assertIn('features.di_direction',alerts.FIELDS)

    def test_past_backfill_does_not_trigger_new_rule(self):
        alerts.save('admin',self.rule(field='client.high',operator='above',value=1))
        self.add_bar(120000);alerts.evaluate_once()
        self.assertEqual(alerts.events('admin',0)['events'],[])

    def test_bounded_read_preserves_warmup_and_limits_processing_batch(self):
        for i in range(510): self.add_bar(120000+i*60000)
        all_rows=db.read_klines('BTCUSDT','1m',0,1000000000)
        self.assertEqual(db.read_klines_tail('BTCUSDT','1m',1000000000,500),all_rows[-500:])
        self.assertEqual(len(orchestrator._fetch_bars_since('BTCUSDT','1m',60000)),200)

    def test_stale_worker_snapshot_cannot_fire_edited_rule(self):
        key=self.create(field='client.high',operator='above',value=1)
        conn=alerts.open_db();rule=conn.execute('SELECT * FROM rules WHERE id=?',(key,)).fetchone();conn.close()
        self.add_bar(120000)
        with patch.object(alerts.time,'time',return_value=120): alerts.save('admin',self.rule(id=key,field='client.high',operator='above',value=1000))
        alerts.evaluate_rule(rule)
        self.assertEqual(alerts.events('admin',0)['events'],[])
        self.assertEqual(alerts.list_rules('admin')[0]['value'],1000)

    def test_deleted_and_rebuilt_history_is_not_replayed(self):
        self.create(field='client.high',operator='above',value=1,repeat='per_bar')
        data_admin.delete_data(interval='1m');data_admin.set_timeframe('1m','active')
        self.add_bar(120000)
        with patch.object(alerts.time,'time',return_value=360): alerts.evaluate_once()
        self.assertEqual(alerts.events('admin',0)['events'],[])
        self.add_bar(360000)
        with patch.object(alerts.time,'time',return_value=421): alerts.evaluate_once()
        self.assertEqual(len(alerts.events('admin',0)['events']),1)

    def test_remember_me_survives_memory_reset_and_logout_revokes_token(self):
        salt='12'*16
        account=dict(role='admin',salt=salt,hash=auth.digest('long-password-test',salt))
        auth.USERS_FILE.write_text(json.dumps({'admin':account}))
        token=auth.login('admin','long-password-test',remember=True)
        auth.SESSIONS.clear()
        self.assertTrue(auth.identity(token)['remembered'])
        self.assertEqual(auth.identity(token)['role'],'admin')
        conn=auth._remember_db()
        self.assertNotEqual(conn.execute('SELECT token_hash FROM sessions').fetchone()[0],token);conn.close()
        auth.logout(token);self.assertEqual(auth.identity(token)['role'],'guest')
        token=auth.login('admin','long-password-test',remember=True)
        account['hash']=auth.digest('different-password',salt)
        auth.USERS_FILE.write_text(json.dumps({'admin':account}))
        self.assertEqual(auth.identity(token)['role'],'guest')

    def test_multiple_new_alerts_save_during_runner_processing_and_edit_preserves_identity(self):
        with ThreadPoolExecutor(1) as pool:
            with data_policy.locked():
                first=pool.submit(self.create,name='First').result(timeout=2)
                second=pool.submit(self.create,name='Second').result(timeout=2)
                third=pool.submit(self.create,name='Third').result(timeout=2)
        self.assertEqual(len({first,second,third}),3)
        self.assertEqual(len(alerts.list_rules('admin')),3)
        alerts.save('admin',self.rule(id=first,name='First edited'))
        self.assertEqual(len(alerts.list_rules('admin')),3)
        alerts.delete('admin',second)
        self.assertEqual({r['id'] for r in alerts.list_rules('admin')},{first,third})
