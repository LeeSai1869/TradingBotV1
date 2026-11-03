"""Conservative adapter of Section 4 structure state, not another pivot detector."""
from copy import deepcopy
import hashlib
import json
import math

VERSION='1.0.0'
FIELDS=('current_structure','bullish_structure_active','bearish_structure_active','range_structure_active',
        'bull_bos_count','bear_bos_count','range_bos_count','last_structure_bos','last_structure_choch',
        'measurement_gap','measurement_version','measurement_config_id')
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
    state=deepcopy(previous_state) if previous_state else dict(**bind,last_open=None,last_close=None,last_event='NONE',counters=None,choch=None,classification=UNKNOWN.copy())
    if any(state.get(k)!=v for k,v in bind.items()):raise ValueError('Structure state identity/config/source mismatch')
    if state['last_open'] is not None and start<=state['last_open']:raise ValueError('Structure candles must be chronological')
    previous=deepcopy(state['classification']);f={};flags=['PIVOT_EVENT_LINEAGE_UNAVAILABLE'];invalid=False
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
    events=[];old_counts=state['counters']
    if usable and count_valid and old_counts is not None:
        if any(a<b for a,b in zip(counters,old_counts)):flags.append('SOURCE_COUNTER_RESET')
        elif counters!=old_counts:
            kind='CHOCH' if f['last_structure_choch'] in ('BullishCHOCH','BearishCHOCH') and f['last_structure_choch']!=state['choch'] else 'BOS'
            event_id=hashlib.sha256(json.dumps([identity,snapshot['source_versions'].get('feature_signature',snapshot['input_signature']),counters,known,kind],sort_keys=True).encode()).hexdigest()
            events.append(dict(id=event_id,type=kind,known_time=known,origin_time=None,source='Section4 cumulative BOS counters',source_type=f['last_structure_bos']))
            state['last_event']=kind;flags.append('BREAK_ORIGIN_UNAVAILABLE')
    elif usable and count_valid and old_counts is None:state['last_event']='UNKNOWN' if sum(counters)>0 else 'NONE'
    mapped=MAP.get(f['current_structure'])
    active=[f[key] for key in ('bullish_structure_active','bearish_structure_active','range_structure_active')]
    coherent=all(type(value) is bool for value in active) and sum(active)==1
    if sum(value is True for value in active)>1:flags.append('CONFLICTING_SOURCE_STATE')
    supported=usable and coherent and mapped is not None and f[mapped[2]] is True
    classification=UNKNOWN.copy()
    if supported:classification.update(direction=mapped[0],condition='CONFIRMED',active_structure=mapped[1],last_event=state['last_event'])
    elif usable:classification.update(condition='DEVELOPING',last_event=state['last_event'])
    if events:classification['condition']='BROKEN';classification['last_event']=state['last_event']
    coverage=(.6 if supported else 0)+(.2 if usable and count_valid else 0)
    if gap:classification=UNKNOWN.copy();events=[]
    quality='GAP' if gap else 'INVALID' if not raw or invalid else 'PARTIAL' if usable else 'WARMUP'
    if snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION':flags.append('AVAILABILITY_RECONSTRUCTED')
    result=dict(contract_version=VERSION,engine='STRUCTURE',engine_version=VERSION,state_schema_version=VERSION,
        identity=identity,candle_open_time=start,candle_close_time=end,as_of=known,computed_at=snapshot['computed_at'],
        available_at=snapshot['computed_at'] if closed else None,mode='CONFIRMED' if closed else 'PROVISIONAL',
        classification=classification if closed else previous,candidate_classification=classification,
        strength=100. if supported else None,confidence=coverage,coverage=coverage,data_quality=quality,quality_flags=sorted(set(flags)),
        measurements={**f,'new_events':events if closed else [],'strength_meaning':'source establishment completeness, not trend strength'},
        confirmation=dict(status='CONFIRMED' if supported and closed else 'PENDING' if usable else 'UNAVAILABLE',candidate_bars=1 if supported and closed else 0,required_bars=1),
        previous_state=dict(classification=previous),evidence=[dict(code='SECTION4_STRUCTURE_ADAPTER',inputs=list(FIELDS),description='Source state and cumulative break counters only; candidate high/low types are not confirmed pivots.')],
        config_hash=CONFIG_HASH,input_signature=snapshot['input_signature'],provenance=dict(mode=snapshot['provenance_mode'],source_versions=deepcopy(snapshot['source_versions']),dependency_results=[]))
    state.update(last_open=start,last_close=end,classification=classification,counters=counters if usable and count_valid else None,choch=f['last_structure_choch'] if usable else None)
    return result,state if closed else deepcopy(previous_state)
