import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Section_11_UI_UX.server import delivery_diagnostics as diagnostics,alerts,auth

class DeliveryDiagnostics(unittest.TestCase):
    def setUp(self):
        temp=self.enterContext(tempfile.TemporaryDirectory());self.root=Path(temp)
        self.enterContext(patch.object(auth,'USERS_FILE',self.root/'users.json'))
        self.enterContext(patch.object(diagnostics.android_push,'status',return_value=dict(ready=False,reason='not configured')))
        self.enterContext(patch.object(diagnostics.mobile_push,'status',return_value=dict(ready=False,reason='not configured')))
        self.enterContext(patch.object(diagnostics.public_access,'configured_origin',return_value=None))

    def test_missing_store_is_not_created(self):
        self.assertEqual(diagnostics.report()['store'],'MISSING')
        self.assertEqual(list(self.root.iterdir()),[])

    def test_settings_and_device_failure_counts_exclude_private_payloads(self):
        conn=alerts.open_db()
        with conn:
            conn.execute('INSERT INTO signal_preferences VALUES (?,?)',('test',json.dumps(dict(enabled=True,mobile=False,coins={'BTCUSDT':dict(mobile=False)}))))
            conn.execute('INSERT INTO android_devices(id,owner,token,cursor,enabled,failures,touched) VALUES (?,?,?,?,?,?,?)',('private-id','test','private-token',0,1,2,0))
            conn.execute('INSERT INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES (?,?,?,?,?,?)',('test','rule','0',100,200,'private-event'))
        conn.close();result=diagnostics.report();text=json.dumps(result)
        self.assertEqual(result['devices']['android'],dict(registered=1,enabled=1,retrying=1))
        self.assertFalse(result['accounts'][0]['mobile']);self.assertEqual(result['accounts'][0]['muted_mobile_coins'],1)
        self.assertEqual(result['last_event_created_ms'],200)
        self.assertNotIn('private-',text)
        conn=alerts.open_db()
        try:self.assertEqual(conn.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
        finally:conn.close()
