"""Single-runner, resumable full-history feature conversion in bounded batches.

The feature row and its replay checkpoint commit together. Revision-2 rows are
preserved while the runner progressively replaces them from the first raw bar.
Market downloads remain owned by the existing orchestrator.
"""
from pathlib import Path
import threading
import time
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import db,features_store,klines_store
from Section_4_Features.feature_builder import build_feature_packet
from Section_4_Features.individual.engine import Engine
from Section_4_Features.individual import checkpoint

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
    conn=klines_store.open_db()
    try:rows=klines_store.read_after_page(conn,symbol,interval,engine.context.last_time if engine.context.last_time is not None else -1,max_bars)
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
    """Round-robin replay in the existing runner, including pairs without new bars."""
    global _cursor
    pairs=[(symbol,interval) for symbol in symbols for interval in intervals]
    if not pairs:return 0
    start=time.monotonic();deadline=start+time_budget;count=0
    with _LOCK:
        for _ in range(len(pairs)):
            symbol,interval=pairs[_cursor%len(pairs)];_cursor+=1
            try:count+=_advance(symbol,interval,max_bars-count,deadline)
            except Exception:
                reset_pair(symbol,interval);raise
            if time.monotonic()<deadline:_repair_daily(symbol,interval,deadline)
            if count>=max_bars or time.monotonic()>=deadline:break
    return count


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


def process_bar(ev):
    with _LOCK:
        engine=_load(ev.symbol,ev.timeframe,_epoch(ev.symbol,ev.timeframe))
        if engine.context.last_time is None or engine.context.last_time<ev.open_time:
            # One bounded page also makes the public processor useful outside the
            # orchestrator. False means replay is still behind; never skip bars.
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
        key=(str(path),symbol,interval,_epoch(symbol,interval))
        with _LOCK:
            cached=_PREVIEWS.get(key)
            if not cached or cached[0]!=row[0]:
                state=conn.execute('SELECT state FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                engine=checkpoint.restore(symbol,interval,state[0],_epoch(symbol,interval)) if state else None
                if engine is None:return None
                _PREVIEWS[key]=(row[0],engine)
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
    return fork.step(client,is_confirmed=False,is_realtime=True,daily_bars=daily,is_new=is_new)


def _compute_and_write_one(symbol,interval,bar_open_ms):
    """Compatibility entry: replay missing predecessors before computing a target."""
    with _LOCK:
        engine=_load(symbol,interval,_epoch(symbol,interval))
        while engine.context.last_time is None or engine.context.last_time<bar_open_ms:
            if not _advance(symbol,interval):return 0
        return 1
