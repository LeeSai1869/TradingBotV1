"""Bounded closed-DI decisions in the existing runner and ADCN memory."""
from contextlib import closing
import json
import math
import sqlite3
import threading
import time
import traceback
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import db,adcn_store,features_store
from .rules import di_turning_point as rule
from .sequence import alternate

_LOCK=threading.RLock()
_CACHE={}
_cursor=0
_bulk_cursor=0
BATCH=200


def _epoch(symbol,interval):
    epochs=data_policy.read()['epochs']
    epoch=[epochs.get(f'symbol:{symbol}',0),epochs.get(f'interval:{interval}',0)]
    generation=features_store.decision_generation(symbol,interval)
    return epoch+[generation] if generation else epoch


def _load(symbol,interval):
    epoch=_epoch(symbol,interval);key=(str(adcn_store.DB_PATH),symbol,interval,tuple(epoch))
    if key not in _CACHE:
        conn=adcn_store.open_db()
        try:text=adcn_store.read_rule_state(conn,symbol,interval)
        finally:conn.close()
        state=json.loads(text) if text else None
        if state and state.get('version')==2 and state.get('epoch')==epoch:
            # Preserve closed-bar progress; seed direction from the same historical
            # gate used by chart pages, rather than resetting to an empty state.
            state={**state,'version':rule.VERSION,
                   'last_signal':db.read_previous_decision_candidate(symbol,interval,state['last']+1)}
        if not state or state.get('version')!=rule.VERSION or state.get('epoch')!=epoch:
            state={'version':rule.VERSION,'epoch':epoch,'last':-1,'previous':[],'seeded':bool(len(epoch)>2 and epoch[-1]),'last_signal':None}
        _CACHE[key]=state
    return _CACHE[key]


def reset_pair(symbol,interval):
    for key in list(_CACHE):
        if key[1:3]==(symbol,interval):_CACHE.pop(key,None)


def _record(item):
    fields=item['features'] or {}
    result={key:fields.get(key) for key in rule.FIELDS}
    result.update(close=item.get('close'),open_time=item['open_time'],close_time=item['close_time'])
    return {key:(value if not isinstance(value,float) or math.isfinite(value) else None) for key,value in result.items()}


def _advance(symbol,interval,limit=BATCH,deadline=None,*,recent_only=False):
    if not data_policy.enabled(symbol,interval):return 0
    # A turn can own many pages; the public raw reader accepts at most 1,000.
    limit=min(1000,limit)
    if limit<=0:return 0
    state=_load(symbol,interval);epoch=state['epoch']
    # Work on a copy. A failed transaction must never move the cached cursor.
    previous=list(state['previous']);rows=[];last=state['last'];now=int(time.time()*1000)
    last_signal=state.get('last_signal')
    if not state.get('seeded'):
        seed=db.read_decision_seed(symbol,interval)
        if not seed:return 0
        last_signal=db.read_previous_decision_candidate(symbol,interval,seed[-1]['open_time'])
        previous=[]
        for item in seed[:-1]:
            record=_record(item)
            if previous and previous[-1]['close_time']+1!=record['open_time']:previous=[]
            previous.append(record)
        if previous:last=previous[-1]['open_time']
    recover_recent=False
    if recent_only:
        from Section_1_Global_Core import work_priority
        recover_recent=bool(previous and now-previous[-1]['close_time']<=work_priority.recent_recovery_window(interval))
    inputs=db.read_decision_inputs(symbol,interval,last,min(200,limit) if recover_recent else 13 if recent_only else limit)
    if recent_only and not recover_recent and len(inputs)>12:return 0
    if recent_only:inputs=inputs[:limit]
    for item in inputs:
        if rows and deadline is not None and time.monotonic()>=deadline:break
        if item['close_time']>=now or item['features'] is None:break
        current=_record(item)
        if previous and previous[-1]['close_time']+1!=current['open_time']:previous=[]
        decision,last_signal=alternate(rule.evaluate(previous,current),last_signal)
        rows.append({'open_time':item['open_time'],**decision});last=item['open_time']
        # JSON memory stores unavailable inputs as null, never NaN/Infinity.
        previous.append(current)
        previous=previous[-rule.LOOKBACK:]
    if not rows:return 0
    new_state={'version':rule.VERSION,'epoch':epoch,'last':last,'previous':previous,'seeded':True,'last_signal':last_signal}
    with data_policy.locked():
        if not data_policy.enabled(symbol,interval) or _epoch(symbol,interval)!=epoch:
            reset_pair(symbol,interval);return 0
        conn=adcn_store.open_db()
        try:adcn_store.commit_rule_rows(conn,symbol,interval,rows,last,json.dumps(new_state,allow_nan=False,separators=(',',':')))
        finally:conn.close()
    state.update(new_state)
    signals=[row['open_time'] for row in rows if row['signal_type'] in ('BUY','SELL')]
    if signals:
        try:
            from Section_1_Global_Core.global_packet import store_decision_evidence
            store_decision_evidence(symbol,interval,signals,deadline=min(deadline or float('inf'),time.monotonic()+.15))
        except Exception:
            # Decision commits are authoritative; failed evidence is retried separately.
            traceback.print_exc()

    buys=sum(row['signal_type']=='BUY' for row in rows)
    print(f'[decision] {symbol} {interval}: +{len(rows)} closed DI decisions, buys={buys}, sells={sum(row['signal_type']=='SELL' for row in rows)}, through={last}',flush=True)
    return len(rows)


def maintenance(symbols,intervals,*,max_bars=BATCH,time_budget=.25,pairs=None,bulk_symbol=None):
    global _cursor,_bulk_cursor
    pairs=[(symbol,interval) for symbol in symbols for interval in intervals] if pairs is None else list(pairs)
    started=time.monotonic();deadline=started+time_budget;count=0
    phases=[(pairs,deadline,False)] if bulk_symbol is None else [
        ([p for p in pairs if p[0]!=bulk_symbol],started+time_budget*.25,True),
        ([p for p in pairs if p[0]==bulk_symbol],deadline,False)]
    with _LOCK:
        for lane,lane_deadline,recent_only in phases:
            for _ in lane:
                if count>=max_bars or time.monotonic()>=lane_deadline:break
                if bulk_symbol is not None and not recent_only:
                    symbol,interval=lane[_bulk_cursor%len(lane)];_bulk_cursor+=1
                else:symbol,interval=lane[_cursor%len(lane)];_cursor+=1
                advanced=0
                try:
                    if recent_only:advanced=_advance(symbol,interval,max_bars-count,lane_deadline,recent_only=True)
                    else:advanced=_advance(symbol,interval,max_bars-count,lane_deadline)
                    count+=advanced
                except Exception:
                    reset_pair(symbol,interval);traceback.print_exc()
                if time.monotonic()<lane_deadline and (not recent_only or advanced):
                    try:
                        from Section_1_Global_Core.global_packet import recover_decision_evidence
                        recover_decision_evidence(symbol,interval,deadline=lane_deadline)
                    except Exception:traceback.print_exc()
    return count


def catch_up(symbol,interval):
    with _LOCK:return _advance(symbol,interval)


def process_bar(ev):
    if not data_policy.enabled(ev.symbol,ev.timeframe):return False
    with _LOCK:
        state=_load(ev.symbol,ev.timeframe)
        if state['last']<ev.open_time:
            from Section_1_Global_Core import work_priority
            _advance(ev.symbol,ev.timeframe,deadline=time.monotonic()+.15,recent_only=not work_priority.owns_history(ev.symbol))
        return state['last']>=ev.open_time


def pending_history(symbol,intervals):
    """Read indexed rule checkpoints without creating or rewriting ADCN stores."""
    if not adcn_store.DB_PATH.is_file():return True
    try:
        with closing(sqlite3.connect(adcn_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)) as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='decision_rule_state'").fetchone():return True
            for interval in intervals:
                with closing(sqlite3.connect(features_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)) as source:
                    target=source.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                if not target or target[0] is None:continue
                row=conn.execute('SELECT state FROM decision_rule_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                state=json.loads(row[0]) if row else {}
                if state.get('version')!=rule.VERSION or state.get('epoch')!=_epoch(symbol,interval) or state.get('last',-1)<target[0]:return True
        return False
    except sqlite3.Error:return True
