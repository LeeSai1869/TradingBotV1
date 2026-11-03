"""Conservative adapter of Section 4 structure state, not another pivot detector."""
from copy import deepcopy
import hashlib
import json
import math

VERSION='1.1.0'
FIELDS=('current_structure','bullish_structure_active','bearish_structure_active','range_structure_active',
        'bull_bos_count','bear_bos_count','range_bos_count','last_structure_bos','last_structure_choch',
        'measurement_gap','measurement_version','measurement_config_id',
        'structure_events','structure_events_version','structure_event_status')
UNITS={key:'source_enum' for key in FIELDS}
for key in ('bullish_structure_active','bearish_structure_active','range_structure_active','measurement_gap'):UNITS[key]='boolean'
for key in ('bull_bos_count','bear_bos_count','range_bos_count'):UNITS[key]='count'
UNITS.update(measurement_version='version',measurement_config_id='identifier')
CONFIG=dict(adapter_version=VERSION,coverage_state=.6,coverage_break_history=.2,coverage_pivot_events=.2)
CONFIG_HASH=hashlib.sha256(json.dumps(CONFIG,sort_keys=True).encode()).hexdigest()
MAP={'STRUCTURE_BULL':('BULLISH','HH_HL','bullish_structure_active'),
     'STRUCTURE_BEAR':('BEARISH','LH_LL','bearish_structure_active'),
     'STRUCTURE_RANGE':('NEUTRAL','RANGE','range_structure_active')}
UNKNOWN=dict(direction='UNKNOWN',condition='UNKNOWN',last_event='UNKNOWN',active_structure='UNKNOWN')


def evaluate(snapshot,config=None,previous_state=None):
    if config is not None:raise ValueError('Structure v1 uses the documented fixed source mapping')
    identity=deepcopy(snapshot['identity'])
    if set(identity)!={'venue','market_type','instrument_id','symbol','timeframe','dataset_generation'} or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Complete Structure identity required')
    start=snapshot['candle_open_time'];end=snapshot['candle_close_time'];known=snapshot['as_of']
    if any(type(t) is not int or t<0 for t in (start,end,known,snapshot['computed_at'])) or end<start or snapshot['computed_at']<known:raise ValueError('Invalid Structure snapshot times')
    closed=snapshot['closed']
    if type(closed) is not bool or closed and known<=end:raise ValueError('Invalid closed-candle availability')
    bind=dict(identity=identity,config_hash=CONFIG_HASH,input_signature=snapshot['input_signature'],state_schema_version=VERSION)
    state=deepcopy(previous_state) if previous_state else dict(**bind,last_open=None,last_close=None,last_event='NONE',counters=None,choch=None,classification=UNKNOWN.copy(),seen_events=[])
    if any(state.get(k)!=v for k,v in bind.items()):raise ValueError('Structure state identity/config/source mismatch')
    if state['last_open'] is not None and start<=state['last_open']:raise ValueError('Structure candles must be chronological')
    previous=deepcopy(state['classification']);f={};flags=[];invalid=False
    for key in FIELDS:
        value=snapshot['features'].get(key);available=snapshot['field_available_at'].get(key)
        if value is not None and (snapshot['field_validity'].get(key)!='VALID' or snapshot['units'].get(key)!=UNITS[key] or type(available) is not int or not 0<=available<=known):
            value=None;flags.append('INPUT_UNAVAILABLE:'+key)
        if isinstance(value,float) and not math.isfinite(value):value=None;invalid=True
        if value is not None:
            kind=UNITS[key]
            if kind=='boolean' and type(value) is not bool or kind=='count' and (type(value) is not int or value<0) or kind in ('source_enum','version','identifier') and not isinstance(value,str):value=None;invalid=True
        f[key]=value
    prices=[snapshot['candle'].get(k) for k in ('open','high','low','close')]
    raw=all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0 for v in prices)
    raw=raw and prices[1]>=max(prices) and prices[2]<=min(prices)
    gap=state['last_close'] is not None and start!=state['last_close']+1 or f['measurement_gap'] is True
    if gap:flags.append('CANDLE_GAP');state.update(counters=None,last_event='UNKNOWN',choch=None)
    counters=[f[k] for k in ('bull_bos_count','bear_bos_count','range_bos_count')]
    count_valid=all(type(v) is int and v>=0 for v in counters)
    usable=raw and not gap and not invalid and f['measurement_version']=='shared-v1' and bool(f['measurement_config_id'])
    events=[]
    lineage=usable and f['structure_events_version']=='structure-events-v1' and f['structure_event_status']=='READY'
    source_events=[]
    if lineage:
        try:
            source_events=json.loads(f['structure_events'])
            if not isinstance(source_events,list) or len(source_events)>8:raise ValueError('Invalid event batch')
            for event in source_events:
                json.dumps(event,allow_nan=False)
                if not isinstance(event,dict) or not isinstance(event.get('id'),str) or not event['id']:raise ValueError('Missing producer event ID')
                if event['id'] in state['seen_events']:continue
                if event.get('type') not in ('PIVOT_HIGH','PIVOT_LOW','BOS','CHOCH') or event.get('source_version')!='structure-events-v1':raise ValueError('Unknown source event')
                if type(event.get('known_time')) is not int or type(event.get('confirmation_time')) is not int or event.get('known_time')!=end+1 or event.get('confirmation_time')!=start:raise ValueError('Event not confirmed at this candle')
                origin=event.get('origin_time')
                if origin is not None and (type(origin) is not int or not 0<=origin<=start):raise ValueError('Invalid event origin')
                if event['type'].startswith('PIVOT_'):
                    if origin is None or origin>=start or not isinstance(event.get('price'),(int,float)) or isinstance(event['price'],bool) or not math.isfinite(event['price']) or event['price']<=0:raise ValueError('Invalid confirmed pivot')
                    allowed=(None,'HIGHER_HIGH','LOWER_HIGH','EQUAL_HIGH') if event['type']=='PIVOT_HIGH' else (None,'HIGHER_LOW','LOWER_LOW','EQUAL_LOW')
                    if event.get('classification') not in allowed:raise ValueError('Invalid pivot classification')
                events.append(deepcopy(event))
        except (ValueError,TypeError):
            lineage=False;events=[];flags.append('INVALID_STRUCTURE_EVENTS');invalid=True
    if not lineage:flags.append('PIVOT_EVENT_LINEAGE_UNAVAILABLE')
    if usable and not invalid:
        for event in events:
            state['seen_events'].append(event['id'])
            state['seen_events']=state['seen_events'][-256:]
            if event.get('classification'):state['last_event']=event['classification']
            if event['type'] in ('BOS','CHOCH') and event.get('origin_time') is None:flags.append('BREAK_ORIGIN_UNAVAILABLE');lineage=False
    else:events=[]
    breaks=any(event['type'] in ('BOS','CHOCH') for event in events)
    mapped=MAP.get(f['current_structure'])
    active=[f[key] for key in ('bullish_structure_active','bearish_structure_active','range_structure_active')]
    coherent=all(type(value) is bool for value in active) and sum(active)==1
    if sum(value is True for value in active)>1:flags.append('CONFLICTING_SOURCE_STATE')
    supported=usable and not invalid and coherent and mapped is not None and f[mapped[2]] is True
    classification=UNKNOWN.copy()
    if supported:classification.update(direction=mapped[0],condition='CONFIRMED',active_structure=mapped[1],last_event=state['last_event'])
    elif usable and not invalid:classification.update(condition='DEVELOPING',last_event=state['last_event'])
    if breaks:classification['condition']='BROKEN';classification['last_event']=state['last_event']
    coverage=(.6 if supported else 0)+(.2 if usable and count_valid else 0)+(.2 if lineage else 0)
    if gap:classification=UNKNOWN.copy();events=[]
    quality='GAP' if gap else 'INVALID' if not raw or invalid else 'VALID' if coverage>=1-1e-12 else 'PARTIAL' if usable else 'WARMUP'
    if snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION':flags.append('AVAILABILITY_RECONSTRUCTED')
    result=dict(contract_version='1.0.0',engine='STRUCTURE',engine_version=VERSION,state_schema_version=VERSION,
        identity=identity,candle_open_time=start,candle_close_time=end,as_of=known,computed_at=snapshot['computed_at'],
        available_at=snapshot['computed_at'] if closed else None,mode='CONFIRMED' if closed else 'PROVISIONAL',
        classification=classification if closed else previous,candidate_classification=classification,
        strength=100. if supported else None,confidence=coverage,coverage=coverage,data_quality=quality,quality_flags=sorted(set(flags)),
        measurements={**f,'new_events':events if closed else [],'strength_meaning':'source establishment completeness, not trend strength'},
        confirmation=dict(status='CONFIRMED' if supported and closed else 'PENDING' if usable else 'UNAVAILABLE',candidate_bars=1 if supported and closed else 0,required_bars=1),
        previous_state=dict(classification=previous),evidence=[dict(code='SECTION4_STRUCTURE_ADAPTER',inputs=list(FIELDS),description='Section 4 producer-confirmed events retain original IDs, origin and known times; no pivot redetection.')],
        config_hash=CONFIG_HASH,input_signature=snapshot['input_signature'],provenance=dict(mode=snapshot['provenance_mode'],source_versions=deepcopy(snapshot['source_versions']),dependency_results=[]))
    state.update(last_open=start,last_close=end,classification=classification,counters=counters if usable and count_valid else None,choch=f['last_structure_choch'] if usable else None)
    return result,state if closed else deepcopy(previous_state)
