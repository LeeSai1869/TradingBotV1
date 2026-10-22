"""Bounded closed-DI decisions in the existing runner and ADCN memory."""
import json
import math
import threading
import time
import traceback
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import db,adcn_store
from .rules import di_spread_recovery as rule

_LOCK=threading.RLock()
_CACHE={}
_cursor=0
BATCH=200


def _epoch(symbol,interval):
    epochs=data_policy.read()['epochs']
    return [epochs.get(f'symbol:{symbol}',0),epochs.get(f'interval:{interval}',0)]


def _load(symbol,interval):
    epoch=_epoch(symbol,interval);key=(str(adcn_store.DB_PATH),symbol,interval,tuple(epoch))
    if key not in _CACHE:
        conn=adcn_store.open_db()
        try:text=adcn_store.read_rule_state(conn,symbol,interval)
        finally:conn.close()
        state=json.loads(text) if text else None
        if not state or state.get('version')!=rule.VERSION or state.get('epoch')!=epoch:
            state={'version':rule.VERSION,'epoch':epoch,'last':-1,'previous':[],'seeded':False}
        _CACHE[key]=state
    return _CACHE[key]


def reset_pair(symbol,interval):
    for key in list(_CACHE):
        if key[1:3]==(symbol,interval):_CACHE.pop(key,None)


def _record(item):
    fields=item['features'] or {}
    result={key:fields.get(key) for key in rule.FIELDS}
    result.update(open_time=item['open_time'],close_time=item['close_time'])
    return {key:(value if not isinstance(value,float) or math.isfinite(value) else None) for key,value in result.items()}


def _advance(symbol,interval,limit=BATCH,deadline=None):
    if not data_policy.enabled(symbol,interval):return 0
    state=_load(symbol,interval);epoch=state['epoch']
    # Work on a copy. A failed transaction must never move the cached cursor.
    previous=list(state['previous']);rows=[];last=state['last'];now=int(time.time()*1000)
    if not state.get('seeded'):
        seed=db.read_decision_seed(symbol,interval)
        if not seed:return 0
        previous=[]
        for item in seed[:-1]:
            record=_record(item)
            if previous and previous[-1]['close_time']+1!=record['open_time']:previous=[]
            previous.append(record)
        if previous:last=previous[-1]['open_time']
    inputs=db.read_decision_inputs(symbol,interval,last,limit)
    for item in inputs:
        if rows and deadline is not None and time.monotonic()>=deadline:break
        if item['close_time']>=now or item['features'] is None:break
        current=_record(item)
        if previous and previous[-1]['close_time']+1!=current['open_time']:previous=[]
        decision=rule.evaluate(previous,current)
        rows.append({'open_time':item['open_time'],**decision});last=item['open_time']
        # JSON memory stores unavailable inputs as null, never NaN/Infinity.
        previous.append(current)
        previous=previous[-rule.LOOKBACK:]
    if not rows:return 0
    new_state={'version':rule.VERSION,'epoch':epoch,'last':last,'previous':previous,'seeded':True}
    with data_policy.locked():
        if not data_policy.enabled(symbol,interval) or _epoch(symbol,interval)!=epoch:
            reset_pair(symbol,interval);return 0
        conn=adcn_store.open_db()
        try:adcn_store.commit_rule_rows(conn,symbol,interval,rows,last,json.dumps(new_state,allow_nan=False,separators=(',',':')))
        finally:conn.close()
    state.update(new_state)
    buys=sum(row['signal_type']=='BUY' for row in rows)
    print(f'[decision] {symbol} {interval}: +{len(rows)} closed DI decisions, buys={buys}, through={last}',flush=True)
    return len(rows)


def maintenance(symbols,intervals,*,max_bars=BATCH,time_budget=.25):
    global _cursor
    pairs=[(symbol,interval) for symbol in symbols for interval in intervals]
    deadline=time.monotonic()+time_budget;count=0
    with _LOCK:
        for _ in range(len(pairs)):
            symbol,interval=pairs[_cursor%len(pairs)];_cursor+=1
            try:count+=_advance(symbol,interval,max_bars-count,deadline)
            except Exception:
                reset_pair(symbol,interval);traceback.print_exc()
            if count>=max_bars or time.monotonic()>=deadline:break
    return count


def catch_up(symbol,interval):
    with _LOCK:return _advance(symbol,interval)


def process_bar(ev):
    if not data_policy.enabled(ev.symbol,ev.timeframe):return False
    with _LOCK:
        state=_load(ev.symbol,ev.timeframe)
        if state['last']<ev.open_time:
            _advance(ev.symbol,ev.timeframe,deadline=time.monotonic()+.15)
        return state['last']>=ev.open_time
