"""Trend v1: pure interpretation of shared measurements and public Structure."""
from copy import deepcopy
import math
from .trend_config import TrendConfig

VERSION='1.0.0'
FIELDS=('ema7','ema25','ema50','ema100','ema200','ema50_slope_atr','ema200_slope_atr',
    'adx','di_signed_dominance','efficiency_ratio','positive_return_fraction','negative_return_fraction','flat_return_fraction',
    'measurement_gap','measurement_version','measurement_config_id','measurement_contiguous_bars')
UNITS={field:'dimensionless' for field in FIELDS}
for field in ('ema7','ema25','ema50','ema100','ema200'):UNITS[field]='price'
UNITS.update(adx='index_0_100',measurement_gap='boolean',measurement_version='version',measurement_config_id='identifier',measurement_contiguous_bars='candles')


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def sign(v):return 1 if v>0 else -1 if v<0 else 0

def evaluate(snapshot,config=None,previous_state=None):
    cfg=config or TrendConfig()
    if not isinstance(cfg,TrendConfig):raise TypeError('Use a validated TrendConfig')
    identity=deepcopy(snapshot['identity']);start,end,as_of,computed=(snapshot[k] for k in ('candle_open_time','candle_close_time','as_of','computed_at'))
    if set(identity)!={'venue','market_type','instrument_id','symbol','timeframe','dataset_generation'} or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Complete Trend identity required')
    if any(type(t) is not int or t<0 for t in (start,end,as_of,computed)) or end<start or computed<as_of:raise ValueError('Invalid Trend time ordering')
    closed=snapshot['closed']
    if type(closed) is not bool or closed and as_of<=end or not closed and as_of<start:raise ValueError('Invalid candle availability')
    signature=snapshot['input_signature']
    if not isinstance(signature,str) or not signature:raise ValueError('Input signature required')
    binding=dict(identity=identity,config_hash=cfg.fingerprint,input_signature=signature,state_schema_version=VERSION)
    state=deepcopy(previous_state) if previous_state else dict(**binding,last_open=None,last_close=None,confirmed=None,candidate=None,count=0,history=[],declining=0,duration=0)
    if any(state.get(k)!=v for k,v in binding.items()):raise ValueError('Trend state identity/config/source mismatch')
    if state['last_open'] is not None and start<=state['last_open']:raise ValueError('Trend candles must be chronological')
    old=state.get('classification',dict(direction='UNKNOWN',strength_band='UNKNOWN',persistence='UNKNOWN',condition='UNKNOWN',structural_alignment='UNAVAILABLE'))
    flags=[];f={};invalid=False
    for key in FIELDS:
        value=snapshot['features'].get(key);known=snapshot['field_available_at'].get(key)
        if value is not None and (snapshot['field_validity'].get(key)!='VALID' or snapshot['units'].get(key)!=UNITS[key] or type(known) is not int or not 0<=known<=as_of):value=None;flags.append('INPUT_UNAVAILABLE:'+key)
        if key.startswith('ema') and value is not None and (not finite(value) or key in ('ema7','ema25','ema50','ema100','ema200') and value<=0):value=None;invalid=True
        if key in ('adx','di_signed_dominance','efficiency_ratio','positive_return_fraction','negative_return_fraction','flat_return_fraction') and value is not None:
            bounds=(0,100) if key=='adx' else (-1,1) if key=='di_signed_dominance' else (0,1)
            if not finite(value) or not bounds[0]<=value<=bounds[1]:value=None;invalid=True
        if key=='measurement_contiguous_bars' and value is not None and (type(value) is not int or value<0):value=None;invalid=True
        if key=='measurement_gap' and value is not None and type(value) is not bool:value=None;invalid=True
        if key in ('measurement_version','measurement_config_id') and value is not None and not isinstance(value,str):value=None;invalid=True
        f[key]=value
    prices=[snapshot['candle'].get(k) for k in ('open','high','low','close')]
    raw=all(finite(v) and v>0 for v in prices)
    raw=raw and prices[1]>=max(prices) and prices[2]<=min(prices)
    gap=state['last_close'] is not None and start!=state['last_close']+1 or f['measurement_gap'] is True
    if gap:flags.append('CANDLE_GAP');state.update(confirmed=None,candidate=None,count=0,history=[],declining=0,duration=0)
    parameters=snapshot.get('feature_parameters',{})
    compatible=all(parameters.get(k)==v for k,v in (('measurementERLength',cfg.er_length),('measurementSlopeLength',cfg.slope_length),('measurementReturnLength',cfg.consistency_length)))
    periods=[parameters.get('ema'+str(p)+'Len') for p in (7,25,50,100,200)]
    compatible=compatible and all(type(p) is int and p>0 for p in periods) and all(a<b for a,b in zip(periods,periods[1:]))
    seed_fraction=min(1.,f['measurement_contiguous_bars']/max(periods)) if compatible and f['measurement_contiguous_bars'] is not None else 0.
    if seed_fraction<1:flags.append('EMA_RECURSIVE_SEED_HISTORY')
    if not compatible:flags.append('INCOMPATIBLE_FEATURE_PARAMETERS')
    shared_ready=f['measurement_version']=='shared-v1' and bool(f['measurement_config_id'])
    if not shared_ready:flags.append('SHARED_FEATURES_UNAVAILABLE')
    usable=raw and not invalid and not gap and compatible and shared_ready
    dep=snapshot.get('dependencies',{}).get('STRUCTURE');dep_direction=None;dep_coverage=0.;references=[]
    if dep:
        expected=snapshot.get('dependency_expectations',{}).get('STRUCTURE',{})
        bound=all(isinstance(expected.get(k),str) and bool(expected[k]) and dep.get(k)==expected[k] for k in ('engine_version','config_hash','input_signature'))
        good=(bound and dep.get('engine')=='STRUCTURE' and dep.get('engine_version')=='1.1.0' and dep.get('identity')==identity and dep.get('mode')=='CONFIRMED'
            and dep.get('candle_open_time')==start and dep.get('candle_close_time')==end and type(dep.get('as_of')) is int and end<dep['as_of']<=as_of)
        reconstructed=snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION' and dep.get('provenance',{}).get('mode')=='HISTORICAL_RECONSTRUCTION'
        available=dep.get('available_at');good=good and type(available) is int and (available<=as_of or reconstructed)
        if reconstructed and good:flags.append('DEPENDENCY_AVAILABILITY_RECONSTRUCTED')
        classification=dep.get('classification',{})
        if good and dep.get('data_quality') in ('VALID','PARTIAL') and classification.get('condition')=='CONFIRMED' and classification.get('direction') in ('BULLISH','BEARISH','NEUTRAL') and finite(dep.get('coverage')) and 0<dep['coverage']<=1:
            dep_direction=classification['direction'];dep_coverage=dep['coverage']
        ref=snapshot.get('dependency_refs',{}).get('STRUCTURE')
        if good and isinstance(ref,str) and ref:references=[ref]
        elif good:dep_direction=None;dep_coverage=0.;flags.append('DEPENDENCY_REFERENCE_UNAVAILABLE')
        if not good:flags.append('STRUCTURE_DEPENDENCY_REJECTED')
    if dep_direction is None:flags.append('STRUCTURE_UNAVAILABLE_MEASUREMENT_ONLY')
    ema_ready=usable and all(f[k] is not None for k in ('ema7','ema25','ema50','ema100','ema200','ema50_slope_atr','ema200_slope_atr'))
    di_ready=usable and f['adx'] is not None and f['di_signed_dominance'] is not None
    movement_ready=usable and all(f[k] is not None for k in ('efficiency_ratio','positive_return_fraction','negative_return_fraction','flat_return_fraction'))
    if movement_ready and abs(sum(f[k] for k in ('positive_return_fraction','negative_return_fraction','flat_return_fraction'))-1)>1e-8:movement_ready=False;flags.append('INVALID_RETURN_FRACTIONS')
    ema_score=None;direction_score=None;proposal=None
    if ema_ready:
        values=[f[k] for k in ('ema7','ema25','ema50','ema100','ema200')]
        alignment=sum(sign(a-b) for a,b in zip(values,values[1:]))/4
        slopes=sum(max(-1,min(1,f[k]/cfg.slope_reference_atr)) for k in ('ema50_slope_atr','ema200_slope_atr'))/2
        position=(sign(prices[3]-f['ema50'])+sign(prices[3]-f['ema200']))/2
        ema_score=.5*alignment+.3*slopes+.2*position
    if ema_ready and di_ready:
        structural={'BULLISH':1,'BEARISH':-1,'NEUTRAL':0}.get(dep_direction,0)
        measurement_score=.5*ema_score+.3*f['di_signed_dominance']
        direction_score=measurement_score+.2*structural*dep_coverage
        held=state['confirmed']
        proposal=held if held=='BULLISH' and measurement_score>0 and direction_score>=cfg.hold_deadband or held=='BEARISH' and measurement_score<0 and direction_score<=-cfg.hold_deadband else 'BULLISH' if measurement_score>0 and direction_score>=cfg.entry_deadband else 'BEARISH' if measurement_score<0 and direction_score<=-cfg.entry_deadband else 'NEUTRAL'
    if closed:
        if proposal is None:state.update(confirmed=None,candidate=None,count=0,duration=0)
        elif proposal==state['confirmed']:state.update(candidate=None,count=0)
        else:
            state['count']=state['count']+1 if state['candidate']==proposal else 1;state['candidate']=proposal
            if state['count']>=cfg.confirmation_bars:state.update(confirmed=proposal,candidate=None,count=0)
    status='UNAVAILABLE' if proposal is None else 'CONFIRMED' if state['confirmed']==proposal else 'PENDING'
    count=cfg.confirmation_bars if status=='CONFIRMED' else state['count'] if state['candidate']==proposal else 0
    direction=state['confirmed'] or 'UNKNOWN'
    strength=100*(.35*abs(ema_score)+.30*min(f['adx']/50,1)+.20*f['efficiency_ratio']+.15*abs(f['positive_return_fraction']-f['negative_return_fraction'])) if ema_ready and di_ready and movement_ready else None
    persistence='UNKNOWN'
    if strength is not None and len(state['history'])>=cfg.persistence_bars:
        change=strength-state['history'][-cfg.persistence_bars]
        persistence='INCREASING' if change>=cfg.persistence_points else 'DECLINING' if change<=-cfg.persistence_points else 'STABLE'
    if closed:
        if strength is None:state.update(history=[],declining=0)
        else:state['history']=(state['history']+[strength])[-(cfg.persistence_bars+1):];state['declining']=state['declining']+1 if persistence=='DECLINING' else 0
        state['duration']=state['duration']+1 if direction in ('BULLISH','BEARISH') and old['direction']==direction else 1 if direction in ('BULLISH','BEARISH') else 0
    alignment='UNAVAILABLE' if dep_direction is None or direction=='UNKNOWN' else 'NEUTRAL' if dep_direction=='NEUTRAL' or direction=='NEUTRAL' else 'ALIGNED' if direction==dep_direction else 'CONFLICTED'
    band='UNKNOWN' if strength is None else 'WEAK' if strength<25 else 'MODERATE' if strength<50 else 'STRONG' if strength<75 else 'VERY_STRONG'
    condition='UNKNOWN' if direction=='UNKNOWN' else 'UNCONFIRMED' if direction=='NEUTRAL' or status!='CONFIRMED' or alignment=='CONFLICTED' else 'EXHAUSTING' if state['declining']>=cfg.exhaustion_bars and strength is not None and strength<cfg.established_strength else 'ESTABLISHED' if alignment=='ALIGNED' and strength is not None and strength>=cfg.established_strength else 'DEVELOPING'
    classification=dict(direction=direction,strength_band=band,persistence=persistence,condition=condition,structural_alignment=alignment)
    candidate_alignment='UNAVAILABLE' if dep_direction is None or proposal is None else 'NEUTRAL' if dep_direction=='NEUTRAL' or proposal=='NEUTRAL' else 'ALIGNED' if proposal==dep_direction else 'CONFLICTED'
    candidate={**classification,'direction':proposal or 'UNKNOWN','structural_alignment':candidate_alignment}
    coverage=.4*ema_ready*seed_fraction+.25*di_ready+.15*movement_ready+(.2*dep_coverage if usable else 0)
    agree=lambda score:1-abs(score) if proposal=='NEUTRAL' else max(0,score*(1 if proposal=='BULLISH' else -1))
    parts=dict(ema=.4*seed_fraction*agree(ema_score) if ema_ready and proposal else 0.,di=.25*agree(f['di_signed_dominance']) if di_ready and proposal else 0.,
        movement=.15*((1-f['efficiency_ratio']+f['flat_return_fraction'])/2 if proposal=='NEUTRAL' else (f['efficiency_ratio']+abs(f['positive_return_fraction']-f['negative_return_fraction']))/2) if movement_ready and proposal else 0.,
        structure=.2*dep_coverage if usable and dep_direction==proposal else 0.)
    confidence=sum(parts.values())*count/cfg.confirmation_bars
    quality='GAP' if gap else 'INVALID' if invalid or not raw else 'WARMUP' if proposal is None else 'VALID' if coverage>=1-1e-12 else 'PARTIAL'
    if snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION':flags.append('AVAILABILITY_RECONSTRUCTED')
    result=dict(contract_version='1.0.0',engine='TREND',engine_version=VERSION,state_schema_version=VERSION,identity=identity,
        candle_open_time=start,candle_close_time=end,as_of=as_of,computed_at=computed,available_at=computed if closed else None,mode='CONFIRMED' if closed else 'PROVISIONAL',
        classification=classification if closed else old,candidate_classification=candidate,strength=strength,confidence=round(confidence,8),coverage=round(coverage,8),
        data_quality=quality,quality_flags=sorted(set(flags)),measurements={**f,'ema_family_score':ema_score,'direction_score':direction_score,'evidence_contributions':parts,'direction_duration_bars':state['duration'],'ema_seed_fraction':seed_fraction},
        confirmation=dict(status=status,candidate_bars=count,required_bars=cfg.confirmation_bars),previous_state=dict(classification=deepcopy(old)),
        evidence=[dict(code='CAPPED_TREND_FAMILIES',inputs=list(FIELDS),description='Separate direction, strength and persistence; evidence scores are not win probabilities.')],
        config_hash=cfg.fingerprint,input_signature=signature,provenance=dict(mode=snapshot['provenance_mode'],source_versions=deepcopy(snapshot['source_versions']),dependency_results=references))
    state.update(last_open=start,last_close=end,classification=classification)
    return result,state if closed else deepcopy(previous_state)
