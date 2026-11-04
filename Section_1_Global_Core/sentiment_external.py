"""Optional normalized news/social inputs. No polling, classifier or secret storage.

Providers are configured explicitly. Only scored aggregate observations can become
features; unscored/raw headlines remain unavailable. All revisions are append-only.
"""
from contextlib import contextmanager
import hashlib
import json
import math
import os
import re
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

from .paths import data_path
DB_PATH=data_path('storage/sentiment_sources.db',Path(__file__).with_name('memory_storage')/'Storage'/'sentiment_sources.db')
VERSION='external-sentiment-v1'
MAX_PROVIDERS=20


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(encode(value).encode()).hexdigest()
def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def writer():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True);conn=sqlite3.connect(DB_PATH,timeout=2)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS providers (provider_id TEXT,known_ms INTEGER,config TEXT,
                PRIMARY KEY(provider_id,known_ms));
            CREATE TABLE IF NOT EXISTS observations (provider_id TEXT,event_id TEXT,revision TEXT,received_ms INTEGER,
                published_ms INTEGER,asset TEXT,payload TEXT,PRIMARY KEY(provider_id,event_id,revision));
            CREATE INDEX IF NOT EXISTS sentiment_observed ON observations(provider_id,received_ms DESC,published_ms DESC);
            CREATE INDEX IF NOT EXISTS sentiment_published ON observations(provider_id,asset,published_ms DESC,received_ms DESC);
        ''')
        return conn
    except BaseException:conn.close();raise


@contextmanager
def reader():
    conn=None
    try:
        if DB_PATH.is_file():conn=sqlite3.connect(DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2);conn.execute('BEGIN')
    except (OSError,sqlite3.Error):
        if conn:conn.close()
        conn=None
    try:yield conn
    finally:
        if conn:conn.close()


def valid_url(value):
    if not isinstance(value,str):return False
    parsed=urllib.parse.urlsplit(value)
    return parsed.scheme=='https' and bool(parsed.hostname) and parsed.username is None and parsed.password is None


def configure(config,*,now_ms=None):
    allowed={'provider_id','category','source_name','publisher_group','method','terms_url','enabled','reliability','endpoint','auth_header','auth_env','auth_prefix'}
    if set(config)-allowed:raise ValueError('Unknown provider configuration fields')
    required=('provider_id','source_name','publisher_group','method','terms_url')
    if any(not isinstance(config.get(k),str) or not config[k].strip() or len(config[k])>500 for k in required):raise ValueError('Declare provider identity, publisher group, method and terms URL')
    if config.get('category') not in ('NEWS','SOCIAL') or type(config.get('enabled')) is not bool or not finite(config.get('reliability')) or not 0<config['reliability']<=1:raise ValueError('Invalid provider category/enabled/reliability')
    if not valid_url(config['terms_url']) or config.get('endpoint') and not valid_url(config['endpoint']):raise ValueError('Use HTTPS source/terms URLs without embedded credentials')
    for key in ('auth_header','auth_env','auth_prefix'):
        if config.get(key) is not None and (not isinstance(config[key],str) or '\n' in config[key] or '\r' in config[key]):raise ValueError('Invalid authentication declaration')
    if config.get('auth_env') and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',config['auth_env']):raise ValueError('Use a credential environment-variable name, not its value')
    if config.get('auth_header') and not re.fullmatch(r'[A-Za-z0-9_-]+',config['auth_header']):raise ValueError('Invalid header name')
    if bool(config.get('auth_header'))!=bool(config.get('auth_env')):raise ValueError('Header and environment-variable name are required together')
    now=int(time.time()*1000) if now_ms is None else now_ms
    if type(now) is not int or now<0:raise ValueError('Invalid configuration time')
    conn=writer()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            ids={r[0] for r in conn.execute('SELECT DISTINCT provider_id FROM providers')}
            if config['provider_id'] not in ids and len(ids)>=MAX_PROVIDERS:raise ValueError('Provider limit reached')
            last=conn.execute('SELECT known_ms,config FROM providers WHERE provider_id=? ORDER BY known_ms DESC LIMIT 1',(config['provider_id'],)).fetchone()
            if last and now<last[0]:raise ValueError('Configuration clock moved backwards')
            encoded=encode(config)
            if last and last[0]==now:
                if last[1]!=encoded:raise ValueError('Conflicting configuration at the same time')
            else:conn.execute('INSERT INTO providers VALUES (?,?,?)',(config['provider_id'],now,encoded))
    finally:conn.close()


def import_records(provider_id,records,*,received_ms=None):
    now=int(time.time()*1000) if received_ms is None else received_ms
    if type(now) is not int or now<0 or not isinstance(records,list) or len(records)>200:raise ValueError('Import at most 200 observations with a valid receipt time')
    conn=writer();inserted=0
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            provider=conn.execute('SELECT config FROM providers WHERE provider_id=? AND known_ms<=? ORDER BY known_ms DESC LIMIT 1',(provider_id,now)).fetchone()
            if not provider or not json.loads(provider[0])['enabled']:raise ValueError('Provider is not enabled/configured at receipt time')
            for record in records:
                required=('event_id','revision','asset','published_ms','kind','score')
                if not isinstance(record,dict) or set(record)!=set(required):raise ValueError('Use canonical observation fields only')
                for key in ('event_id','revision','asset'):
                    if not isinstance(record[key],str) or not record[key] or len(record[key])>200:raise ValueError('Invalid observation '+key)
                if type(record['published_ms']) is not int or not 0<=record['published_ms']<=now:raise ValueError('Future/invalid publication time')
                if record['kind'] not in ('AGGREGATE_SENTIMENT','UNSCORED_HEADLINE'):raise ValueError('Unsupported observation kind')
                score=record['score']
                if score is not None and (not finite(score) or not -1<=score<=1):raise ValueError('Scores must be signed fractions [-1,1] or null')
                if record['kind']=='UNSCORED_HEADLINE' and score is not None:raise ValueError('Unscored headlines cannot carry a score')
                key=(provider_id,record['event_id'],record['revision']);encoded=encode(record)
                old=conn.execute('SELECT payload FROM observations WHERE provider_id=? AND event_id=? AND revision=?',key).fetchone()
                if old:
                    if old[0]!=encoded:raise ValueError('Same source revision has conflicting values')
                    continue
                clock=conn.execute('SELECT MAX(received_ms) FROM observations WHERE provider_id=?',(provider_id,)).fetchone()[0]
                if clock is not None and now<clock:raise ValueError('Observation receipt clock moved backwards')
                conn.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?)',(*key,now,record['published_ms'],record['asset'],encoded));inserted+=1
        return inserted
    finally:conn.close()


def project(conn,symbol,as_of):
    if conn is None:return []
    profiles=conn.execute('SELECT p.provider_id,p.known_ms,p.config FROM providers p WHERE p.known_ms=(SELECT MAX(q.known_ms) FROM providers q WHERE q.provider_id=p.provider_id AND q.known_ms<=?) ORDER BY p.provider_id LIMIT ?',(as_of,MAX_PROVIDERS)).fetchall()
    rows=[]
    for provider_id,known,encoded in profiles:
        profile=json.loads(encoded)
        if not profile['enabled']:continue
        record=conn.execute("SELECT o.received_ms,o.payload FROM observations o WHERE o.provider_id=? AND o.received_ms<=? AND o.published_ms<=? AND o.asset IN (?, '*') AND o.rowid=(SELECT q.rowid FROM observations q WHERE q.provider_id=o.provider_id AND q.event_id=o.event_id AND q.received_ms<=? ORDER BY q.received_ms DESC,q.rowid DESC LIMIT 1) ORDER BY o.published_ms DESC,o.received_ms DESC,o.rowid DESC LIMIT 1",(provider_id,as_of,as_of,symbol,as_of)).fetchone()
        if not record:continue
        value=json.loads(record[1])
        rows.append(dict(version=VERSION,provider_id=provider_id,category=profile['category'],source_name=profile['source_name'],publisher_group=profile['publisher_group'],method=profile['method'],terms_url=profile['terms_url'],reliability=profile['reliability'],profile_known_ms=known,
            profile_revision=digest(profile),received_ms=record[0],available_ms=max(record[0],value['published_ms']),**value))
    return rows


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def fetch(provider_id):
    """Explicit opt-in network action; no background poller or automatic activation."""
    now=int(time.time()*1000)
    with reader() as conn:
        if conn is None:raise ValueError('No configured providers')
        row=conn.execute('SELECT config FROM providers WHERE provider_id=? AND known_ms<=? ORDER BY known_ms DESC LIMIT 1',(provider_id,now)).fetchone()
    if not row:raise ValueError('Provider not configured')
    profile=json.loads(row[0]);endpoint=profile.get('endpoint')
    if not profile['enabled'] or not valid_url(endpoint):raise ValueError('An enabled HTTPS endpoint is required')
    headers={'Accept':'application/json','User-Agent':'TradingBotV1-sentiment/1'}
    if profile.get('auth_env'):
        secret=os.environ.get(profile['auth_env'])
        if not secret:raise ValueError('Configured credential environment variable is missing')
        headers[profile['auth_header']]=profile.get('auth_prefix','')+secret
    request=urllib.request.Request(endpoint,headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=10) as response:
            body=response.read(1024*1024+1)
        if len(body)>1024*1024:raise ValueError('Provider response exceeds 1 MiB')
        records=json.loads(body)
    except (urllib.error.URLError,TimeoutError,OSError,ValueError):raise ValueError('Provider request failed; check endpoint, access and response format') from None
    return import_records(provider_id,records)
