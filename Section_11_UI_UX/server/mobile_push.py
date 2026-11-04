"""Opt-in Web Push. Dedicated worker; no market writes or browser polling dependency."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlparse

from Section_1_Global_Core.paths import data_path
CONFIG_FILE=data_path('accounts/mobile_push.json',Path.home()/'.tradingbot'/'mobile_push.json')
PROVIDERS=('fcm.googleapis.com','push.services.mozilla.com','web.push.apple.com','notify.windows.com')
MAX_AGE_SECONDS=300


def configuration():
    if not CONFIG_FILE.exists():return {}
    value=json.loads(CONFIG_FILE.read_text())
    if not isinstance(value,dict):raise ValueError('Invalid mobile configuration')
    origin=value.get('origin','')
    if not isinstance(origin,str):raise ValueError('Invalid mobile origin')
    parsed=urlparse(origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:raise ValueError('Configure a valid HTTPS mobile origin')
    return value


def status():
    try:
        cfg=configuration()
        if not cfg:return {'ready':False,'reason':'HTTPS address and push keys have not been configured','public_key':None,'origin':None}
        ready=bool(cfg.get('public_key') and Path(cfg.get('private_key_file','')).is_file() and cfg.get('contact') and importlib.util.find_spec('pywebpush'))
        return {'ready':ready,'reason':'' if ready else 'Install requirements-mobile.txt and configure push keys','public_key':cfg.get('public_key') if ready else None,'origin':cfg.get('origin')}
    except (ValueError,OSError):return {'ready':False,'reason':'Mobile push configuration needs attention','public_key':None,'origin':None}


def validate_subscription(value):
    if not isinstance(value,dict):raise ValueError('Push subscription required')
    endpoint=value.get('endpoint','')
    if not isinstance(endpoint,str):raise ValueError('Invalid push endpoint')
    parsed=urlparse(endpoint)
    host=parsed.hostname or ''
    if not isinstance(endpoint,str) or len(endpoint)>2048 or parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.fragment or not any(host==domain or host.endswith('.'+domain) for domain in PROVIDERS):raise ValueError('Unsupported browser push endpoint')
    keys=value.get('keys',{})
    if not isinstance(keys,dict):raise ValueError('Invalid push keys')
    for name,size in (('p256dh',65),('auth',16)):
        key=keys.get(name)
        if not isinstance(key,str) or len(key)>128:raise ValueError('Invalid push key')
        try:decoded=base64.b64decode(key+'='*((-len(key))%4),altchars=b'-_',validate=True)
        except ValueError:raise ValueError('Invalid push key') from None
        if len(decoded)!=size or name=='p256dh' and decoded[0]!=4:raise ValueError('Invalid push key')
    return {'endpoint':endpoint,'keys':{key:keys[key] for key in ('p256dh','auth')}}


def enroll(owner,data):
    from . import alerts
    if not status()['ready']:raise ValueError('Configure HTTPS and Web Push before enabling mobile notifications')
    subscription=validate_subscription(data.get('subscription'))
    key=hashlib.sha256(subscription['endpoint'].encode()).hexdigest()
    conn=alerts.open_db()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            old=conn.execute('SELECT owner FROM push_devices WHERE id=?',(key,)).fetchone()
            latest=conn.execute('SELECT COALESCE(MAX(seq),0) FROM events WHERE owner=?',(owner,)).fetchone()[0]
            if conn.execute('SELECT COUNT(*) FROM push_devices WHERE owner=?',(owner,)).fetchone()[0]>=5 and (not old or old['owner']!=owner):raise ValueError('Maximum five push devices per account')
            conn.execute('INSERT OR REPLACE INTO push_devices(id,owner,subscription,cursor,failures,next_try,last_error,last_sent,touched) VALUES (?,?,?,?,0,0,\'\',NULL,?)',(key,owner,json.dumps(subscription),latest,time.time()))
        alerts.signal_preferences(owner,{'mobile':True})
        return {'ok':True,'device':key}
    finally:conn.close()


def remove(owner,data):
    from . import alerts
    endpoint=data.get('endpoint')
    if not isinstance(endpoint,str):raise ValueError('Device endpoint required')
    key=hashlib.sha256(endpoint.encode()).hexdigest();conn=alerts.open_db()
    try:
        with conn:conn.execute('DELETE FROM push_devices WHERE id=? AND owner=?',(key,owner))
        return {'ok':True}
    finally:conn.close()


def devices(owner):
    from . import alerts
    conn=alerts.open_db()
    try:return {'devices':[dict(row) for row in conn.execute('SELECT id,last_sent,last_error FROM push_devices WHERE owner=?',(owner,))]}
    finally:conn.close()


def send(subscription,payload,cfg):
    from pywebpush import webpush
    import requests
    # Subscription URLs cannot redirect outside the browser push provider allowlist.
    class NoRedirectSession(requests.Session):
        def request(self,*args,**kwargs):
            kwargs['allow_redirects']=False
            return super().request(*args,**kwargs)
    with NoRedirectSession() as session:
        response=webpush(subscription_info=subscription,data=json.dumps(payload,separators=(',',':')),vapid_private_key=cfg['private_key_file'],
            vapid_claims={'sub':cfg['contact']},ttl=MAX_AGE_SECONDS,timeout=5,requests_session=session)
        if response is not None and response.status_code>=300:raise ValueError('Push provider rejected delivery')


def deliver_once():
    from . import alerts,auth,notification_payload
    if not status()['ready']:return
    cfg=configuration();conn=alerts.open_db()
    try:rows=conn.execute('SELECT * FROM push_devices WHERE next_try<=? ORDER BY touched LIMIT 20',(time.time(),)).fetchall()
    finally:conn.close()
    budget=10
    for device in rows:
        if budget<=0:break
        if device['owner'] not in auth.users():continue
        packet=alerts.events(device['owner'],device['cursor']);cursor=device['cursor'];error='';failures=0;next_try=0;sent=device['last_sent'];gone=False
        for event in packet['events'][:20]:
            if not device['enabled'] or not event.get('mobile') or time.time()*1000-event['created']>MAX_AGE_SECONDS*1000:
                cursor=event['seq'];continue
            if budget<=0:break
            budget-=1
            try:
                check=alerts.open_db()
                try:current=check.execute('SELECT 1 FROM push_devices WHERE id=? AND owner=? AND subscription=? AND cursor=?',(device['id'],device['owner'],device['subscription'],device['cursor'])).fetchone()
                finally:check.close()
                if not current:break
                payload=notification_payload.push_payload(event);payload['data'].update(account=device['owner'],server=cfg['origin']);payload['silent']=not bool(device['sound'])
                send(json.loads(device['subscription']),payload,cfg)
                cursor=event['seq'];sent=int(time.time()*1000)
            except Exception as failure:
                response=getattr(failure,'response',None);code=getattr(response,'status_code',None)
                if code in (404,410):gone=True;break
                failures=device['failures']+1;error=f'Push delivery failed ({code or type(failure).__name__})'
                if failures>=5:cursor=event['seq'];failures=0
                next_try=time.time()+min(300,2**min(failures+1,8));break
        conn=alerts.open_db()
        try:
            with conn:
                if gone:conn.execute('DELETE FROM push_devices WHERE id=? AND owner=? AND subscription=?',(device['id'],device['owner'],device['subscription']))
                else:conn.execute('UPDATE push_devices SET cursor=?,failures=?,next_try=?,last_error=?,last_sent=?,touched=? WHERE id=? AND owner=? AND subscription=? AND cursor=?',
                    (cursor,failures,next_try,error,sent,time.time(),device['id'],device['owner'],device['subscription'],device['cursor']))
        finally:conn.close()


def start():
    stop=threading.Event()
    def work():
        while not stop.is_set():
            try:deliver_once()
            except Exception as error:print(f'[mobile push] {type(error).__name__}',flush=True)
            stop.wait(2)
    threading.Thread(target=work,name='mobile-push',daemon=True).start()
    return stop


def send_test(owner,data):
    from . import alerts
    if not status()['ready']:raise ValueError('Mobile push is not configured')
    endpoint=data.get('endpoint')
    if not isinstance(endpoint,str):raise ValueError('Connect this device first')
    key=hashlib.sha256(endpoint.encode()).hexdigest();conn=alerts.open_db()
    try:row=conn.execute('SELECT subscription FROM push_devices WHERE id=? AND owner=?',(key,owner)).fetchone()
    finally:conn.close()
    if not row:raise ValueError('Connect this device first')
    send(json.loads(row['subscription']),dict(title='Push connection test',body='This device can receive alerts from your laptop.',tag='mobile-test',timestamp=int(time.time()*1000),data={'url':'/web_root/mobile.html'}),configuration())
    return {'ok':True}



def preferences(owner,data):
    from . import alerts
    endpoint=data.get('endpoint')
    if not isinstance(endpoint,str) or any(type(data.get(key)) is not bool for key in ('enabled','sound')):raise ValueError('Device switches required')
    key=hashlib.sha256(endpoint.encode()).hexdigest();conn=alerts.open_db()
    try:
        with conn:conn.execute('UPDATE push_devices SET enabled=?,sound=? WHERE id=? AND owner=?',(data['enabled'],data['sound'],key,owner))
        return {'ok':True}
    finally:conn.close()
