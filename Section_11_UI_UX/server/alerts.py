"""Per-account stored-candle alerts. No exchange requests and no chart dependency."""
import json
import math
import os
import sqlite3
import threading
import time
import uuid
from . import auth, live_candle
from Section_1_Global_Core import data_policy, data_admin
from Section_1_Global_Core.memory_storage.Storage import db, features_store
from Section_1_Global_Core.memory_storage.market_data.update_klines import INTERVAL_MS

FIELDS = {f'client.{key}': f'Candle {key}' for key in ('high','low','close')}
FIELDS.update({f'features.{key}': key.replace('_',' ').upper() for key in features_store.COLUMNS if key not in {'symbol','interval','open_time'}})
FIELDS.update({'features.di_plus':'+DI','features.di_minus':'−DI','features.di_direction':'DI direction (signed)','features.di_spread':'DI spread'})
OPERATORS = {'above','at_or_above','below','at_or_below','equals','crosses_above','crosses_below'}
SOUNDS = {'chime','bell','alarm','none'}


def open_db():
    path = auth.USERS_FILE.with_name('alerts.sqlite3')
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd=os.open(path,os.O_CREAT | os.O_RDWR,0o600);os.close(fd)
    conn=sqlite3.connect(path,timeout=5)
    conn.row_factory=sqlite3.Row
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS rules(id TEXT PRIMARY KEY,owner TEXT NOT NULL,spec TEXT NOT NULL,
            cursor INTEGER NOT NULL,epoch TEXT NOT NULL,created INTEGER NOT NULL,revision TEXT NOT NULL,status TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS rules_owner ON rules(owner);
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,owner TEXT NOT NULL,rule_id TEXT NOT NULL,
            epoch TEXT NOT NULL,bar_time INTEGER NOT NULL,created INTEGER NOT NULL,packet TEXT NOT NULL,
            UNIQUE(rule_id,epoch,bar_time));
        CREATE TABLE IF NOT EXISTS live_state(rule_id TEXT PRIMARY KEY,value REAL,target REAL,revision TEXT);
        CREATE INDEX IF NOT EXISTS events_owner ON events(owner,seq);
    ''')
    return conn


def epoch(symbol, interval):
    state=data_policy.read()['epochs']
    return f"{state.get(f'symbol:{symbol}',0)}:{state.get(f'interval:{interval}',0)}"


def validate(data):
    known={r['symbol'] for key in ('approved','disapproved','staged','pending','top50') for r in data_admin.catalog().get(key,[])}
    if data.get('symbol') not in known or data.get('interval') not in data_policy.INTERVALS:
        raise ValueError('Choose a registered coin and supported timeframe')
    if data.get('field') not in FIELDS or data.get('operator') not in OPERATORS:
        raise ValueError('Choose a supported field and condition')
    mode=data.get('mode','closed')
    if mode not in {'live','closed'}: raise ValueError('Choose live price or closed-candle evaluation')
    target_field=data.get('target_field') or None
    if target_field is not None and target_field not in FIELDS:
        raise ValueError('Unsupported comparison field')
    if mode=='live' and any(field and not field.startswith('client.') for field in (data['field'],target_field)):
        raise ValueError('Live rules support candle high, low and close. Features require closed candles.')
    value=data.get('value',0)
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('Threshold must be a finite number')
    if data.get('sound') not in SOUNDS or data.get('repeat') not in {'once','per_bar'}:
        raise ValueError('Unsupported sound or repeat mode')
    name=data.get('name','')
    if not isinstance(name,str) or not 1 <= len(name.strip()) <= 120:
        raise ValueError('Name must contain 1..120 characters')
    for key in ('enabled','notify'):
        if not isinstance(data.get(key),bool): raise ValueError(f'{key} must be true or false')
    return {key:data[key] for key in ('symbol','interval','field','operator','sound','repeat','enabled','notify')} | {'name':name.strip(),'target_field':target_field,'value':value,'mode':mode}


def list_rules(owner):
    conn=open_db()
    try:
        return [json.loads(r['spec']) | {'id':r['id'],'status':r['status']} for r in conn.execute('SELECT * FROM rules WHERE owner=? ORDER BY created DESC',(owner,))]
    finally: conn.close()


def save(owner,data):
    spec=validate(data); key=data.get('id') or uuid.uuid4().hex
    if not isinstance(key,str): raise ValueError('Invalid rule ID')
    with data_policy.locked():
        last=db.last_kline_time(spec['symbol'],spec['interval']) or 0
        version=epoch(spec['symbol'],spec['interval'])
    conn=open_db()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            old=conn.execute('SELECT owner FROM rules WHERE id=?',(key,)).fetchone()
            if old and old['owner']!=owner: raise ValueError('Unknown alert')
            if not old and conn.execute('SELECT COUNT(*) FROM rules WHERE owner=?',(owner,)).fetchone()[0]>=50:
                raise ValueError('Maximum 50 alert rules per account')
            conn.execute('DELETE FROM live_state WHERE rule_id=?',(key,))
            conn.execute('INSERT OR REPLACE INTO rules VALUES (?,?,?,?,?,?,?,?)',(key,owner,json.dumps(spec),last,version,int(time.time()*1000),uuid.uuid4().hex,('Armed for live price' if spec['mode']=='live' else 'Armed for new closed candles') if spec['enabled'] else 'Paused'))
        return key
    finally: conn.close()


def delete(owner,key):
    conn=open_db()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT 1 FROM rules WHERE owner=? AND id=?',(owner,key)).fetchone():
                conn.execute('DELETE FROM live_state WHERE rule_id=?',(key,))
                conn.execute('DELETE FROM rules WHERE owner=? AND id=?',(owner,key))
    finally: conn.close()


def events(owner,after):
    conn=open_db()
    try:
        latest=conn.execute('SELECT COALESCE(MAX(seq),0) FROM events WHERE owner=?',(owner,)).fetchone()[0]
        if after is None:
            history=conn.execute('SELECT seq,packet FROM events WHERE owner=? ORDER BY seq DESC LIMIT 20',(owner,)).fetchall()
            return {'events':[],'cursor':latest,'history':[json.loads(r['packet']) | {'seq':r['seq']} for r in reversed(history)]}
        rows=conn.execute('SELECT seq,packet FROM events WHERE owner=? AND seq>? ORDER BY seq LIMIT 100',(owner,after)).fetchall()
        return {'events':[json.loads(r['packet']) | {'seq':r['seq']} for r in rows],'cursor':rows[-1]['seq'] if rows else max(after,latest)}
    finally: conn.close()


def number(bar,field):
    if not bar: return None
    group,key=field.split('.',1); packet=bar.get(group)
    value=packet.get(key) if packet else None
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) else None


def matches(operator,value,target,previous=None,previous_target=None):
    if value is None or target is None: return False
    if operator=='above': return value>target
    if operator=='at_or_above': return value>=target
    if operator=='below': return value<target
    if operator=='at_or_below': return value<=target
    if operator=='equals': return value==target
    if previous is None or previous_target is None: return False
    if operator=='crosses_above': return previous<=previous_target and value>target
    if operator=='crosses_below': return previous>=previous_target and value<target
    return False


def evaluate_live(rule,spec):
    symbol,iv=spec['symbol'],spec['interval']
    snapshot=live_candle.get_snapshot(symbol,iv) if data_policy.enabled(symbol,iv) else {'bar':None,'status':'inactive'}
    bar=snapshot.get('bar')
    with data_policy.locked():
        if not data_policy.enabled(symbol,iv): bar=None
        version=epoch(symbol,iv)
        conn=open_db()
        try:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                current=conn.execute('SELECT revision FROM rules WHERE id=?',(rule['id'],)).fetchone()
                if not current or current['revision']!=rule['revision']: return
                status='Waiting for live feed' if snapshot.get('status')!='inactive' else 'Suspended: coin or timeframe inactive'
                if snapshot.get('error'): status=f'Live feed unavailable: {snapshot["error"]}'
                if bar is None and snapshot.get('status')=='inactive': conn.execute('DELETE FROM live_state WHERE rule_id=?',(rule['id'],))
                if bar is not None:
                    value=number(bar,spec['field'])
                    target=number(bar,spec['target_field']) if spec['target_field'] else spec['value']
                    previous=conn.execute('SELECT * FROM live_state WHERE rule_id=?',(rule['id'],)).fetchone()
                    if previous and (previous['revision']!=rule['revision'] or version!=rule['epoch']): previous=None
                    fired=matches(spec['operator'],value,target,previous['value'] if previous else None,previous['target'] if previous else None)
                    conn.execute('INSERT OR REPLACE INTO live_state VALUES (?,?,?,?)',(rule['id'],value,target,rule['revision']))
                    status='Watching live price'
                    if fired:
                        message=f"{spec['name']}: {symbol} {iv} live — {FIELDS[spec['field']]} {spec['operator'].replace('_',' ')} {target:g} (value {value:g})"
                        event={'name':spec['name'],'message':message,'symbol':symbol,'interval':iv,'field':spec['field'],'value':value,'target':target,'bar_time':bar['open_time'],'sound':spec['sound'],'notify':spec['notify'],'created':int(time.time()*1000),'mode':'live'}
                        inserted=conn.execute('INSERT OR IGNORE INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES(?,?,?,?,?,?)',(rule['owner'],rule['id'],version,bar['open_time'],event['created'],json.dumps(event))).rowcount
                        status='Triggered' if inserted else 'Already triggered on this candle'
                        if inserted and spec['repeat']=='once': spec['enabled']=False
                conn.execute('UPDATE rules SET spec=?,epoch=?,status=? WHERE id=?',(json.dumps(spec),version,status,rule['id']))
        finally: conn.close()


def evaluate_rule(rule):
    spec=json.loads(rule['spec'])
    if not spec['enabled']: return
    if spec.get('mode')=='live':
        evaluate_live(rule,spec); return
    symbol,iv=spec['symbol'],spec['interval']
    cursor=rule['cursor']; created=rule['created']; updates=[]; status='Waiting for next closed candle'
    with data_policy.locked():
        version=epoch(symbol,iv)
        if version!=rule['epoch']:
            cursor=0;created=int(time.time()*1000)
        if not data_policy.enabled(symbol,iv):
            status='Suspended: coin or timeframe inactive'
        else:
            if rule['status'].startswith('Suspended'):
                created=int(time.time()*1000)
            # Skip pre-creation history without scanning years of a new coin's backfill.
            start=max(cursor,created-2*INTERVAL_MS[iv])
            bars=db.read_state_after(symbol,iv,start,200)
            previous=None
            if bars:
                prior=db.read_state_page(symbol,iv,1,before=bars[0]['open_time'])['bars']
                previous=prior[-1] if prior else None
            for bar in bars:
                if bar['client']['close_time']<created:
                    cursor=bar['open_time']; previous=bar; continue
                needed=[spec['field'],spec['target_field']]
                if any(field and field.startswith('features.') for field in needed) and bar['features'] is None:
                    status='Waiting for stored features'; break
                if spec['operator'].startswith('crosses_') and previous and previous['features'] is None and any(field and field.startswith('features.') for field in needed):
                    status='Waiting for preceding stored features'; break
                value=number(bar,spec['field'])
                target=number(bar,spec['target_field']) if spec['target_field'] else spec['value']
                pvalue=number(previous,spec['field'])
                ptarget=number(previous,spec['target_field']) if spec['target_field'] else spec['value']
                fired=matches(spec['operator'],value,target,pvalue,ptarget)
                cursor=bar['open_time']; previous=bar
                status='Watching new closed candles' if value is not None and target is not None else 'Field has no numeric value on last candle'
                if fired:
                    message=f"{spec['name']}: {symbol} {iv} — {FIELDS[spec['field']]} {spec['operator'].replace('_',' ')} {target:g} (value {value:g})"
                    updates.append({'name':spec['name'],'message':message,'symbol':symbol,'interval':iv,'field':spec['field'],'value':value,'target':target,'bar_time':bar['open_time'],'sound':spec['sound'],'notify':spec['notify'],'created':int(time.time()*1000),'mode':'closed'})
                    status='Triggered'
                    if spec['repeat']=='once': spec['enabled']=False; break
        conn=open_db()
        try:
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                current=conn.execute('SELECT revision FROM rules WHERE id=?',(rule['id'],)).fetchone()
                if not current or current['revision']!=rule['revision']: return
                for event in updates:
                    conn.execute('INSERT OR IGNORE INTO events(owner,rule_id,epoch,bar_time,created,packet) VALUES(?,?,?,?,?,?)',(rule['owner'],rule['id'],version,event['bar_time'],event['created'],json.dumps(event)))
                conn.execute('UPDATE rules SET spec=?,cursor=?,epoch=?,created=?,status=? WHERE id=?',(json.dumps(spec),cursor,version,created,status,rule['id']))
        finally: conn.close()


def evaluate_once():
    conn=open_db()
    try: rules=conn.execute('SELECT * FROM rules').fetchall()
    finally: conn.close()
    for rule in rules:
        try: evaluate_rule(rule)
        except Exception as error:
            print(f'[alerts] evaluation failed for rule {rule["id"]}: {type(error).__name__}',flush=True)
            conn=open_db()
            try:
                with conn:
                    conn.execute('UPDATE rules SET status=? WHERE id=? AND revision=?',
                                 (f'Evaluation error: {type(error).__name__}',rule['id'],rule['revision']))
            finally: conn.close()


def start():
    stop=threading.Event()
    def work():
        while not stop.is_set():
            try: evaluate_once()
            except Exception as error: print(f'[alerts] worker: {type(error).__name__}',flush=True)
            stop.wait(1)
    thread=threading.Thread(target=work,name='stored-alerts',daemon=True);thread.start()
    return stop
