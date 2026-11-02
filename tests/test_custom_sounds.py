"""Account-owned audio library and notification-only delivery scopes."""
import base64
import io
import json
import unittest
import wave
import test_data_admin as fixtures
from Section_11_UI_UX.server import alerts,alert_routes


def wav():
    stream=io.BytesIO()
    with wave.open(stream,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\0\0'*800)
    return base64.b64encode(stream.getvalue()).decode()

class CustomSounds(unittest.TestCase):
    setUp=fixtures.DataAdminTests.setUp
    server=fixtures.DataAdminTests.server

    def test_upload_assignment_isolation_and_delete_mutes_references_without_rearming(self):
        key=alerts.upload_sound('admin',{'name':'My bell','data':wav()})['id']
        self.assertEqual(alerts.sounds('admin')['sounds'][0]['name'],'My bell')
        self.assertEqual(alerts.sounds('user')['sounds'],[])
        self.assertTrue(alerts.valid_sound('admin',key));self.assertFalse(alerts.valid_sound('user',key))
        with self.assertRaises(ValueError):alerts.sounds('user',key)
        alerts.signal_preferences('admin',{'buy':key})
        spec=dict(name='Mine',symbol='BTCUSDT',interval='1m',field='client.close',operator='above',value=10,target_field=None,repeat='per_bar',sound=key,notify=True,enabled=True,mode='closed')
        rule=alerts.save('admin',spec)
        with self.assertRaises(ValueError):alerts.save('user',spec)
        conn=alerts.open_db();before=conn.execute('SELECT cursor,created FROM rules WHERE id=?',(rule,)).fetchone();conn.close()
        alerts.delete_sound('admin',key)
        self.assertEqual(alerts.signal_preferences('admin')['buy'],'none')
        self.assertEqual(alerts.list_rules('admin')[0]['sound'],'none')
        conn=alerts.open_db();after=conn.execute('SELECT cursor,created FROM rules WHERE id=?',(rule,)).fetchone();conn.close()
        self.assertEqual(tuple(before),tuple(after))
        with self.assertRaises(ValueError):alerts.sounds('admin',key)

    def test_validation_and_account_limit(self):
        for payload in ({'name':'','data':wav()},{'name':'bad','data':'not base64'},{'name':'bad','data':base64.b64encode(b'not audio').decode()},{'name':'big','data':'a'*(4*((alerts.MAX_SOUND_BYTES+2)//3)+1)}):
            with self.assertRaises(ValueError):alerts.upload_sound('admin',payload)
        for i in range(10):alerts.upload_sound('admin',{'name':str(i),'data':wav()})
        with self.assertRaises(ValueError):alerts.upload_sound('admin',{'name':'11','data':wav()})

    def test_upload_api_requires_login_same_origin_and_private_read(self):
        self.assertEqual(alert_routes.handle_post('/api/alerts/sounds',json.dumps({'name':'x','data':wav()}),self.server())[0],401)
        self.assertEqual(alert_routes.handle_post('/api/alerts/sounds',json.dumps({'name':'x','data':wav()}),self.server('admin','https://elsewhere.test'))[0],403)
        key=alerts.upload_sound('admin',{'name':'Mine','data':wav()})['id']
        self.assertEqual(alert_routes.handle_get('/api/alerts/sounds','id='+key,self.server('user'))[0],404)

    def test_coin_and_timeframe_switches_only_gate_desktop_delivery(self):
        conn=alerts.open_db()
        with conn:
            for i,(symbol,iv) in enumerate([('BTCUSDT','5m'),('SUIUSDT','5m'),('BTCUSDT','1m'),('SUIUSDT','1m')]):
                event=dict(name='BUY',message='BUY',symbol=symbol,interval=iv,field='decision.buy',sound='chime',notify=True,created=1,bar_time=i)
                conn.execute('INSERT INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES (?,?,?,?,?,?)',('admin',str(i),'0',i,1,json.dumps(event)))
        conn.close()
        alerts.signal_preferences('admin',{'timeframes':{'5m':{'desktop':False}},'coins':{'BTCUSDT':{'desktop':False}}})
        rows=alerts.events('admin',0)['events']
        self.assertEqual([r['notify'] for r in rows],[False,False,False,True])
        self.assertEqual([r['app'] for r in rows],[False,False,False,True]);self.assertTrue(all(r['sound']=='chime' for r in rows))
        prefs=alerts.signal_preferences('admin',{'coins':{'SUIUSDT':{'desktop':True}}})
        self.assertFalse(prefs['coins']['BTCUSDT']['desktop'])
        with self.assertRaisesRegex(ValueError,'Mobile'):alerts.signal_preferences('admin',{'timeframes':{'5m':{'mobile':True}}})
        with self.assertRaises(ValueError):alerts.signal_preferences('admin',{'coins':{'UNKNOWN':{'desktop':True}}})
        with self.assertRaises(ValueError):alerts.signal_preferences('admin',{'timeframes':{'5m':{'sound':False}}})

if __name__=='__main__':unittest.main()
