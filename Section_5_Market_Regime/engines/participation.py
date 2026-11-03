"""Activity interpretation of shared volume inputs; no inferred aggressor flow."""
from copy import deepcopy
import hashlib
import json
import math
from .participation_config import ParticipationConfig

VERSION='1.0.0'
FIELDS=('relative_volume_valid','relative_volume','volume_change_pct','price_progress_per_relative_volume','measurement_gap','measurement_version','measurement_config_id')
UNITS={key:'dimensionless' for key in FIELDS}
UNITS.update(relative_volume_valid='boolean',measurement_gap='boolean',volume_change_pct='percent',measurement_version='version',measurement_config_id='identifier')
UNKNOWN=dict(activity='UNKNOWN',participation='UNKNOWN',dominance='UNKNOWN',confirmation='UNKNOWN')


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)


def confirm(item,proposal,bars):
    if proposal is None:item.update(confirmed=None,candidate=None,count=0);return 'UNAVAILABLE',0
    if item.get('confirmed')==proposal:item.update(candidate=None,count=0);return 'CONFIRMED',bars
    count=item.get('count',0)+1 if item.get('candidate')==proposal else 1
    item.update(candidate=proposal,count=count)
    if count>=bars:item.update(confirmed=proposal,candidate=None,count=0);return 'CONFIRMED',bars
    return 'PENDING',count


def evaluate(snapshot,config=None,previous_state=None):
    cfg=config or ParticipationConfig()
    if not isinstance(cfg,ParticipationConfig):raise TypeError('Use ParticipationConfig')
    identity=deepcopy(snapshot['identity']);start,end,known,computed=(snapshot[k] for k in ('candle_open_time','candle_close_time','as_of','computed_at'))
    if set(identity)!={'venue','market_type','instrument_id','symbol','timeframe','dataset_generation'} or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Complete Participation identity required')
    if any(type(v) is not int or v<0 for v in (start,end,known,computed)) or end<start or computed<known:raise ValueError('Invalid Participation times')
    closed=snapshot['closed']
    if type(closed) is not bool or closed and known<=end or not closed and known<start:raise ValueError('Invalid candle availability')
    signature=snapshot['input_signature']
    if not isinstance(signature,str) or not signature:raise ValueError('Participation signature required')
    if snapshot['provenance_mode'] not in ('LIVE','SIMULATION','HISTORICAL_RECONSTRUCTION'):raise ValueError('Invalid provenance')
    binding=dict(identity=identity,config_hash=cfg.fingerprint,input_signature=signature,state_schema_version=VERSION)
    state=deepcopy(previous_state) if previous_state else dict(**binding,last_open=None,last_close=None,dimensions={})
    if any(state.get(k)!=v for k,v in binding.items()):raise ValueError('Participation state identity/config/source mismatch')
    if state['last_open'] is not None and start<=state['last_open']:raise ValueError('Participation candles must be chronological')
    old={key:state['dimensions'].get(key,{}).get('confirmed') or 'UNKNOWN' for key in UNKNOWN}
    f={};invalid=False;flags=[]
    for key in FIELDS:
        value=snapshot['features'].get(key);at=snapshot['field_available_at'].get(key);kind=UNITS[key]
        if value is not None and (snapshot['field_validity'].get(key)!='VALID' or snapshot['units'].get(key)!=kind or type(at) is not int or not 0<=at<=known):value=None;flags.append('INPUT_UNAVAILABLE:'+key)
        if value is not None:
            valid=isinstance(value,str) if kind in ('version','identifier') else (type(value) is bool or finite(value) and value in (0,1)) if kind=='boolean' else finite(value) and value>=0 and int(value)==value if kind=='candles' else finite(value)
            if valid and key=='relative_volume':valid=value>=0
            if not valid:value=None;invalid=True;flags.append('INVALID_INPUT:'+key)
            elif kind=='boolean':value=bool(value)
            elif kind=='candles':value=int(value)
        f[key]=value
    prices=[snapshot['candle'].get(key) for key in ('open','high','low','close')]
    raw=all(finite(v) and v>0 for v in prices);raw=raw and prices[1]>=max(prices) and prices[2]<=min(prices)
    gap=state['last_close'] is not None and start!=state['last_close']+1 or f['measurement_gap'] is True
    if gap:state['dimensions']={};flags.append('CANDLE_GAP')
    shared=f['measurement_version']=='shared-v1' and bool(f['measurement_config_id'])
    calendar=snapshot.get('market_metadata',{}).get('calendar')=='24/7 UTC'
    if not calendar:flags.append('UNSUPPORTED_MARKET_CALENDAR')
    if not shared:flags.append('SHARED_FEATURES_UNAVAILABLE')
    usable=raw and shared and calendar and not gap
    volume_ok=usable and f['relative_volume_valid'] is True and f['relative_volume'] is not None
    rvol=f['relative_volume'] if volume_ok else None
    change=f['volume_change_pct'] if volume_ok else None
    progress=f['price_progress_per_relative_volume'] if volume_ok else None
    price_return=progress*rvol if progress is not None else None
    if price_return is not None and not finite(price_return):price_return=None;flags.append('PRICE_RETURN_OVERFLOW')
    proposals=dict(activity=None,participation=None,dominance=None,confirmation=None)
    if volume_ok:
        proposals['activity']='VERY_LOW' if rvol<cfg.very_low_rvol else 'LOW' if rvol<cfg.low_rvol else 'NORMAL' if rvol<cfg.high_rvol else 'HIGH' if rvol<cfg.extreme_rvol else 'EXTREME'
    if change is not None:
        proposals['participation']='INCREASING' if change>=cfg.change_deadband_pct else 'DECLINING' if change<=-cfg.change_deadband_pct else 'STABLE'
    if price_return is not None:
        moving=abs(price_return)>=cfg.price_deadband_fraction
        proposals['confirmation']='CONFIRMING' if moving and rvol>=cfg.high_rvol else 'DIVERGING' if moving and rvol<cfg.low_rvol else 'NEUTRAL'
        if not moving and rvol>=cfg.high_rvol:flags.append('POTENTIAL_ABSORPTION_OR_TWO_SIDED_ACTIVITY')
    flags.append('AGGRESSOR_FLOW_UNAVAILABLE')
    if not volume_ok:flags.append('VOLUME_BASELINE_UNAVAILABLE')
    statuses={};classification={}
    for key,proposal in proposals.items():
        item=state['dimensions'].setdefault(key,{})
        if closed:status,count=confirm(item,proposal,cfg.confirmation_bars)
        else:status,count=('UNAVAILABLE',0) if proposal is None else ('CONFIRMED',cfg.confirmation_bars) if item.get('confirmed')==proposal else ('PENDING',item.get('count',0) if item.get('candidate')==proposal else 0)
        statuses[key]=dict(status=status,candidate_bars=count,required_bars=cfg.confirmation_bars)
        classification[key]=item.get('confirmed') or 'UNKNOWN'
    weights=dict(activity=.35,participation=.20,confirmation=.20,dominance=.25)
    coverage=sum(weights[key] for key,value in proposals.items() if value is not None)
    contributions={key:weights[key]*statuses[key]['candidate_bars']/cfg.confirmation_bars if proposals[key] is not None else 0. for key in weights}
    events=[]
    if closed:
        for key,value in classification.items():
            if value!='UNKNOWN' and value!=old[key]:
                event=dict(type='PARTICIPATION_TRANSITION',dimension=key,value=value,origin_time=start,known_time=end+1)
                event['id']=hashlib.sha256(json.dumps([identity,cfg.fingerprint,signature,event],sort_keys=True,allow_nan=False).encode()).hexdigest();events.append(event)
    quality='GAP' if gap else 'INVALID' if invalid or not raw else 'PARTIAL' if coverage else 'WARMUP'
    if snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION':flags.append('AVAILABILITY_RECONSTRUCTED')
    result=dict(contract_version='1.0.0',engine='PARTICIPATION',engine_version=VERSION,state_schema_version=VERSION,identity=identity,candle_open_time=start,candle_close_time=end,as_of=known,computed_at=computed,available_at=computed if closed else None,mode='CONFIRMED' if closed else 'PROVISIONAL',
        classification=classification if closed else old,candidate_classification={key:value or 'UNKNOWN' for key,value in proposals.items()},strength=round(100*min(rvol/cfg.extreme_rvol,1),8) if volume_ok else None,confidence=round(sum(contributions.values()),8),coverage=round(coverage,8),data_quality=quality,quality_flags=sorted(set(flags)),
        measurements={**f,'close_return_fraction':price_return,'evidence_contributions':contributions,'dimension_confirmation':statuses,'new_events':events},confirmation=statuses['activity'],previous_state=dict(classification=old),evidence=[dict(code='SAME_SOURCE_VOLUME_CONTEXT',inputs=list(FIELDS),description='RVOL measures activity, one-bar volume change measures participation change, absolute close return measures price progress. No candle-colour aggressor proxy or directional vote.')],config_hash=cfg.fingerprint,input_signature=signature,provenance=dict(mode=snapshot['provenance_mode'],source_versions=deepcopy(snapshot['source_versions']),dependency_results=[]))
    state.update(last_open=start,last_close=end)
    return result,state if closed else deepcopy(previous_state)
