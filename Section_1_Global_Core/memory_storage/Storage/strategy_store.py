"""Sparse, independently checkpointed strategy histories inside ADCN.db.

Schema creation belongs to adcn_store.open_db. Reader helpers never create files.
"""
import json
import sqlite3
from contextlib import closing
from . import adcn_store

SCHEMA = '''
CREATE TABLE IF NOT EXISTS strategy_versions (strategy_id TEXT NOT NULL, version INTEGER NOT NULL, fingerprint TEXT NOT NULL, PRIMARY KEY(strategy_id,version));
CREATE TABLE IF NOT EXISTS strategy_pairs (
    symbol TEXT NOT NULL, interval TEXT NOT NULL, selected_id TEXT,
    revision INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(symbol,interval));
CREATE TABLE IF NOT EXISTS strategy_instances (
    id TEXT PRIMARY KEY, symbol TEXT NOT NULL, interval TEXT NOT NULL,
    strategy_id TEXT NOT NULL, version INTEGER NOT NULL, fingerprint TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)), start_at INTEGER NOT NULL,
    created_ms INTEGER NOT NULL, not_before INTEGER NOT NULL DEFAULT 0,
    UNIQUE(symbol,interval,strategy_id,version,fingerprint));
CREATE INDEX IF NOT EXISTS strategy_instances_pair ON strategy_instances(symbol,interval);
CREATE TABLE IF NOT EXISTS strategy_checkpoints (
    instance_id TEXT PRIMARY KEY, epoch TEXT NOT NULL, last_open_time INTEGER NOT NULL,
    state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS strategy_events (
    instance_id TEXT NOT NULL, epoch TEXT NOT NULL, open_time INTEGER NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), price REAL NOT NULL,
    payload TEXT NOT NULL, recorded_ms INTEGER NOT NULL,
    PRIMARY KEY(instance_id,epoch,open_time));
CREATE INDEX IF NOT EXISTS strategy_events_time ON strategy_events(instance_id,open_time DESC,side);
'''


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def exists(conn):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name='strategy_pairs'").fetchone())


def records(cursor):
    names=[c[0] for c in cursor.description]
    return [dict(zip(names,row)) for row in cursor.fetchall()]


def instances(conn, symbol=None, interval=None):
    if not exists(conn):return []
    terms=[];args=[]
    for name,value in (('symbol',symbol),('interval',interval)):
        if value is not None:terms.append('i.'+name+'=?');args.append(value)
    return records(conn.execute('SELECT i.*,p.selected_id=i.id AS selected FROM strategy_instances i '
        'JOIN strategy_pairs p ON p.symbol=i.symbol AND p.interval=i.interval WHERE '+(' AND '.join(terms) or '1')+
        ' ORDER BY i.created_ms,i.id',args))


def instance(conn, identity):
    rows=records(conn.execute('SELECT * FROM strategy_instances WHERE id=?',(identity,)))
    return rows[0] if rows else None


def pair(conn, symbol, interval):
    if not exists(conn):return None
    rows=records(conn.execute('SELECT * FROM strategy_pairs WHERE symbol=? AND interval=?',(symbol,interval)))
    return rows[0] if rows else None


def read_pair(symbol, interval):
    if not adcn_store.DB_PATH.is_file():return None
    with closing(sqlite3.connect(adcn_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as conn:
        return pair(conn,symbol,interval)


def epoch(symbol, interval):
    from ... import data_policy
    from . import features_store
    values=data_policy.read()['epochs']
    return dumps([values.get('symbol:'+symbol,0),values.get('interval:'+interval,0),
                  features_store.decision_generation(symbol,interval)])


def checkpoint(conn, identity):
    rows=records(conn.execute('SELECT * FROM strategy_checkpoints WHERE instance_id=?',(identity,)))
    return rows[0] if rows else None


def selected(conn, symbol, interval):
    binding=pair(conn,symbol,interval)
    if binding is None:return None
    item=instance(conn,binding['selected_id']) if binding['selected_id'] else None
    if item and (item['symbol']!=symbol or item['interval']!=interval):item=None
    return dict(binding=binding,instance=item if item and item['enabled'] else None)


def events(conn, identity, *, current_epoch=None, start=0, end=2**63-1, limit=None):
    query='SELECT * FROM strategy_events WHERE instance_id=? AND open_time>=? AND open_time<?';args=[identity,start,end]
    if current_epoch is not None:query+=' AND epoch=?';args.append(current_epoch)
    query+=' ORDER BY open_time'
    if limit is not None:query+=' LIMIT ?';args.append(limit)
    return records(conn.execute(query,args))


def projection(conn, symbol, interval, start, end):
    choice=selected(conn,symbol,interval)
    if choice is None:return None
    item=choice['instance']
    if not item:return []
    current=epoch(symbol,interval)
    out=[]
    for event in events(conn,item['id'],current_epoch=current,start=start,end=end):
        row={key:None for key in adcn_store.COLUMNS}
        row.update(json.loads(event['payload'])['decision'])
        row.update(symbol=symbol,interval=interval,open_time=event['open_time'],signal_type=event['side'],
            strategy_instance_id=item['id'],strategy_id=item['strategy_id'],strategy_version=item['version'],
            strategy_epoch=current,signal_price=event['price'])
        out.append(row)
    return out


def commit(conn, item, current_epoch, decisions, state, recorded_ms, *, expected_checkpoint=None):
    """Caller holds the policy lock; state and accepted events commit atomically."""
    with conn:
        if checkpoint(conn,item['id'])!=expected_checkpoint:return False
        actual=instance(conn,item['id'])
        if not actual or not actual['enabled'] or actual['fingerprint']!=item['fingerprint']:return False
        for event in decisions:
            if event['decision']['signal_type'] not in ('BUY','SELL'):continue
            conn.execute('INSERT OR IGNORE INTO strategy_events VALUES (?,?,?,?,?,?,?)',
                (item['id'],current_epoch,event['open_time'],event['decision']['signal_type'],event['price'],dumps(event),recorded_ms))
        conn.execute('INSERT OR REPLACE INTO strategy_checkpoints VALUES (?,?,?,?)',
            (item['id'],current_epoch,state['last'],dumps(state)))
    return True


def snapshot_status(conn, symbol, interval):
    choice=selected(conn,symbol,interval)
    if choice is not None:
        item=choice['instance'];state=checkpoint(conn,item['id']) if item else None
        valid=bool(state and state['epoch']==epoch(symbol,interval))
        return dict(managed=True,instance_id=item['id'] if item else None,enabled=bool(item),
                    revision=choice['binding']['revision'],through=state['last_open_time'] if valid else -1)
    through=-1
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='decision_rule_state'").fetchone():
        text=adcn_store.read_rule_state(conn,symbol,interval)
        if text:
            state=json.loads(text);expected=json.loads(epoch(symbol,interval))
            if not expected[-1]:expected=expected[:2]
            if state.get('version')==3 and state.get('epoch')==expected:through=state.get('last',-1)
    return dict(managed=False,enabled=True,through=through,revision=0)


def annotate_status(bars, symbol, interval, *, snapshot=None):
    if snapshot is None:
        if not adcn_store.DB_PATH.is_file():return None
        with closing(sqlite3.connect(adcn_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as conn:
            snapshot=snapshot_status(conn,symbol,interval)
    for bar in bars:
        if snapshot['managed']:
            bar['strategy_managed']=True
            bar['strategy_instance_id']=snapshot['instance_id']
        bar['decision_ready']=snapshot['enabled'] and bar['open_time']<=snapshot['through']
    return snapshot if snapshot['managed'] else None



def previous_projection(conn, symbol, interval, before):
    choice=selected(conn,symbol,interval)
    if choice is None:return None
    item=choice['instance']
    if not item:return []
    stamp=conn.execute('SELECT MAX(open_time) FROM strategy_events WHERE instance_id=? AND epoch=? AND open_time<?',
        (item['id'],epoch(symbol,interval),before)).fetchone()[0]
    return projection(conn,symbol,interval,stamp,stamp+1) if stamp is not None else []
