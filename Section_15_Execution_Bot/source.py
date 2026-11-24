"""Read-only adapters to the existing live strategy and optional selected instances."""
from contextlib import closing
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import adcn_store, features_store, klines_store


def _current_rule():
    from Section_8_Decision_Engine.rules import di_turning_point
    return di_turning_point


def bind_current(config):
    """Pin the installed rule without running/replacing it or changing its state."""
    if config.strategy_source!='current':return config
    fingerprint=hashlib.sha256(Path(_current_rule().__file__).read_bytes()).hexdigest()
    return replace(config,strategy_fingerprint=fingerprint)


def _epoch(symbol,interval):
    values=data_policy.read().get('epochs',{})
    return [values.get('symbol:'+symbol,0),values.get('interval:'+interval,0),
            features_store.decision_generation(symbol,interval)]


def _managed(conn,config,after,start,limit,epoch):
    try:
        from Section_8_Decision_Engine import strategy_registry
    except ImportError:raise ValueError('Selected strategy support is unavailable; use the existing current strategy') from None
    rows=conn.execute('SELECT i.id,i.strategy_id,i.version,i.fingerprint FROM strategy_pairs p '
        'JOIN strategy_instances i ON i.id=p.selected_id AND i.symbol=p.symbol AND i.interval=p.interval '
        'WHERE p.symbol=? AND p.interval=? AND i.enabled=1',(config.symbol,config.interval)).fetchall()
    if not rows:raise ValueError('No enabled strategy is selected for this coin/timeframe')
    identity,strategy_id,version,fingerprint=rows[0]
    if config.strategy_source=='selected' and identity!=config.instance_id:raise ValueError('Configured strategy is no longer selected and enabled')
    definition=strategy_registry.require(strategy_id,version)
    if definition.fingerprint!=fingerprint:raise ValueError('Strategy fingerprint changed')
    key=json.dumps(epoch,sort_keys=True,separators=(',',':'))
    rows=conn.execute('SELECT open_time,side,payload FROM strategy_events WHERE instance_id=? AND epoch=? '
        'AND open_time>=? ORDER BY open_time LIMIT ?',(identity,key,start,limit)).fetchall()
    # Current-mode accounts bind to the effective strategy identity as well as
    # data generation: a strategy switch must never silently trade another rule.
    if config.strategy_source=='current':key=json.dumps(['selected',identity,fingerprint,epoch],separators=(',',':'))
    return dict(epoch=key,events=[dict(open_time=r[0],side=r[1],close_time=json.loads(r[2])['close_time']) for r in rows])


def snapshot(config, after, limit=100, *, armed_at=0):
    if type(limit) is not int or not 1<=limit<=1000:raise ValueError('Signal limit must be 1..1000')
    if not data_policy.enabled(config.symbol,config.interval):raise ValueError('Coin/timeframe is inactive')
    if not adcn_store.DB_PATH.is_file():raise ValueError('Strategy database is unavailable')
    from Section_1_Global_Core.memory_storage.market_data.update_klines import INTERVAL_MS
    duration=31*86400000 if config.interval=='1M' else INTERVAL_MS[config.interval]
    start=max(0,after+1,armed_at-duration)
    epoch=_epoch(config.symbol,config.interval)
    with closing(sqlite3.connect(adcn_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as conn:
        conn.execute('BEGIN')
        managed=conn.execute("SELECT 1 FROM sqlite_master WHERE name='strategy_pairs'").fetchone()
        if managed:managed=conn.execute('SELECT 1 FROM strategy_pairs WHERE symbol=? AND interval=?',(config.symbol,config.interval)).fetchone()
        if managed:return _managed(conn,config,after,start,limit,epoch)
        if config.strategy_source!='current':raise ValueError('No selected strategy instance; use --strategy current for the existing live rule')
        rule=_current_rule();fingerprint=hashlib.sha256(Path(rule.__file__).read_bytes()).hexdigest()
        if not config.strategy_fingerprint or config.strategy_fingerprint!=fingerprint:raise ValueError('Current strategy code changed or is not pinned; create a reviewed allocation')
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='decision_rule_state'").fetchone():raise ValueError('Waiting for the existing strategy checkpoint')
        row=conn.execute('SELECT last_open_time,state FROM decision_rule_state WHERE symbol=? AND interval=?',(config.symbol,config.interval)).fetchone()
        state=json.loads(row[1]) if row else {}
        legacy_epoch=epoch if epoch[-1] else epoch[:2]
        if not row or state.get('version')!=rule.VERSION or state.get('epoch')!=legacy_epoch or state.get('last')!=row[0]:raise ValueError('Waiting for a current strategy checkpoint for this data generation')
        if not klines_store.DB_PATH.is_file():raise ValueError('Candle database is unavailable')
        conn.execute('ATTACH DATABASE ? AS raw',(klines_store.DB_PATH.resolve().as_uri()+'?mode=ro',))
        rows=conn.execute('SELECT d.open_time,d.signal_type,k.close_time FROM decisions d JOIN raw.klines k '
            'ON k.symbol=d.symbol AND k.interval=d.interval AND k.open_time=d.open_time '
            "WHERE d.symbol=? AND d.interval=? AND d.open_time>=? AND d.open_time<=? AND d.trigger=? "
            "AND d.signal_type IN ('BUY','SELL') AND d.decision_state=d.signal_type ORDER BY d.open_time LIMIT ?",
            (config.symbol,config.interval,start,row[0],rule.RULE_ID,limit)).fetchall()
        return dict(epoch=json.dumps(['current',rule.RULE_ID,fingerprint,epoch],separators=(',',':')),
                    events=[dict(open_time=r[0],side=r[1],close_time=r[2]) for r in rows])
