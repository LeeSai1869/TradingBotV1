"""Bounded full-history lane, separate from live publications and decisions."""
import json
import threading
import time
from . import aggregation_processor,data_policy,regime_research
from .memory_storage.Storage import engine_store

ENGINES=('REGIME','STRUCTURE','TREND','MOMENTUM','VOLATILITY','PARTICIPATION','PHASE','LIQUIDITY','SENTIMENT','BIAS')
_cursor=0
_lock=threading.RLock()
_messages={}


def advance(symbol,interval,engine,*,limit=100,now_ms=None):
    now=int(time.time()*1000) if now_ms is None else now_ms
    with data_policy.locked(timeout=.02):
        if not data_policy.enabled(symbol,interval):return dict(processed=0,status='paused')
        row=regime_research.catch_up(symbol,interval,limit=limit,since=0,engine_name=engine,
            now_ms=now,lock_timeout=.02,history_dependencies=True)
        conn=engine_store.open_db()
        try:
            run_id=row.get('run_id');meta={}
            stored=conn.execute('SELECT metadata FROM engine_runs WHERE run_id=?',(run_id,)).fetchone() if run_id else None
            if stored:
                run=json.loads(stored[0]);versions=run['source_versions']
                meta={key:run[key] for key in ('identity','engine_version','config_hash','input_signature')}
                meta.update(raw_epoch=json.loads(versions['raw_epoch']),feature_generation=versions['feature_generation'],revision=versions['operator_revision'])
            else:run_id=None
            with conn:
                conn.execute('INSERT OR REPLACE INTO engine_history_bindings VALUES (?,?,?,?,?,?,?,?)',
                    (symbol,interval,engine,aggregation_processor.generation(engine),run_id,engine_store.encode(meta),row['status'],now))
        finally:conn.close()
        return row


def maintenance(symbols,intervals,*,max_bars=400,time_budget=.5,max_pairs=4):
    global _cursor
    pairs=[(s,t,e) for s in symbols for t in intervals for e in ENGINES]
    if not pairs or max_bars<=0 or time_budget<=0:return 0
    total=0;deadline=time.monotonic()+time_budget
    with _lock:
        for _ in range(min(max_pairs,len(pairs))):
            remaining=max_bars-total
            if remaining<5 or time.monotonic()>=deadline:break
            symbol,interval,engine=pairs[_cursor%len(pairs)];_cursor+=1
            try:
                row=advance(symbol,interval,engine,limit=min(100,remaining))
                total+=row['processed']+row.get('dependency_processed',0)
                message=row['status'];key=(symbol,interval,engine)
                if row['processed'] or _messages.get(key)!=message:
                    print(f'[history:{engine.lower()}] {symbol} {interval}: +{row["processed"]}; {message}; through={(row.get("latest") or {}).get("candle_open_time")}',flush=True)
                _messages[key]=message
            except TimeoutError:
                # Rotate rather than allowing one contended history scope to
                # starve the rest. Live work has its own retry policy/budget.
                break
            except Exception as error:
                print(f'[history:{engine.lower()}] {symbol} {interval}: retry on next rotation: {type(error).__name__}: {error}',flush=True)
        active=set(pairs)
        for key in list(_messages):
            if key not in active:_messages.pop(key)
    return total


def select(conn,symbol,interval,engine,policy,generation,*,at):
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'engine_history_bindings' not in tables:return None,'NOT_STARTED'
    head=conn.execute('SELECT generation,run_id,metadata,status FROM engine_history_bindings WHERE symbol=? AND timeframe=? AND engine=? AND updated_ms<=?',(symbol,interval,engine,at)).fetchone()
    if not head:return None,'NOT_STARTED'
    if head[0]!=generation:return None,'OUTDATED_PRODUCER'
    if not head[1]:return None,head[3]
    binding=json.loads(head[2]);epoch=[policy['epochs'].get('symbol:'+symbol,0),policy['epochs'].get('interval:'+interval,0)]
    if binding.get('raw_epoch')!=epoch or binding.get('revision')!='initial':return None,'OUTDATED_DATA_GENERATION'
    row=conn.execute('SELECT metadata,cursor FROM engine_runs WHERE run_id=?',(head[1],)).fetchone()
    if not row:return None,'RUN_UNAVAILABLE'
    meta=json.loads(row[0]);identity=meta['identity']
    if meta['engine']!=engine or identity['symbol']!=symbol or identity['timeframe']!=interval or meta['history_start']!=0:return None,'INCOMPATIBLE_HISTORY_RUN'
    if any(binding.get(k)!=meta.get(k) for k in ('identity','engine_version','config_hash','input_signature')):return None,'INCOMPATIBLE_HISTORY_BINDING'
    return dict(run_id=head[1],metadata=meta,cursor=row[1]),head[3]


def progress(conn,source,symbol,interval,engine,policy,generation,*,at):
    run,status=select(conn,symbol,interval,engine,policy,generation,at=at)
    result=dict(status=status,run_id=run['run_id'] if run else None)
    if not run:return result
    if source is None:return dict(result,status='SOURCE_UNAVAILABLE')
    feature=source.execute('SELECT signature,generation FROM feature_calculation_versions WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
    from Section_4_Features.execution.components import current_signature
    if not feature or feature[0]!=current_signature() or str(feature[1])!=run['metadata']['source_versions']['feature_generation']:return dict(result,status='OUTDATED_FEATURE_GENERATION')
    if source.execute('SELECT 1 FROM feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval)).fetchone():return dict(result,status='FEATURE_REPLAY_PENDING')
    rows,first=conn.execute('SELECT COUNT(*),MIN(candle_time) FROM engine_results WHERE run_id=?',(run['run_id'],)).fetchone()
    latest=source.execute('SELECT MAX(open_time) FROM raw.klines WHERE symbol=? AND interval=? AND close_time<?',(symbol,interval,at)).fetchone()[0]
    cap=source.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
    pending=source.execute('SELECT COUNT(*) FROM raw.klines WHERE symbol=? AND interval=? AND close_time<? AND open_time>?',(symbol,interval,at,run['cursor'])).fetchone()[0]
    result.update(classified_candles=rows,first_ms=first,through_ms=run['cursor'],latest_closed_ms=latest,feature_prefix_ms=cap[0] if cap else None,pending_candles=pending,checkpoint_status=status)
    result['status']='CAUGHT_UP' if pending==0 and rows else 'BACKFILLING' if rows else status
    if status not in ('processed','caught up to committed feature prefix') and pending:result['status']='WAITING: '+status
    if latest is not None and (not cap or cap[0]<latest and run['cursor']>=cap[0]):result['status']='WAITING_FOR_FEATURE_CHECKPOINT'
    return result
