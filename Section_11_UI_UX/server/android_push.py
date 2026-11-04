"""Optional FCM transport for the small native Android inbox. No market writes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlparse

from Section_1_Global_Core.paths import data_path
CONFIG_FILE=data_path('accounts/android_push.json',Path.home()/'.tradingbot'/'android_push.json')


def configuration():
    if not CONFIG_FILE.exists():return {}
    value=json.loads(CONFIG_FILE.read_text())
    if not isinstance(value,dict):raise ValueError('Invalid Android configuration')
    origin=value.get('origin');parsed=urlparse(origin or '')
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:raise ValueError('Android push requires a valid HTTPS origin')
    return value


def status():
    try:
        cfg=configuration();required=('project_id','app_id','api_key','sender_id','package_name','service_account_file')
        ready=bool(cfg and all(cfg.get(k) for k in required) and Path(cfg['service_account_file']).is_file() and importlib.util.find_spec('google.auth'))
        return {'ready':ready,'reason':'' if ready else 'Firebase Android push is not configured','origin':cfg.get('origin')}
    except (ValueError,OSError,ImportError):return {'ready':False,'reason':'Firebase Android push needs setup','origin':None}


def client_config():
    result=status()
    if result['ready']:
        cfg=configuration();result.update({key:cfg[key] for key in ('project_id','app_id','api_key','sender_id','package_name')})
    return result


def register(owner,data):
    from . import alerts
    if not status()['ready']:raise ValueError('Configure Firebase on the laptop first')
    token=data.get('token');cfg=configuration()
    if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_.:\-]{30,4096}',token):raise ValueError('Invalid Android registration token')
    if data.get('package_name')!=cfg['package_name']:raise ValueError('This Android package does not match the laptop configuration')
    for key in ('enabled','sound'):
        if type(data.get(key,True)) is not bool:raise ValueError('Invalid device switch')
    key=hashlib.sha256(token.encode()).hexdigest();conn=alerts.open_db()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            old=conn.execute('SELECT owner,cursor FROM android_devices WHERE id=?',(key,)).fetchone()
            if conn.execute('SELECT COUNT(*) FROM android_devices WHERE owner=?',(owner,)).fetchone()[0]>=5 and (not old or old['owner']!=owner):raise ValueError('Maximum five Android devices per account')
            cursor=old['cursor'] if old and old['owner']==owner else conn.execute('SELECT COALESCE(MAX(seq),0) FROM events WHERE owner=?',(owner,)).fetchone()[0]
            conn.execute('INSERT OR REPLACE INTO android_devices(id,owner,token,cursor,enabled,sound,touched) VALUES (?,?,?,?,?,?,?)',(key,owner,token,cursor,data.get('enabled',True),data.get('sound',True),time.time()))
        alerts.signal_preferences(owner,{'mobile':True})
        return {'ok':True}
    finally:conn.close()


def remove(owner,data):
    from . import alerts
    token=data.get('token')
    if not isinstance(token,str):raise ValueError('Device token required')
    conn=alerts.open_db()
    try:
        with conn:conn.execute('DELETE FROM android_devices WHERE id=? AND owner=?',(hashlib.sha256(token.encode()).hexdigest(),owner))
        return {'ok':True}
    finally:conn.close()


def send(token,event,owner,sound,cfg):
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    credentials=service_account.Credentials.from_service_account_file(cfg['service_account_file'],scopes=['https://www.googleapis.com/auth/firebase.messaging'])
    compact={key:event.get(key) for key in ('seq','name','symbol','interval','bar_time','created','details','message')}
    payload={'message':{'token':token,'data':{'event':json.dumps(compact,separators=(',',':')),'owner':owner,'origin':cfg['origin'],'sound':'true' if sound else 'false'},'android':{'priority':'HIGH','ttl':'300s'}}}
    with AuthorizedSession(credentials) as session:
        response=session.post(f"https://fcm.googleapis.com/v1/projects/{cfg['project_id']}/messages:send",json=payload,timeout=5,allow_redirects=False)
        if response.status_code>=300:
            error=RuntimeError('FCM rejected notification');error.response=response;raise error


def deliver_once():
    from . import alerts,auth
    if not status()['ready']:return
    cfg=configuration();conn=alerts.open_db()
    try:devices=conn.execute('SELECT * FROM android_devices WHERE next_try<=? ORDER BY touched LIMIT 20',(time.time(),)).fetchall()
    finally:conn.close()
    budget=10
    for device in devices:
        if budget<=0:break
        if device['owner'] not in auth.users():continue
        cursor=device['cursor'];failures=0;retry=0;message='';gone=False
        for event in alerts.events(device['owner'],cursor)['events'][:20]:
            if not device['enabled'] or not event.get('mobile') or time.time()*1000-event['created']>300000:cursor=event['seq'];continue
            if budget<=0:break
            budget-=1
            try:
                check=alerts.open_db()
                try:current=check.execute('SELECT 1 FROM android_devices WHERE id=? AND owner=? AND token=? AND cursor=? AND enabled=1',(device['id'],device['owner'],device['token'],device['cursor'])).fetchone()
                finally:check.close()
                if not current:break
                send(device['token'],event,device['owner'],bool(device['sound']),cfg);cursor=event['seq']
            except Exception as error:
                response=getattr(error,'response',None);code=getattr(response,'status_code',None)
                if code in (404,410):gone=True;break
                failures=device['failures']+1;message=f'Android delivery failed ({code or type(error).__name__})'
                if failures>=5:cursor=event['seq'];failures=0
                retry=time.time()+min(300,2**min(failures+1,8));break
        conn=alerts.open_db()
        try:
            with conn:
                if gone:conn.execute('DELETE FROM android_devices WHERE id=? AND owner=? AND token=?',(device['id'],device['owner'],device['token']))
                else:conn.execute('UPDATE android_devices SET cursor=?,failures=?,next_try=?,last_error=?,touched=? WHERE id=? AND owner=? AND cursor=?',(cursor,failures,retry,message,time.time(),device['id'],device['owner'],device['cursor']))
        finally:conn.close()


def start():
    stop=threading.Event()
    def run():
        while not stop.is_set():
            try:deliver_once()
            except Exception as error:print(f'[Android push] {type(error).__name__}',flush=True)
            stop.wait(2)
    threading.Thread(target=run,name='android-push',daemon=True).start();return stop
