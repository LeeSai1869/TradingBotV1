"""Current Decision Engine alerts are durable and independent of the open chart."""
import unittest
from unittest.mock import patch
import test_data_admin as fixtures
from Section_11_UI_UX.server import alerts, alert_routes
from Section_1_Global_Core.memory_storage.Storage import db


class SignalAlerts(unittest.TestCase):
    server=fixtures.DataAdminTests.server
    def setUp(self):fixtures.DataAdminTests.setUp(self)

    def arm(self):
        with patch.object(alerts.time,'time',return_value=120):
            alerts.signal_preferences('admin')
            alerts.sync_signal_rules()

    def add(self,side=None,trigger='DI_TURNING_POINT_V3',symbol='SUIUSDT',t=120000):
        db.write_klines([dict(self.rows[0],symbol=symbol,open_time=t,close_time=t+59999)])
        if side is not None:db.write_adcn([dict(symbol=symbol,interval='1m',open_time=t,signal_type=side,trigger=trigger)])

    def test_unviewed_pair_waits_for_decision_and_delivers_exactly_once(self):
        self.arm();self.add()
        alerts.evaluate_once()
        self.assertEqual(alerts.events('admin',0)['events'],[])
        self.add('BUY');alerts.evaluate_once();alerts.evaluate_once()
        events=alerts.events('admin',0)['events']
        self.assertEqual(len(events),1)
        self.assertEqual((events[0]['symbol'],events[0]['field'],events[0]['sound']),('SUIUSDT','decision.buy','chime'))
        self.assertEqual(alerts.events('user',0)['events'],[])
        self.assertEqual(alerts.list_rules('admin'),[])
        # Re-opening the subscription does not reset stored watermarks.
        alerts.signal_preferences('admin');alerts.evaluate_once()
        self.assertEqual(len(alerts.events('admin',0)['events']),1)
        self.add('WAIT',t=180000)
        db.write_adcn([dict(symbol='SUIUSDT',interval='1m',open_time=180000,signal_type=None,decision_state='WAIT')])
        alerts.evaluate_once()
        self.add('SELL',t=240000);alerts.evaluate_once()
        self.assertEqual(alerts.events('admin',0)['events'][-1]['sound'],'bell')

    def test_legacy_decision_cannot_trigger_and_history_is_not_announced(self):
        self.add('BUY',t=60000);self.arm();alerts.evaluate_once()
        self.assertEqual(alerts.events('admin',0)['events'],[])
        self.add('BUY',trigger='OLD_RULE');alerts.evaluate_once()
        self.assertEqual(alerts.events('admin',0)['events'],[])
        self.add('SELL');alerts.evaluate_once()
        self.assertEqual(len(alerts.events('admin',0)['events']),1)

    def test_preferences_persist_and_rearm_skips_paused_history(self):
        self.arm();alerts.signal_preferences('admin',{'buy':'alarm','notify':False,'enabled':False});alerts.evaluate_once()
        self.add('BUY');alerts.evaluate_once()
        self.assertEqual(alerts.events('admin',0)['events'],[])
        with patch.object(alerts.time,'time',return_value=180):
            alerts.signal_preferences('admin',{'enabled':True});alerts.evaluate_once()
        self.assertEqual(alerts.events('admin',0)['events'],[])
        self.add('BUY',t=180000);alerts.evaluate_once()
        event=alerts.events('admin',0)['events'][0]
        self.assertEqual(event['sound'],'alarm');self.assertFalse(event['notify'])
        self.assertEqual(alerts.signal_preferences('admin')['buy'],'alarm')
        with self.assertRaises(ValueError):alerts.signal_preferences('admin',{'buy':'unknown'})

    def test_new_active_pair_is_subscribed_without_replaying_history(self):
        with patch.object(alerts.data_policy,'active_symbols',return_value=['BTCUSDT']):self.arm()
        self.add('BUY')
        with patch.object(alerts.time,'time',return_value=180):alerts.sync_signal_rules()
        alerts.evaluate_once();self.assertEqual(alerts.events('admin',0)['events'],[])
        self.add('SELL',t=180000);alerts.evaluate_once()
        self.assertEqual(alerts.events('admin',0)['events'][0]['field'],'decision.sell')

    def test_shared_signal_evidence_is_projected_once_per_pass(self):
        self.arm()
        with patch.object(alerts.time,'time',return_value=120):
            alerts.signal_preferences('user');alerts.sync_signal_rules()
        self.add('BUY')
        with patch.object(alerts.db,'read_state_page',wraps=alerts.db.read_state_page) as read:
            alerts.evaluate_once();self.assertEqual(read.call_count,1)
        self.assertEqual(len(alerts.events('admin',0)['events']),1)
        self.assertEqual(len(alerts.events('user',0)['events']),1)

    def test_preferences_api_is_account_owned_and_origin_checked(self):
        code,_=alert_routes.handle_get('/api/alerts/signals','',self.server())
        self.assertEqual(code,401)
        code,value=alert_routes.handle_get('/api/alerts/signals','',self.server('admin'))
        self.assertEqual(code,200);self.assertTrue(value['enabled'])
        code,_=alert_routes.handle_post('/api/alerts/signals','{"enabled":false}',self.server('admin','https://other.example'))
        self.assertEqual(code,403)
        self.assertTrue(alerts.signal_preferences('admin')['enabled'])

if __name__=='__main__':unittest.main()
