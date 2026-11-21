"""Bounded independent strategy calculations; no order execution or chart writes."""
from contextlib import closing
import json
import math
import time
from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import adcn_store, db, strategy_store as store
from . import strategy_registry as registry
from .sequence import alternate


def _record(item, definition):
    values={key:(item['features'] or {}).get(key) for key in definition.module.FIELDS}
    values.update(close=item['close'],open_time=item['open_time'],close_time=item['close_time'])
    return {key:(None if isinstance(value,float) and not math.isfinite(value) else value) for key,value in values.items()}


def advance_pair(symbol, interval, *, limit=200, deadline=None):
    if not data_policy.enabled(symbol,interval):return 0
    with closing(adcn_store.open_db()) as conn:items=store.instances(conn,symbol,interval)
    items=[item for item in items if item['enabled']]
    with closing(adcn_store.open_db()) as conn:binding=store.pair(conn,symbol,interval)
    items.sort(key=lambda item:item['id']!=binding['selected_id'])
    count=0
    for index,item in enumerate(items):
        if count>=limit:break
        if deadline is not None and time.monotonic()>=deadline:break
        own_deadline=(time.monotonic()+(deadline-time.monotonic())/(len(items)-index)) if deadline is not None else None
        try:definition=registry.require(item['strategy_id'],item['version'])
        except ValueError:continue
        if definition.fingerprint!=item['fingerprint']:continue
        count+=advance(item,limit=min(100,max(1,(limit-count)//(len(items)-index))),deadline=own_deadline)
    return count


def advance(item, *, limit=100, deadline=None):
    definition=registry.require(item['strategy_id'],item['version'])
    if definition.fingerprint!=item['fingerprint']:raise ValueError('Pinned strategy changed; register a new version')
    symbol=item['symbol'];interval=item['interval'];current_epoch=store.epoch(symbol,interval)
    with closing(adcn_store.open_db()) as conn:saved=store.checkpoint(conn,item['id'])
    state=json.loads(saved['state']) if saved and saved['epoch']==current_epoch else dict(last=item['start_at']-1,previous=[],last_signal=None,seeded=False)
    previous=state['previous'];last_signal=state.get('last_signal');last=state['last']
    if not state.get('seeded'):
        previous=[]
        for bar in db.read_strategy_inputs(symbol,interval,definition.module.FIELDS,before=state['last']+1,limit=definition.module.LOOKBACK):
            if bar['features'] is None:previous=[];continue
            record=_record(bar,definition)
            if previous and previous[-1]['close_time']+1!=record['open_time']:previous=[]
            previous.append(record);previous=previous[-definition.module.LOOKBACK:] if definition.module.LOOKBACK else []
    now=int(time.time()*1000);count=0;events=[]
    for bar in db.read_strategy_inputs(symbol,interval,definition.module.FIELDS,after=last,limit=min(1000,limit)):
        if count and deadline is not None and time.monotonic()>=deadline:break
        if bar['close_time']>=now or bar['features'] is None:break
        current=_record(bar,definition)
        if previous and previous[-1]['close_time']+1!=current['open_time']:previous=[]
        decision=definition.module.evaluate(previous,current) if bar['close_time']>=item['not_before'] else dict(signal_type=None,decision_state='BEFORE_ACTIVATION',trigger=None)
        if definition.alternate_signals:decision,last_signal=alternate(decision,last_signal)
        elif decision['signal_type'] in ('BUY','SELL'):last_signal=decision['signal_type']
        if decision['signal_type'] in ('BUY','SELL'):
            events.append(dict(open_time=bar['open_time'],close_time=bar['close_time'],price=bar['close'],decision=decision,
                strategy=dict(instance_id=item['id'],id=definition.id,version=definition.version,fingerprint=definition.fingerprint),
                evidence=dict(previous=previous,current=current),provenance='confirmed feature-prefix strategy worker'))
        last=bar['open_time'];count+=1
        previous=[*previous,current][-definition.module.LOOKBACK:] if definition.module.LOOKBACK else []
    if not count:return 0
    state=dict(last=last,previous=previous,last_signal=last_signal,seeded=True)
    with data_policy.locked():
        if not data_policy.enabled(symbol,interval) or store.epoch(symbol,interval)!=current_epoch:return 0
        with closing(adcn_store.open_db()) as conn:
            if not store.commit(conn,item,current_epoch,events,state,now,expected_checkpoint=saved):return 0
    return count


def caught_up(symbol, interval, through):
    with closing(adcn_store.open_db()) as conn:
        for item in store.instances(conn,symbol,interval):
            if not item['enabled'] or item['start_at']>through:continue
            saved=store.checkpoint(conn,item['id'])
            if not saved or saved['epoch']!=store.epoch(symbol,interval) or saved['last_open_time']<through:return False
    return True
