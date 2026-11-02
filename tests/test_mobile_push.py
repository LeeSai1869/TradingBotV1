"""Small laptop-hosted Web Push: private enrollment, routing, retries and cleanup."""
import base64
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_data_admin as fixtures
from Section_11_UI_UX.server import mobile_push as push,alerts,notification_payload as payload,public_access


def subscription():
    return {'endpoint':'https://fcm.googleapis.com/fcm/send/private-device','keys':{'p256dh':base64.urlsafe_b64encode(b'\x04'+b'x'*64).decode().rstrip('='),'auth':base64.urlsafe_b64encode(b'a'*16).decode().rstrip('=')}}

class MobilePush(unittest.TestCase):
    setUp=fixtures.DataAdminTests.setUp

    def ready(self):
        self.enterContext(patch.object(push,'status',return_value={'ready':True}))
        self.enterContext(patch.object(push,'configuration',return_value={'origin':'https://laptop.tailnet.ts.net','private_key_file':'unused','contact':'mailto:test@example.com'}))
        self.enterContext(patch.object(alerts.auth,'users',return_value={'admin':{}}))

    def event(self):
        event=dict(name='BUY',symbol='BTCUSDT',interval='1m',bar_time=120000,created=int(push.time.time()*1000),field='decision.buy',sound='none',notify=True,message='BUY',details={'side':'BUY','price':100,'confidence':88,'upper':{'low':105,'high':106},'lower':{'low':94,'high':95}})
        conn=alerts.open_db()
        with conn:conn.execute('INSERT INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES (?,?,?,?,?,?)',('admin','signal','0',120000,event['created'],json.dumps(event)))
        conn.close()

    def test_scope_is_independent_of_desktop_and_delivery_is_durable(self):
        self.ready();push.enroll('admin',{'subscription':subscription()})
        alerts.signal_preferences('admin',{'notify':False})
        self.event()
        with patch.object(push,'send') as send:
            push.deliver_once();push.deliver_once();self.assertEqual(send.call_count,1)
            packet=send.call_args.args[1];self.assertIn('Confidence 88/100',packet['body']);self.assertIn('at=120000',packet['data']['url'])
        self.assertEqual(push.devices('user')['devices'],[])
        self.assertIsNotNone(push.devices('admin')['devices'][0]['last_sent'])
        push.remove('user',{'endpoint':subscription()['endpoint']});self.assertEqual(len(push.devices('admin')['devices']),1)
        push.remove('admin',{'endpoint':subscription()['endpoint']});self.assertEqual(push.devices('admin')['devices'],[])

    def test_mobile_scope_mute_skips_without_replay_and_transient_failure_retries(self):
        self.ready();push.enroll('admin',{'subscription':subscription()});alerts.signal_preferences('admin',{'timeframes':{'1m':{'mobile':False}}});self.event()
        with patch.object(push,'send') as send:push.deliver_once();send.assert_not_called()
        alerts.signal_preferences('admin',{'timeframes':{'1m':{'mobile':True}}})
        with patch.object(push,'send') as send:push.deliver_once();send.assert_not_called()
        conn=alerts.open_db()
        with conn:conn.execute('UPDATE push_devices SET cursor=0')
        conn.close()
        with patch.object(push,'send',side_effect=TimeoutError):push.deliver_once()
        self.assertIn('failed',push.devices('admin')['devices'][0]['last_error'])
        conn=alerts.open_db()
        with conn:conn.execute('UPDATE push_devices SET next_try=0')
        conn.close()
        with patch.object(push,'send') as send:push.deliver_once();send.assert_called_once()

    def test_endpoint_and_key_validation_rejects_non_push_destinations(self):
        for endpoint in ('http://127.0.0.1','https://example.com/push','https://fcm.googleapis.com.evil.test/x','https://user@fcm.googleapis.com/x','https://fcm.googleapis.com:8080/x'):
            with self.assertRaises(ValueError):push.validate_subscription({**subscription(),'endpoint':endpoint})
        with self.assertRaises(ValueError):push.validate_subscription({'endpoint':None})
        self.assertEqual(push.validate_subscription(subscription()),subscription())

    def test_explicit_private_https_origin_does_not_accept_other_origins(self):
        with patch.object(push,'configuration',return_value={'origin':'https://laptop.tailnet.ts.net'}):
            server=SimpleNamespace(headers={'Host':'127.0.0.1:8000','Origin':'https://laptop.tailnet.ts.net'})
            self.assertTrue(public_access.same_origin(server,server.headers['Origin']))
            self.assertFalse(public_access.same_origin(server,'https://evil.test'))
            self.assertTrue(public_access.public_request(server))

    def test_missing_setup_is_explicit_and_card_context_must_match_signal(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(push,'CONFIG_FILE',Path(folder)/'missing'):
            self.assertFalse(push.status()['ready'])
            with self.assertRaises(ValueError):push.enroll('admin',{'subscription':subscription()})
        bar={'open_time':120000,'client':{'close':100,'close_time':179999}}
        mismatch={'side':'SELL','open_time':120000,'entry':100,'confidence':{'buy_score':99}}
        self.assertIsNone(payload.details(bar,'BUY',mismatch)['confidence'])
        context={**mismatch,'side':'BUY','confidence':{'buy_score':88},'area_map':{'resistance':[{'low':105,'high':106}],'support':[{'low':94,'high':95}]}}
        rich=payload.details(bar,'BUY',context)
        self.assertEqual((rich['confidence'],rich['upper']['high'],rich['lower']['low']),(88,106,94))

    def test_manual_test_and_expired_endpoint_are_account_owned(self):
        self.ready();push.enroll('admin',{'subscription':subscription()})
        with patch.object(push,'send') as send:
            with self.assertRaises(ValueError):push.send_test('user',{'endpoint':subscription()['endpoint']})
            push.send_test('admin',{'endpoint':subscription()['endpoint']});self.assertEqual(send.call_count,1)
            self.assertEqual(send.call_args.args[1]['title'],'Push connection test')
        self.event();failure=RuntimeError('expired');failure.response=SimpleNamespace(status_code=410)
        with patch.object(push,'send',side_effect=failure):push.deliver_once()
        self.assertEqual(push.devices('admin')['devices'],[])


class RealPushEncryption(unittest.TestCase):
    def test_real_library_encrypts_and_disables_redirects_without_network(self):
        import importlib.util
        if not importlib.util.find_spec('pywebpush'):self.skipTest('Optional requirements-mobile.txt is not installed')
        import requests
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        from configure_mobile import configure
        client=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        sub=subscription();sub['keys']['p256dh']=base64.urlsafe_b64encode(client).decode().rstrip('=')
        with tempfile.TemporaryDirectory() as directory:
            path=configure('https://laptop.tailnet.ts.net','mailto:test@example.com',directory);cfg=json.loads(path.read_text())
            response=requests.Response();response.status_code=201;response._content=b''
            with patch('requests.Session.request',return_value=response) as request:
                push.send(sub,{'title':'Test','body':'Private signal'},cfg)
                self.assertFalse(request.call_args.kwargs['allow_redirects'])
                self.assertEqual(request.call_args.kwargs['timeout'],5)
                self.assertNotIn(b'Private signal',request.call_args.kwargs['data'])
            self.assertEqual(path.stat().st_mode&0o777,0o600)
