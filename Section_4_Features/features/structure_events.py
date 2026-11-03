"""Observe the existing structure confirmation branches; never detect a pivot."""
import hashlib
import json
import math

VERSION='structure-events-v1'
EXPORTS={'structure_events':'string','structure_events_version':'string','structure_event_status':'string'}


def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def new_state():return dict(high=None,low=None,references=[],status='READY')


def identify(symbol,timeframe,event):
    return hashlib.sha256(json.dumps([VERSION,symbol,timeframe,event],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def pivot(state,buffer,symbol,timeframe,client,kind,price,bar,origin):
    if not all(finite(v) for v in (price,bar,origin)) or price<=0 or bar<0 or origin<0 or origin>=client['open_time']:
        state['status']='INVALID_PIVOT_ORIGIN';return state,buffer
    previous=state[kind];label=None
    if previous:
        label=('HIGHER_HIGH' if price>previous['price'] else 'LOWER_HIGH' if price<previous['price'] else 'EQUAL_HIGH') if kind=='high' else ('HIGHER_LOW' if price>previous['price'] else 'LOWER_LOW' if price<previous['price'] else 'EQUAL_LOW')
    event=dict(type='PIVOT_'+kind.upper(),classification=label,price=price,origin_bar=int(bar),origin_time=int(origin),
        confirmation_time=client['open_time'],known_time=client['close_time']+1,previous_id=previous['id'] if previous else None,
        source='Section4.market_structure',source_version=VERSION)
    event['id']=identify(symbol,timeframe,event)
    state[kind]=event;state['references'].append(event);state['references']=state['references'][-64:]
    buffer.append(event);return state,buffer


def transition(state,buffer,symbol,timeframe,client,kind,source_type,pivot_type,pivot_bar):
    expected='PIVOT_HIGH' if pivot_type==1 else 'PIVOT_LOW' if pivot_type==-1 else None
    reference=next((p for p in reversed(state['references']) if p['origin_bar']==pivot_bar and p['type']==expected),None)
    event=dict(type=kind,classification=kind,source_type=source_type,origin_bar=int(pivot_bar) if finite(pivot_bar) else None,
        origin_time=reference['origin_time'] if reference else None,pivot_id=reference['id'] if reference else None,
        confirmation_time=client['open_time'],known_time=client['close_time']+1,source='Section4.market_structure',source_version=VERSION)
    event['id']=identify(symbol,timeframe,event);buffer.append(event);return state,buffer


def update(e):
    e['structure_events'] = json.dumps(e['structureEventBuffer'],sort_keys=True,separators=(',',':'),allow_nan=False)
    e['structure_events_version'] = VERSION
    e['structure_event_status'] = e['structureEventState']['status']
