"""Single-runner, resumable full-history feature conversion in bounded batches.

The feature row and its replay checkpoint commit together. Revision-2 rows are
preserved while the runner progressively replaces them from the first raw bar.
Market downloads remain owned by the existing orchestrator.
"""
from pathlib import Path
import threading
import time
import traceback
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import db,features_store,klines_store
from Section_4_Features.feature_builder import build_feature_packet
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import checkpoint,selective
from Section_4_Features.execution.components import current_signature,catalog

WRITE_BATCH=200
_ENGINES={}
_BACKUP_CHECKED=set()
_LOCK=threading.RLock()
_cursor=0


def _epoch(symbol,interval):
    epochs=data_policy.read()['epochs'];return epochs.get(f'symbol:{symbol}',0),epochs.get(f'interval:{interval}',0)


def _load(symbol,interval,epoch):
    key=(str(features_store.DB_PATH),symbol,interval,epoch)
    if key in _ENGINES:return _ENGINES[key]
    conn=features_store.open_db()
    try:row=conn.execute('SELECT state FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
    finally:conn.close()
    engine=checkpoint.restore(symbol,interval,row[0],epoch) if row else None
    if engine is None:engine=Engine(symbol,interval)
    _ENGINES[key]=engine;return engine


def _backup_legacy():
    path=Path(features_store.DB_PATH);backup=path.with_name(path.stem+'.pre-pine-v3.db')
    if str(path) in _BACKUP_CHECKED:return
    if backup.exists():_BACKUP_CHECKED.add(str(path));return
    conn=features_store.open_db()
    try:
        if not conn.execute('SELECT 1 FROM features WHERE COALESCE(formula_version,1)<3 LIMIT 1').fetchone():
            _BACKUP_CHECKED.add(str(path));return
        import sqlite3
        print(f'[processor] preserving previous feature database before replay: {backup}',flush=True)
        target=sqlite3.connect(backup)
        try:conn.backup(target)
        finally:target.close()
        _BACKUP_CHECKED.add(str(path))
        print(f'[processor] preserved previous feature memory: {backup}',flush=True)
    finally:conn.close()


def _advance(symbol,interval,max_bars=WRITE_BATCH,deadline=None):
    epoch=_epoch(symbol,interval)
    if not data_policy.enabled(symbol,interval):return 0
    engine=_load(symbol,interval,epoch)
    _prepare_engine(symbol,interval,engine,epoch)
    if getattr(engine,'_repair_pending',False):return _advance_targeted(symbol,interval,engine,epoch,max_bars,deadline)
    conn=klines_store.open_db()
    try:
        rows=klines_store.read_after_page(conn,symbol,interval,engine.context.last_time if engine.context.last_time is not None else -1,max_bars)
        cursor=klines_store.history_cursor(conn,symbol,interval)
        if cursor is not None:rows=[row for row in rows if row[2]<cursor]
    finally:conn.close()
    if not rows:return 0
    _backup_legacy();output=[]
    for row in rows:
        if output and deadline is not None and time.monotonic()>=deadline:break
        client=dict(zip(('symbol','interval','open_time','open','high','low','close','volume','close_time'),row))
        daily=None
        daily_ready=True
        if interval in ('3d','1w','1M'):
            daily_rows=db.read_klines_tail(symbol,'1d',client['close_time']+1,3)
            expected=(client['close_time']+1)//86400000*86400000-1
            daily_ready=bool(daily_rows and daily_rows[-1][8]==expected)
            daily=[dict(zip(('symbol','interval','open_time','open','high','low','close','volume','close_time'),r)) for r in daily_rows] if daily_ready else []
        packet=build_feature_packet(symbol=symbol,tf=interval,client=client,engine=engine,is_confirmed=True,daily_bars=daily)
        packet.features['daily_source_ready']=daily_ready
        output.append(packet.features)
    if not output:return 0
    with data_policy.locked():
        if not data_policy.enabled(symbol,interval) or epoch!=_epoch(symbol,interval):
            reset_pair(symbol,interval);raise RuntimeError('Feature replay cancelled after data policy changed')
        conn=features_store.open_db()
        try:
            with conn:
                columns=features_store.COLUMNS
                conn.executemany(f'INSERT OR REPLACE INTO features ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})',[[r.get(c) for c in columns] for r in output])
                conn.execute('INSERT OR REPLACE INTO feature_engine_state VALUES (?,?,?,?)',(symbol,interval,engine.context.last_time,checkpoint.dump(engine,epoch)))
                conn.execute('INSERT INTO feature_calculation_versions(symbol,interval,signature,generation) VALUES (?,?,?,0) ON CONFLICT(symbol,interval) DO UPDATE SET signature=excluded.signature',(symbol,interval,current_signature()))
        except Exception:
            reset_pair(symbol,interval);raise
        finally:conn.close()
    print(f'[processor] {symbol} {interval}: +{len(output)} complete feature packets; replay through {engine.context.last_time}',flush=True)
    return len(output)


def catch_up(symbol,interval):
    with _LOCK:
        try:return _advance(symbol,interval)
        except Exception:
            reset_pair(symbol,interval);raise


def maintenance(symbols,intervals,*,max_bars=200,time_budget=1.):
    """Keep bulk symbol priority while reserving progress for other active pairs."""
    global _cursor
    _recover_runtime_format_job(symbols,intervals)
    from Section_1_Global_Core import work_priority
    owner=work_priority.work_symbol(symbols,intervals)
    ordered=([owner]+[s for s in symbols if s!=owner]) if owner else list(symbols)
    pairs=[(symbol,interval) for symbol in ordered for interval in intervals]
    if not pairs:return 0
    start=time.monotonic();deadline=start+time_budget;count=0;service_extra=0
    with _LOCK:
        service=work_priority.service_pair(symbols,intervals,owner,'features')
        if service:
            try:
                print(f'[processor] background feature turn: {service[0]} {service[1]}',flush=True)
                cap=max(1,max_bars//4)
                serviced=_advance(*service,cap,min(deadline,start+time_budget*.25));count+=serviced
                service_extra=max(0,serviced-cap)
            except Exception:
                reset_pair(*service);traceback.print_exc()
        for _ in range(len(intervals)):
            if count-service_extra>=max_bars or time.monotonic()>=deadline:break

            # Cursor rotates frames of the owner, not the entire coin universe.
            symbol,interval=pairs[_cursor%len(intervals)];_cursor+=1
            try:count+=_advance(symbol,interval,max_bars-count+service_extra,deadline)
            except Exception as error:
                reset_pair(symbol,interval)
                print(f'[processor] replay failed {symbol} {interval}; checkpoint retained, other pairs continue: {error}',flush=True)
                traceback.print_exc()
                # A corrupt symbol must not stop healthy symbols. Its committed
                # checkpoint remains unchanged and it is retried next cycle.
                for other in ordered[1:]:
                    for other_interval in intervals:
                        if count-service_extra>=max_bars or time.monotonic()>=deadline:break
                        try:count+=_advance(other,other_interval,max_bars-count+service_extra,deadline)
                        except Exception:
                            reset_pair(other,other_interval);traceback.print_exc()
                break
            if time.monotonic()<deadline:
                try:_repair_daily(symbol,interval,deadline)
                except Exception as error:
                    print(f'[processor] daily repair failed {symbol} {interval}: {error}',flush=True)
                    traceback.print_exc()
            if count-service_extra>=max_bars or time.monotonic()>=deadline:break
    return count


def _recover_runtime_format_job(symbols,intervals):
    """Retire one proven formatting-only job, even outside the history owner.

    Metadata work only: never run another symbol's feature calculations here.
    Without this, completed frames of other symbols could stay masked behind a
    long real history backlog of the selected owner.
    """
    if not Path(features_store.DB_PATH).exists():return
    conn=features_store.open_db()
    try:jobs=conn.execute('SELECT symbol,interval,signature FROM feature_replay_jobs').fetchall()
    finally:conn.close()
    if not jobs:return
    from .execution.components import legacy_runtime_sources,digest,desired_parameters
    signature=digest([digest(legacy_runtime_sources()),desired_parameters()])
    for symbol,interval,revision in jobs:
        if symbol not in symbols or interval not in intervals or revision!=signature:continue
        if not data_policy.enabled(symbol,interval):continue
        epoch=_epoch(symbol,interval)
        with data_policy.locked():
            if epoch!=_epoch(symbol,interval) or not data_policy.enabled(symbol,interval):return
            conn=features_store.open_db()
            try:
                saved=conn.execute('SELECT state FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                engine=checkpoint.restore(symbol,interval,saved[0],epoch) if saved else None
                if engine:
                    with conn:selective.prepare(conn,engine,epoch)
            finally:conn.close()
        reset_pair(symbol,interval)
        return


def _repair_daily(symbol,interval,deadline):
    """Fill security-only outputs once the existing runner downloads 1D inputs."""
    if interval not in ('3d','1w','1M'):return
    epoch=_epoch(symbol,interval);conn=features_store.open_db()
    try:times=[r[0] for r in conn.execute('SELECT open_time FROM features WHERE symbol=? AND interval=? AND formula_version=3 AND daily_source_ready=0 ORDER BY open_time LIMIT 20',(symbol,interval))]
    finally:conn.close()
    updates=[]
    for timestamp in times:
        if time.monotonic()>=deadline:break
        raw=db.read_klines_tail(symbol,interval,timestamp+1,1)
        if not raw:continue
        row=raw[0];daily=db.read_klines_tail(symbol,'1d',row[8]+1,3)
        if not daily or daily[-1][8]!=(row[8]+1)//86400000*86400000-1:break
        high=daily[-2][4] if len(daily)>1 else None;low=daily[-2][5] if len(daily)>1 else None;opening=daily[-1][3];close=row[6]
        updates.append((high,low,opening,(high-close)/close*100 if high is not None and close else None,(close-low)/close*100 if low is not None and close else None,(close-opening)/close*100 if close else None,symbol,interval,timestamp))
    if updates:
        with data_policy.locked():
            if epoch!=_epoch(symbol,interval) or not data_policy.enabled(symbol,interval):return
            conn=features_store.open_db()
            try:
                with conn:conn.executemany('UPDATE features SET previous_day_high=?,previous_day_low=?,day_open=?,distance_to_pdh=?,distance_to_pdl=?,distance_from_day_open=?,daily_source_ready=1 WHERE symbol=? AND interval=? AND open_time=? AND formula_version=3',updates)
            finally:conn.close()


def process_bar(ev, *, historical_replay=True):
    with _LOCK:
        epoch=_epoch(ev.symbol,ev.timeframe)
        engine=_load(ev.symbol,ev.timeframe,epoch)
        _prepare_engine(ev.symbol,ev.timeframe,engine,epoch)
        if getattr(engine,'_repair_pending',False):
            if not historical_replay:return False
            _advance(ev.symbol,ev.timeframe,WRITE_BATCH,time.monotonic()+.25)
            return False
        if engine.context.last_time is None or engine.context.last_time<ev.open_time:
            if not historical_replay:
                previous=engine.context.last_client
                if not previous or previous['close_time']+1!=ev.open_time:return False
            try:_advance(ev.symbol,ev.timeframe,WRITE_BATCH,time.monotonic()+.25)
            except Exception:
                reset_pair(ev.symbol,ev.timeframe);raise
        return engine.context.last_time is not None and engine.context.last_time>=ev.open_time


def reset_pair(symbol,interval):
    for key in list(_ENGINES):
        if key[1:3]==(symbol,interval):_ENGINES.pop(key,None)


_PREVIEWS={}

def preview(symbol,interval,client,*,is_new=True):
    """Read the runner checkpoint without schema writes and fork it for one tick."""
    import copy
    import sqlite3
    path=Path(features_store.DB_PATH)
    if not path.exists():return None
    conn=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
    try:
        row=conn.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
        if not row:return None
        revision=None
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_calculation_versions'").fetchone():
            revision=conn.execute('SELECT signature FROM feature_calculation_versions WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
        stamp=(row[0],revision)
        repair=features_store.pending_replay(conn,symbol,interval)
        key=(str(path),symbol,interval,_epoch(symbol,interval))
        with _LOCK:
            cached=_PREVIEWS.get(key)
            if not cached or cached[0]!=stamp:
                state=conn.execute('SELECT state FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                engine=checkpoint.restore(symbol,interval,state[0],_epoch(symbol,interval)) if state else None
                if engine is None:return None
                _PREVIEWS[key]=(stamp,engine)
                if len(_PREVIEWS)>64:_PREVIEWS.pop(next(iter(_PREVIEWS)))
            else:engine=cached[1]
            if not engine.context.last_client or engine.context.last_client['close_time']+1!=client['open_time']:return None
            fork=copy.deepcopy(engine)
    except sqlite3.OperationalError as error:
        if 'no such table' in str(error):return None
        raise
    finally:conn.close()
    daily=None
    if interval in ('3d','1w','1M'):
        now=int(time.time()*1000);day_start=now//86400000*86400000
        closed=db.read_klines_tail(symbol,'1d',day_start,2)
        daily=[]
        if closed and closed[-1][8]==day_start-1:
            daily=[dict(open=r[3],high=r[4],low=r[5]) for r in closed]
            opening=None
            for source in ('1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h'):
                rows=db.read_klines_tail(symbol,source,day_start+1,1)
                if rows and rows[0][2]==day_start:opening=rows[0][3];break
            # Only current-day open is used; high/low references point to the
            # previous actual daily candle, never to a fabricated weekly range.
            daily.append({'open':opening})
    result=fork.step(client,is_confirmed=False,is_realtime=True,daily_bars=daily,is_new=is_new)
    if repair:
        for column in repair[2]:result[column]=None
    return result


def _compute_and_write_one(symbol,interval,bar_open_ms):
    """Compatibility entry: replay missing predecessors before computing a target."""
    with _LOCK:
        engine=_load(symbol,interval,_epoch(symbol,interval))
        while engine.context.last_time is None or engine.context.last_time<bar_open_ms:
            if not _advance(symbol,interval):return 0
        return 1



def _advance_targeted(symbol,interval,base,epoch,max_bars,deadline):
    """Patch affected columns and partial state atomically; never replace rows."""
    import json
    started=time.monotonic()
    conn=features_store.open_db()
    try:job=selective.read_job(conn,symbol,interval)
    finally:conn.close()
    if not job:base._repair_pending=False;return 0
    plan=catalog().plan(set(json.loads(job['changed'])))
    restored=checkpoint.restore(symbol,interval,job['state'],epoch) if job['state'] else None
    if job['state'] and restored is None:raise RuntimeError('Invalid selective replay checkpoint; stored features retained')
    partial=selective.PartialEngine(symbol,interval,plan,selective.desired_parameters(),restored.context if restored else None)
    raw=klines_store.open_db()
    try:rows=[r for r in klines_store.read_after_page(raw,symbol,interval,job['last_time'],min(1000,max_bars*5)) if r[2]<=job['target']]
    finally:raw.close()
    if not rows:raise RuntimeError('Missing raw history for selective replay; checkpoint retained')
    conn=features_store.open_db()
    required={catalog().export[field] for field in plan.reads|plan.history_keys|{'regimeState'} if field in catalog().export and field not in plan.state_writes}
    required.update(catalog().export[field] for field in plan.shadowed)
    if 'mtfData.vwapValue' in plan.reads:required.add('vwap')
    if 'mtfData.volumeMA' in plan.reads:required.add('volume_ma')
    try:stored={r['open_time']:r for r in features_store.read_replay_inputs(conn,symbol,interval,rows[0][2],rows[-1][2]+1,required)}
    finally:conn.close()
    output=[]
    for row in rows:
        if output and deadline is not None and time.monotonic()>=deadline:break
        old=stored.get(row[2])
        if not old or old.get('formula_version')!=3:raise RuntimeError('Selective replay requires the committed full feature prefix')
        client=dict(zip(('symbol','interval','open_time','open','high','low','close','volume','close_time'),row))
        daily=None;ready=True
        if interval in ('3d','1w','1M') and 'daily_source_ready' in plan.columns:
            daily_rows=db.read_klines_tail(symbol,'1d',client['close_time']+1,3)
            ready=bool(daily_rows and daily_rows[-1][8]==(client['close_time']+1)//86400000*86400000-1)
            daily=[dict(zip(('symbol','interval','open_time','open','high','low','close','volume','close_time'),r)) for r in daily_rows] if ready else []
        result=partial.step(client,old,daily_bars=daily);result['daily_source_ready']=ready
        output.append(result)
    last=partial.context.last_time;complete=last>=job['target']
    columns=sorted(set(plan.columns)&set(features_store.COLUMNS)-{'symbol','interval','open_time','formula_version'})
    merged=selective.merge(base,partial) if complete else None
    with data_policy.locked():
        if epoch!=_epoch(symbol,interval) or not data_policy.enabled(symbol,interval):
            reset_pair(symbol,interval);return 0
        conn=features_store.open_db()
        try:
            with conn:
                if columns:
                    conn.executemany('UPDATE features SET '+','.join(f'{c}=?' for c in columns)+' WHERE symbol=? AND interval=? AND open_time=?',
                                     [[r.get(c) for c in columns]+[symbol,interval,r['open_time']] for r in output])
                if complete:
                    conn.execute('UPDATE feature_engine_state SET state=? WHERE symbol=? AND interval=?',(checkpoint.dump(merged,epoch),symbol,interval))
                    conn.execute('DELETE FROM feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval))
                    conn.execute('UPDATE feature_calculation_versions SET signature=? WHERE symbol=? AND interval=?',(current_signature(),symbol,interval))
                else:
                    conn.execute('UPDATE feature_replay_jobs SET last_time=?,state=? WHERE symbol=? AND interval=?',(last,checkpoint.dump(partial,epoch),symbol,interval))
        finally:conn.close()
    if complete:
        key=(str(features_store.DB_PATH),symbol,interval,epoch)
        merged._repair_pending=False;merged._prepared_signature=current_signature();_ENGINES[key]=merged
    print(f'[processor] {symbol} {interval}: targeted +{len(output)} rows, {len(columns)} columns; through={last}; complete={complete}; {len(output)/max(.001,time.monotonic()-started):.1f} rows/s',flush=True)
    return len(output)



def _prepare_engine(symbol,interval,engine,epoch):
    signature=current_signature()
    if getattr(engine,'_prepared_signature',None)==signature:return
    with data_policy.locked():
        if epoch!=_epoch(symbol,interval) or not data_policy.enabled(symbol,interval):return
        conn=features_store.open_db()
        try:
            with conn:job=selective.prepare(conn,engine,epoch)
        finally:conn.close()
    engine._repair_pending=bool(job);engine._prepared_signature=signature
