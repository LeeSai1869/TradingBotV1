"""Read-only operational readiness across configured analytical scopes."""
from contextlib import contextmanager
import json
import sqlite3
import time
from . import aggregation_processor,data_policy,regime_inputs
from .Symbols import symbols as symbol_registry
from .memory_storage.Storage import engine_store


@contextmanager
def reader():
    conn=None
    try:
        if engine_store.DB_PATH.is_file():
            conn=sqlite3.connect(engine_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)
            conn.row_factory=sqlite3.Row
            conn.execute('BEGIN')
    except (OSError,sqlite3.Error):
        if conn:conn.close()
        conn=None
    try:yield conn
    finally:
        if conn:conn.close()


def select_run(conn,symbol,interval,engine,policy,generation,*,at):
    """Only the current indexed normal-runner cohort, never an arbitrary old run."""
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'mtf_bindings','engine_runs','engine_results'}<=tables:return None,'PUBLICATION_INDEX_UNAVAILABLE'
    row=conn.execute('SELECT generation,run_id,metadata FROM mtf_bindings WHERE symbol=? AND timeframe=? AND engine=? AND known_ms<=? ORDER BY known_ms DESC,id DESC LIMIT 1',(symbol,interval,engine,at)).fetchone()
    if not row:return None,'NOT_INDEXED'
    if row['generation']!=generation:return None,'OUTDATED_PRODUCER'
    if not row['run_id']:return None,'ENGINE_WAITING: '+json.loads(row['metadata']).get('reason','unavailable')
    meta=json.loads(row['metadata']);epoch=[policy['epochs'].get('symbol:'+symbol,0),policy['epochs'].get('interval:'+interval,0)]
    if meta['raw_epoch']!=epoch or meta['revision']!='initial':return None,'OUTDATED_DATA_GENERATION'
    stored=conn.execute('SELECT metadata,cursor FROM engine_runs WHERE run_id=?',(row['run_id'],)).fetchone()
    if not stored:return None,'RUN_UNAVAILABLE'
    run=json.loads(stored['metadata'])
    return dict(run_id=row['run_id'],metadata=run,cursor=stored['cursor']),'READY'


def report(symbols=None,intervals=None,*,max_pairs=1000,now_ms=None):
    if type(max_pairs) is not int or not 1<=max_pairs<=10000:raise ValueError('max_pairs must be 1–10000')
    now=int(time.time()*1000) if now_ms is None else now_ms
    selected=sorted(set(symbols or data_policy.active_symbols()));timeframes=list(dict.fromkeys(intervals or data_policy.active_intervals()))
    if not set(timeframes)<=set(data_policy.INTERVALS):raise ValueError('Unregistered timeframe')
    engines=aggregation_processor.registry();generations={name:aggregation_processor.generation(name) for name in engines}
    result=dict(as_of=now,pairs_requested=len(selected)*len(timeframes),pairs_checked=0,truncated=False,counts={},pairs=[],source='CURRENT_INDEXED_NORMAL_RUNNER_OUTPUTS',predictive_validation='NOT_ESTABLISHED_BY_OPERATIONAL_STATUS')
    source=None
    with data_policy.snapshot_guard(timeout=1),reader() as conn:
        policy=data_policy.read()
        try:
            try:source=regime_inputs.open_sources()
            except regime_inputs.InputsUnavailable:pass
            from Section_4_Features.execution.components import current_signature
            desired=current_signature() if source else None
            for symbol in selected:
                active_symbol=symbol_registry.is_active(symbol) and symbol not in policy['paused_coins']
                for interval in timeframes:
                    if result['pairs_checked']>=max_pairs:result['truncated']=True;return result
                    enabled=active_symbol and policy['timeframes'].get(interval,'active')=='active'
                    pair=dict(symbol=symbol,timeframe=interval,active=enabled,engines={})
                    for engine in engines:
                        item=dict(status='DISABLED' if not enabled else 'ENGINE_MEMORY_UNAVAILABLE',classification=None,coverage=None,confidence=None,run_id=None)
                        if enabled and conn:
                            run,status=select_run(conn,symbol,interval,engine,policy,generations[engine],at=now);item['status']=status
                            if run:
                                item['run_id']=run['run_id'];meta=run['metadata']
                                feature=None;pending=None
                                if source:
                                    feature=source.execute('SELECT signature,generation FROM feature_calculation_versions WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                                    pending=source.execute('SELECT 1 FROM feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                                if not feature or feature[0]!=desired or str(feature[1])!=meta['source_versions']['feature_generation'] or pending:item['status']='FEATURE_REPLAY_PENDING_OR_CHANGED'
                                else:
                                    row=conn.execute('SELECT payload FROM engine_results WHERE run_id=? ORDER BY candle_time DESC LIMIT 1',(run['run_id'],)).fetchone()
                                    if not row:item['status']='NO_COMMITTED_ROWS'
                                    else:
                                        value=json.loads(row[0]);fresh_until=aggregation_processor.advance(value['candle_close_time']+1,interval)+30000
                                        item.update(scope=value.get('measurements',{}).get('scope'),classification=value['classification'],coverage=value['coverage'],confidence=value['confidence'],through_ms=value['candle_open_time'],available_ms=value['available_at'],confirmation=value['confirmation']['status'],quality_flags=value['quality_flags'])
                                        item['status']='FUTURE_PUBLICATION' if value['available_at']>now else 'STALE_OR_BACKLOG' if fresh_until<now else value['data_quality']
                        pair['engines'][engine]=item;counts=result['counts'].setdefault(engine,{})
                        counts[item['status']]=counts.get(item['status'],0)+1
                    result['pairs'].append(pair);result['pairs_checked']+=1
            return result
        finally:
            if source:source.close()
