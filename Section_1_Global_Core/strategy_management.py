"""Admin-owned strategy lifecycle; one selection and independent enabled histories."""
from contextlib import closing
import hashlib
import json
import re
import sqlite3
import time
import uuid
from . import data_policy
from .memory_storage.Storage import adcn_store, strategy_store as store
from Section_8_Decision_Engine import strategy_registry as registry


def validate_pair(symbol, interval):
    if not isinstance(symbol,str) or not re.fullmatch('[A-Z0-9]{2,30}USDT',symbol):raise ValueError('Use a Binance Spot USDT symbol')
    if interval not in data_policy.INTERVALS:raise ValueError('Choose a supported timeframe')
    from .data_admin import catalog
    known={r['symbol'] for key in ('approved','disapproved','pending','staged','top50') for r in catalog().get(key,[]) if isinstance(r,dict) and 'symbol' in r}
    if symbol not in known:raise ValueError('Choose a registered coin')


def _counts(conn, identity):
    row=conn.execute("SELECT COUNT(*),COALESCE(SUM(side='BUY'),0),COALESCE(SUM(side='SELL'),0),MIN(open_time),MAX(open_time) FROM strategy_events WHERE instance_id=?",(identity,)).fetchone()
    state=store.checkpoint(conn,identity)
    return dict(events=row[0],buys=row[1],sells=row[2],first=row[3],last=row[4],through=state['last_open_time'] if state else None)


def catalog():
    from .Symbols import symbols
    rows=[];pairs=[]
    active_symbols=set(data_policy.active_symbols());active_intervals=set(data_policy.active_intervals())
    if adcn_store.DB_PATH.is_file():
        with closing(sqlite3.connect(adcn_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as conn:
            if store.exists(conn):pairs=store.records(conn.execute('SELECT * FROM strategy_pairs ORDER BY symbol,interval'))
            for item in store.instances(conn):
                try:
                    definition=registry.require(item['strategy_id'],item['version']);available=definition.fingerprint==item['fingerprint']
                except ValueError:available=False
                rows.append({**item,**_counts(conn,item['id']),
                    'source_available':available,'market_active':item['symbol'] in active_symbols and item['interval'] in active_intervals})
    return dict(strategies=registry.catalog(),instances=rows,pairs=pairs,symbols=symbols.get_approved_symbols(),
                intervals=data_policy.INTERVALS,note='Only selected-strategy events appear on the chart. Other enabled strategies calculate for comparison. No exchange orders are enabled.')


def _require(conn, identity):
    if not isinstance(identity,str):raise ValueError('Choose a strategy instance')
    if not store.exists(conn):raise ValueError('Strategy instance does not exist')
    value=store.instance(conn,identity)
    if value is None:raise ValueError('Strategy instance does not exist')
    return value


def deletion_preview(conn, item):
    if item['enabled']:raise ValueError('Deactivate this strategy before deleting its memory')
    counts=_counts(conn,item['id'])
    token=hashlib.sha256(store.dumps(dict(instance=item,counts=counts)).encode()).hexdigest()
    return dict(instance_id=item['id'],symbol=item['symbol'],interval=item['interval'],strategy_id=item['strategy_id'],
                version=item['version'],**counts,token=token,required_confirmation='DELETE '+item['id'])


def history(identity, limit=100):
    if type(limit) is not int or not 1<=limit<=500:raise ValueError('History limit must be 1..500')
    if not adcn_store.DB_PATH.is_file():raise ValueError('Strategy instance does not exist')
    with closing(sqlite3.connect(adcn_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as conn:
        item=_require(conn,identity)
        # Bounded recent history, retaining generation identity for comparison.
        rows=store.records(conn.execute('SELECT * FROM strategy_events WHERE instance_id=? ORDER BY open_time DESC,epoch LIMIT ?',(identity,limit)))
        return dict(instance=item,events=[{**r,'payload':json.loads(r['payload'])} for r in rows])


def _recent_start(interval, now):
    from .memory_storage.market_data.update_klines import INTERVAL_MS
    # Include the currently forming candle; the close-time guard prevents
    # announcing any candle already closed when the strategy was enabled.
    duration=31*86400000 if interval=='1M' else INTERVAL_MS[interval]
    return max(0,now-duration+1)


def _pin_version(conn, definition):
    conn.execute('INSERT OR IGNORE INTO strategy_versions VALUES (?,?,?)',
        (definition.id,definition.version,definition.fingerprint))
    saved=conn.execute('SELECT fingerprint FROM strategy_versions WHERE strategy_id=? AND version=?',
        (definition.id,definition.version)).fetchone()[0]
    if saved!=definition.fingerprint:raise ValueError('This strategy version already has another fingerprint; register a new version')


def _continue_legacy(conn, symbol, interval, now):
    """On first switching away, keep the previously implicit v3 rule enabled."""
    definition=registry.require('di_turning_point',3);_pin_version(conn,definition);identity=uuid.uuid4().hex
    conn.execute('INSERT INTO strategy_instances VALUES (?,?,?,?,?,?,?,?,?,?)',
        (identity,symbol,interval,definition.id,definition.version,definition.fingerprint,1,_recent_start(interval,now),now,0))
    text=adcn_store.read_rule_state(conn,symbol,interval)
    old=json.loads(text) if text else {}
    expected=json.loads(store.epoch(symbol,interval))
    legacy_epoch=expected if expected[-1] else expected[:2]
    if old.get('version')==3 and old.get('epoch')==legacy_epoch and type(old.get('last')) is int:
        conn.execute('INSERT INTO strategy_checkpoints VALUES (?,?,?,?)',
            (identity,store.epoch(symbol,interval),old['last'],store.dumps(old)))
    conn.execute('UPDATE strategy_pairs SET selected_id=?,revision=revision+1 WHERE symbol=? AND interval=?',
        (identity,symbol,interval))


def change(action, data):
    if not isinstance(data,dict):raise ValueError('JSON object required')
    with data_policy.locked(), closing(adcn_store.open_db()) as conn, conn:
        if action=='pause_pair':
            symbol=data.get('symbol');interval=data.get('interval');validate_pair(symbol,interval)
            conn.execute('INSERT OR IGNORE INTO strategy_pairs(symbol,interval,revision) VALUES (?,?,1)',(symbol,interval))
            conn.execute('UPDATE strategy_instances SET enabled=0 WHERE symbol=? AND interval=?',(symbol,interval))
            conn.execute('UPDATE strategy_pairs SET selected_id=NULL,revision=revision+1 WHERE symbol=? AND interval=?',(symbol,interval))
            return dict(ok=True)
        if action=='enable':
            symbol=data.get('symbol');interval=data.get('interval');validate_pair(symbol,interval)
            definition=registry.require(data.get('strategy_id'),data.get('version'));_pin_version(conn,definition)
            now=int(time.time()*1000);start=data.get('start_at',_recent_start(interval,now));not_before=0 if 'start_at' in data else now
            if type(start) is not int or not 0<=start<=now:raise ValueError('Start time must be a past/current millisecond timestamp')
            prior=store.pair(conn,symbol,interval)
            conn.execute('INSERT OR IGNORE INTO strategy_pairs(symbol,interval,revision) VALUES (?,?,1)',(symbol,interval))
            if prior is None and (definition.id,definition.version)!=('di_turning_point',3):
                _continue_legacy(conn,symbol,interval,now)
            found=conn.execute('SELECT id FROM strategy_instances WHERE symbol=? AND interval=? AND strategy_id=? AND version=? AND fingerprint=?',
                (symbol,interval,definition.id,definition.version,definition.fingerprint)).fetchone()
            identity=found[0] if found else uuid.uuid4().hex
            if type(data.get('select',True)) is not bool:raise ValueError('Selection must be true or false')
            if found:
                original=store.instance(conn,identity)
                if not original['enabled']:
                    # Resume from now, not through candles observed while paused.
                    saved=store.checkpoint(conn,identity);current_epoch=store.epoch(symbol,interval)
                    old=json.loads(saved['state']) if saved and saved['epoch']==current_epoch else {}
                    resume=_recent_start(interval,now)
                    state=dict(last=resume-1,previous=[],last_signal=old.get('last_signal'),seeded=False)
                    conn.execute('UPDATE strategy_instances SET start_at=?,not_before=? WHERE id=?',(resume,now,identity))
                    conn.execute('INSERT OR REPLACE INTO strategy_checkpoints VALUES (?,?,?,?)',(identity,current_epoch,resume-1,store.dumps(state)))
                conn.execute('UPDATE strategy_instances SET enabled=1 WHERE id=?',(identity,))
            else:conn.execute('INSERT INTO strategy_instances VALUES (?,?,?,?,?,?,?,?,?,?)',
                (identity,symbol,interval,definition.id,definition.version,definition.fingerprint,1,start,now,not_before))
            if data.get('select',True) is not False:
                conn.execute('UPDATE strategy_pairs SET selected_id=?,revision=revision+1 WHERE symbol=? AND interval=?',(identity,symbol,interval))
            return dict(instance_id=identity)
        item=_require(conn,data.get('instance_id'))
        if action=='select':
            if not item['enabled']:raise ValueError('Enable this strategy before selecting it')
            definition=registry.require(item['strategy_id'],item['version'])
            if definition.fingerprint!=item['fingerprint']:raise ValueError('Pinned strategy code changed; register a new version')
            conn.execute('UPDATE strategy_pairs SET selected_id=?,revision=revision+1 WHERE symbol=? AND interval=?',(item['id'],item['symbol'],item['interval']))
        elif action=='deactivate':
            conn.execute('UPDATE strategy_instances SET enabled=0 WHERE id=?',(item['id'],))
            conn.execute('UPDATE strategy_pairs SET selected_id=NULL,revision=revision+1 WHERE symbol=? AND interval=? AND selected_id=?',(item['symbol'],item['interval'],item['id']))
        elif action=='preview_delete':return deletion_preview(conn,item)
        elif action=='delete':
            plan=deletion_preview(conn,item)
            if data.get('token')!=plan['token'] or data.get('confirmation')!=plan['required_confirmation']:raise ValueError('Preview this exact history and type its confirmation before deleting')
            conn.execute('DELETE FROM strategy_events WHERE instance_id=?',(item['id'],))
            conn.execute('DELETE FROM strategy_checkpoints WHERE instance_id=?',(item['id'],))
            conn.execute('DELETE FROM strategy_instances WHERE id=?',(item['id'],))
            # Keep the managed-pair tombstone: deleted histories must not fall
            # back to the legacy global rule or be recreated by evidence recovery.
            return dict(deleted=plan)
        else:raise ValueError('Unknown strategy action')
        return dict(ok=True)
