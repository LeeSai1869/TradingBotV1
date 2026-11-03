"""Native inbox history isolation, device switches and optional Firebase setup."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import test_data_admin as fixtures
from Section_11_UI_UX.server import alerts,android_push as push
from configure_android import configure

class AndroidInbox(unittest.TestCase):
    setUp=fixtures.DataAdminTests.setUp

    def insert(self,owner='admin',count=1):
        conn=alerts.open_db()
        with conn:
            for i in range(count):
                packet=dict(name='BUY',symbol='BTCUSDT',interval='1m',field='decision.buy',created=int(push.time.time()*1000),bar_time=i,mobile=True)
                conn.execute('INSERT INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES (?,?,?,?,?,?)',(owner,owner+str(i),'0',i,packet['created'],json.dumps(packet)))
        conn.close()

    def ready(self):
        self.enterContext(patch.object(push,'status',return_value={'ready':True}))
        self.enterContext(patch.object(push,'configuration',return_value={'origin':'https://laptop.example','package_name':'com.tradingindicator.alerts'}))
        self.enterContext(patch.object(alerts.auth,'users',return_value={'admin':{},'user':{}}))

    def test_history_pages_are_complete_private_and_do_not_replay(self):
        self.insert(count=123);self.insert('user',3)
        seen=[];before=None
        while True:
            page=alerts.events('admin',None,history_before=before,history_limit=50)
            seen.extend(row['seq'] for row in page['history'])
            if not page['has_more']:break
            before=page['next_before']
        self.assertEqual(len(seen),123);self.assertEqual(len(set(seen)),123)
        self.assertEqual(alerts.events('admin',page['cursor'])['events'],[])
        self.assertEqual(len(alerts.events('user',None)['history']),3)

    def test_device_updates_keep_cursor_and_muted_events_do_not_replay(self):
        self.ready();data=dict(token='a'*40,package_name='com.tradingindicator.alerts',enabled=False,sound=False)
        push.register('admin',data);self.insert()
        with patch.object(push,'send') as send:push.deliver_once();send.assert_not_called()
        push.register('admin',dict(data,enabled=True))
        with patch.object(push,'send') as send:push.deliver_once();send.assert_not_called()
        conn=alerts.open_db()
        with conn:conn.execute('UPDATE android_devices SET cursor=0')
        conn.close()
        with patch.object(push,'send') as send:
            push.deliver_once();push.deliver_once();send.assert_called_once();self.assertFalse(send.call_args.args[3])
        push.remove('user',data)
        conn=alerts.open_db();self.assertEqual(conn.execute('SELECT COUNT(*) FROM android_devices').fetchone()[0],1);conn.close()
        push.remove('admin',data)

    def test_configuration_rejects_project_mismatch_and_protects_secret(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);google=root/'google.json';secret=root/'secret.json'
            google.write_text(json.dumps({'project_info':{'project_id':'example','project_number':'123'},'client':[{'client_info':{'android_client_info':{'package_name':'com.tradingindicator.alerts'},'mobilesdk_app_id':'1:123:android:abc'},'api_key':[{'current_key':'public'}]}]}))
            service=dict(type='service_account',project_id='other',private_key='SECRET',client_email='sender@example.com');secret.write_text(json.dumps(service))
            with self.assertRaises(ValueError):configure('https://laptop.example',google,secret,'com.tradingindicator.alerts',root/'config')
            service['project_id']='example';secret.write_text(json.dumps(service))
            config=configure('https://laptop.example',google,secret,'com.tradingindicator.alerts',root/'config')
            self.assertEqual(config.stat().st_mode&0o777,0o600)
            with patch.object(push,'CONFIG_FILE',config),patch.object(push,'status',return_value={'ready':True}):
                public=push.client_config();self.assertNotIn('service_account_file',public);self.assertNotIn('SECRET',json.dumps(public))
