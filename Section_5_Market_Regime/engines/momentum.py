"""Momentum interpretation; all numerical indicators and DI anchors are inputs."""
from copy import deepcopy
import hashlib
import json
import math
from .momentum_config import MomentumConfig

VERSION='1.0.0'
FIELDS=('rsi','di_signed_dominance','roc_pct','momentum_atr','momentum_atr_change','momentum_strength_change',
    'macd_histogram','atr','di_anchor_events','di_anchor_continuous','bull_momentum_divergence','bear_momentum_divergence',
    'di_price_high_time','di_price_high_known_time','di_signed_spread_from_price_high',
    'di_price_low_time','di_price_low_known_time','di_signed_spread_from_price_low',
    'measurement_gap','measurement_version','measurement_config_id')
UNITS={k:'dimensionless' for k in FIELDS}
UNITS.update(rsi='index_0_100',roc_pct='percent',atr='price',macd_histogram='price',di_anchor_events='json',measurement_gap='boolean',measurement_version='version',measurement_config_id='identifier')
for kind in ('high','low'):
    UNITS['di_price_'+kind+'_time']='utc_ms';UNITS['di_price_'+kind+'_known_time']='utc_ms';UNITS['di_signed_spread_from_price_'+kind]='di_points'
for k in ('di_anchor_continuous','bull_momentum_divergence','bear_momentum_divergence'):UNITS[k]='boolean'

def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def clip(v):return max(-1.,min(1.,v))


def evaluate(snapshot,config=None,previous_state=None):
    cfg=config or MomentumConfig()
    if not isinstance(cfg,MomentumConfig):raise TypeError('Use MomentumConfig')
    identity=deepcopy(snapshot['identity']);start,end,known,computed=(snapshot[k] for k in ('candle_open_time','candle_close_time','as_of','computed_at'))
    if set(identity)!={'venue','market_type','instrument_id','symbol','timeframe','dataset_generation'} or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Complete Momentum identity required')
    if any(type(v) is not int or v<0 for v in (start,end,known,computed)) or end<start or computed<known:raise ValueError('Invalid Momentum times')
    closed=snapshot['closed']
    if type(closed) is not bool or closed and known<=end or not closed and known<start:raise ValueError('Invalid candle availability')
    signature=snapshot['input_signature']
    if not isinstance(signature,str) or not signature:raise ValueError('Momentum input signature required')
    if snapshot['provenance_mode'] not in ('LIVE','SIMULATION','HISTORICAL_RECONSTRUCTION'):raise ValueError('Invalid Momentum provenance mode')
    binding=dict(identity=identity,config_hash=cfg.fingerprint,input_signature=signature,state_schema_version=VERSION)
    state=deepcopy(previous_state) if previous_state else dict(**binding,last_open=None,last_close=None,confirmed=None,candidate=None,count=0,weakening=0,corroboration={'BULLISH':None,'BEARISH':None})
    if any(state.get(k)!=v for k,v in binding.items()):raise ValueError('Momentum state identity/config/source mismatch')
    if state['last_open'] is not None and start<=state['last_open']:raise ValueError('Momentum candles must be chronological')
    old=state.get('classification',dict(direction='UNKNOWN',strength_band='UNKNOWN',acceleration='UNKNOWN',condition='UNKNOWN'))
    f={};flags=[];invalid=False
    for key in FIELDS:
        value=snapshot['features'].get(key);at=snapshot['field_available_at'].get(key)
        if value is not None and (snapshot['field_validity'].get(key)!='VALID' or snapshot['units'].get(key)!=UNITS[key] or type(at) is not int or not 0<=at<=known):value=None;flags.append('INPUT_UNAVAILABLE:'+key)
        if value is not None:
            kind=UNITS[key]
            good=isinstance(value,str) if kind in ('json','version','identifier') else value in (0,1) and isinstance(value,(int,float,bool)) if kind=='boolean' else finite(value)
            if good and kind=='boolean':value=bool(value)
            if good and kind=='utc_ms':good=value>=0 and int(value)==value
            if good and key=='rsi':good=0<=value<=100
            if good and key=='di_signed_dominance':good=-1<=value<=1
            if good and key=='atr':good=value>=0
            if not good:value=None;invalid=True;flags.append('INVALID_INPUT:'+key)
        f[key]=value
    prices=[snapshot['candle'].get(k) for k in ('open','high','low','close')]
    raw=all(finite(v) and v>0 for v in prices);raw=raw and prices[1]>=max(prices) and prices[2]<=min(prices)
    gap=state['last_close'] is not None and start!=state['last_close']+1 or f['measurement_gap'] is True
    if gap:state.update(confirmed=None,candidate=None,count=0,weakening=0,corroboration={'BULLISH':None,'BEARISH':None});flags.append('CANDLE_GAP')
    compatible=snapshot.get('feature_parameters',{}).get('measurementMomentumLength')==cfg.momentum_length
    if not compatible:flags.append('INCOMPATIBLE_FEATURE_PARAMETERS')
    shared_ready=f['measurement_version']=='shared-v1' and bool(f['measurement_config_id'])
    if not shared_ready:flags.append('SHARED_FEATURES_UNAVAILABLE')
    usable=raw and not gap and compatible and shared_ready
    price=.75*clip(f['momentum_atr']/cfg.atr_reference)+.25*clip(f['roc_pct']/cfg.roc_reference_pct) if usable and f['momentum_atr'] is not None and f['roc_pct'] is not None else None
    oscillator=(f['rsi']-50)/50 if usable and f['rsi'] is not None else None
    di=f['di_signed_dominance'] if usable else None
    macd=clip(f['macd_histogram']/(f['atr']*cfg.macd_reference_atr)) if usable and cfg.use_macd and f['macd_histogram'] is not None and f['atr'] is not None and f['atr']>0 else None
    anchors={}
    for kind in ('high','low'):
        origin,at,delta=(f['di_price_'+kind+'_time'],f['di_price_'+kind+'_known_time'],f['di_signed_spread_from_price_'+kind])
        valid=usable and f['di_anchor_continuous'] is True and origin is not None and at is not None and delta is not None and origin<=at<=known
        anchors[kind]=clip(delta/cfg.anchor_reference_points) if valid else None
        if not valid:flags.append('ANCHOR_UNAVAILABLE:'+kind)
    if f['di_anchor_continuous'] is not True:
        state['corroboration']={'BULLISH':None,'BEARISH':None};flags.append('DI_ANCHOR_CONTINUITY_UNAVAILABLE')
    admitted=[];pending_turns={};event_valid=False
    if usable and f['di_anchor_continuous'] is True and f['di_anchor_events'] is not None:
        try:
            events=json.loads(f['di_anchor_events'])
            if not isinstance(events,list) or len(events)>16:raise ValueError('Invalid DI event batch')
            for event in events:
                json.dumps(event,allow_nan=False)
                if not isinstance(event,dict):raise ValueError('Invalid DI event')
                if event.get('type') not in ('di_high','di_low'):continue
                if event.get('channel') not in ('di_plus','di_minus','di_signed_spread') or type(event.get('confirmed_time')) is not int or event['confirmed_time']!=end+1 or type(event.get('time')) is not int or not 0<=event['time']<start or not finite(event.get('value')):raise ValueError('Unconfirmed or mistimed DI anchor')
                if event.get('qualified') is not True:continue
                side='BULLISH' if (event['channel'],event['type']) in (('di_plus','di_high'),('di_signed_spread','di_high')) else 'BEARISH' if (event['channel'],event['type']) in (('di_minus','di_high'),('di_signed_spread','di_low')) else None
                if side:
                    ref={k:event[k] for k in ('type','channel','value','time','confirmed_time')};ref['reference_hash']=hashlib.sha256(json.dumps(ref,sort_keys=True,allow_nan=False).encode()).hexdigest();ref['age']=0
                    pending_turns[side]=ref;admitted.append(ref.copy())
            event_valid=True
        except (ValueError,TypeError):pending_turns={};admitted=[];flags.append('INVALID_DI_ANCHOR_EVENTS')
    state['corroboration'].update(pending_turns)
    direction_score=None;proposal=None
    weights=dict(price=.4 if cfg.use_macd else .5,rsi=.2,di=.15,high=.075,low=.075,macd=.1 if cfg.use_macd else 0.)
    values=dict(price=price,rsi=oscillator,di=di,high=anchors['high'],low=anchors['low'],macd=macd)
    if price is not None and oscillator is not None and di is not None:
        direction_score=sum(weights[k]*value for k,value in values.items() if value is not None)
        held=state['confirmed']
        proposal=held if held=='BULLISH' and price>0 and direction_score>=cfg.hold_deadband or held=='BEARISH' and price<0 and direction_score<=-cfg.hold_deadband else 'BULLISH' if price>0 and direction_score>=cfg.entry_deadband else 'BEARISH' if price<0 and direction_score<=-cfg.entry_deadband else 'NEUTRAL'
    if closed:
        if proposal is None:state.update(confirmed=None,candidate=None,count=0)
        elif proposal==state['confirmed']:state.update(candidate=None,count=0)
        else:
            state['count']=state['count']+1 if state['candidate']==proposal else 1;state['candidate']=proposal
            if state['count']>=cfg.confirmation_bars:state.update(confirmed=proposal,candidate=None,count=0)
    status='UNAVAILABLE' if proposal is None else 'CONFIRMED' if state['confirmed']==proposal else 'PENDING'
    count=cfg.confirmation_bars if status=='CONFIRMED' else state['count'] if state['candidate']==proposal else 0
    direction=state['confirmed'] or 'UNKNOWN'
    strength=100*((.55 if cfg.use_macd else .65)*abs(price)+.2*abs(oscillator)+.15*abs(di)+(.1*abs(macd) if cfg.use_macd else 0)) if price is not None and oscillator is not None and di is not None and (not cfg.use_macd or macd is not None) else None
    change=f['momentum_strength_change'] if usable else None
    acceleration='UNKNOWN' if change is None else 'ACCELERATING' if change>=cfg.acceleration_deadband else 'DECELERATING' if change<=-cfg.acceleration_deadband else 'STABLE'
    if closed:state['weakening']=state['weakening']+1 if acceleration=='DECELERATING' and direction in ('BULLISH','BEARISH') and old['direction']==direction else 0
    reference=state['corroboration'].get(direction)
    corroborated=reference is not None and reference['age']<=cfg.corroboration_bars or direction=='BULLISH' and f['bear_momentum_divergence'] is True or direction=='BEARISH' and f['bull_momentum_divergence'] is True
    condition='UNKNOWN' if direction not in ('BULLISH','BEARISH') or status!='CONFIRMED' or acceleration=='UNKNOWN' else 'EXHAUSTING' if state['weakening']>=cfg.exhaustion_bars and corroborated else 'WEAKENING' if acceleration=='DECELERATING' else 'BUILDING' if acceleration=='ACCELERATING' else 'SUSTAINING'
    band='UNKNOWN' if strength is None else 'WEAK' if strength<25 else 'MODERATE' if strength<50 else 'STRONG' if strength<75 else 'VERY_STRONG'
    classification=dict(direction=direction,strength_band=band,acceleration=acceleration,condition=condition)
    contributions={k:weights[k]*(1-abs(v) if proposal=='NEUTRAL' else max(0,v*(1 if proposal=='BULLISH' else -1))) if v is not None and proposal else 0. for k,v in values.items()}
    coverage=sum(weights[k] for k,v in values.items() if v is not None)
    quality='GAP' if gap else 'INVALID' if invalid or not raw else 'WARMUP' if proposal is None else 'VALID' if coverage>=1-1e-12 and change is not None and event_valid else 'PARTIAL'
    if snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION':flags.append('AVAILABILITY_RECONSTRUCTED')
    result=dict(contract_version='1.0.0',engine='MOMENTUM',engine_version=VERSION,state_schema_version=VERSION,identity=identity,candle_open_time=start,candle_close_time=end,as_of=known,computed_at=computed,available_at=computed if closed else None,mode='CONFIRMED' if closed else 'PROVISIONAL',
        classification=classification if closed else old,candidate_classification={**classification,'direction':proposal or 'UNKNOWN'},strength=strength,confidence=round(sum(contributions.values())*count/cfg.confirmation_bars,8),coverage=round(coverage,8),data_quality=quality,quality_flags=sorted(set(flags)),
        measurements={**f,'direction_score':direction_score,'family_scores':values,'evidence_contributions':contributions,'admitted_di_turns':admitted if closed else [],'corroboration':deepcopy(state['corroboration'])},
        confirmation=dict(status=status,candidate_bars=count,required_bars=cfg.confirmation_bars),previous_state=dict(classification=deepcopy(old)),evidence=[dict(code='MOMENTUM_FAMILIES',inputs=list(FIELDS),description='Signed direction and absolute-strength change are separate; exhaustion requires corroboration, not a BUY/SELL rule.')],config_hash=cfg.fingerprint,input_signature=snapshot['input_signature'],provenance=dict(mode=snapshot['provenance_mode'],source_versions=deepcopy(snapshot['source_versions']),dependency_results=[]))
    if closed:
        for key,ref in state['corroboration'].items():
            if ref:
                ref['age']+=1
                if ref['age']>cfg.corroboration_bars:state['corroboration'][key]=None
    state.update(last_open=start,last_close=end,classification=classification)
    return result,state if closed else deepcopy(previous_state)
