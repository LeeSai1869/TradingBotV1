"""Direction-free interpretation of shared volatility inputs; no new indicators."""
from copy import deepcopy
import hashlib
import json
import math
from .volatility_config import VolatilityConfig

VERSION='1.0.0'
FIELDS=('atr','prev_atr','prev_close','candle_range','natr_pct','natr_percentile','natr_baseline_count','natr_baseline_degenerate',
    'bb_width_fraction','bb_width_percentile','bb_width_baseline_count','bb_width_baseline_degenerate',
    'natr_change_fraction','bb_width_change_fraction','realized_volatility','return_skewness','zero_price_movement',
    'measurement_contiguous_bars','measurement_gap','measurement_version','measurement_config_id')
UNITS={key:'dimensionless' for key in FIELDS}
for key in ('atr','prev_atr','prev_close','candle_range'):UNITS[key]='price'
for key in ('natr_percentile','bb_width_percentile'):UNITS[key]='percentile_0_100'
for key in ('natr_baseline_count','bb_width_baseline_count','measurement_contiguous_bars'):UNITS[key]='candles'
for key in ('natr_baseline_degenerate','bb_width_baseline_degenerate','zero_price_movement','measurement_gap'):UNITS[key]='boolean'
UNITS.update(natr_pct='percent',measurement_version='version',measurement_config_id='identifier')
UNKNOWN=dict(level='UNKNOWN',state='UNKNOWN',distribution='UNKNOWN',shock='UNKNOWN')
LEVELS=('EXTREMELY_LOW','LOW','NORMAL','HIGH','EXTREME')


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def level(rank):return LEVELS[0] if rank<10 else LEVELS[1] if rank<25 else LEVELS[2] if rank<75 else LEVELS[3] if rank<90 else LEVELS[4]


def confirm(item,proposal,bars):
    if proposal is None:item.update(confirmed=None,candidate=None,count=0);return 'UNAVAILABLE',0
    if item.get('confirmed')==proposal:item.update(candidate=None,count=0);return 'CONFIRMED',bars
    count=item.get('count',0)+1 if item.get('candidate')==proposal else 1
    item.update(candidate=proposal,count=count)
    if count>=bars:item.update(confirmed=proposal,candidate=None,count=0);return 'CONFIRMED',bars
    return 'PENDING',count


def evaluate(snapshot,config=None,previous_state=None):
    cfg=config or VolatilityConfig()
    if not isinstance(cfg,VolatilityConfig):raise TypeError('Use VolatilityConfig')
    identity=deepcopy(snapshot['identity']);start,end,known,computed=(snapshot[k] for k in ('candle_open_time','candle_close_time','as_of','computed_at'))
    if set(identity)!={'venue','market_type','instrument_id','symbol','timeframe','dataset_generation'} or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Complete Volatility identity required')
    if any(type(v) is not int or v<0 for v in (start,end,known,computed)) or end<start or computed<known:raise ValueError('Invalid Volatility times')
    closed=snapshot['closed']
    if type(closed) is not bool or closed and known<=end or not closed and known<start:raise ValueError('Invalid candle availability')
    signature=snapshot['input_signature']
    if not isinstance(signature,str) or not signature:raise ValueError('Volatility signature required')
    if snapshot['provenance_mode'] not in ('LIVE','SIMULATION','HISTORICAL_RECONSTRUCTION'):raise ValueError('Invalid provenance')
    binding=dict(identity=identity,config_hash=cfg.fingerprint,input_signature=signature,state_schema_version=VERSION)
    state=deepcopy(previous_state) if previous_state else dict(**binding,last_open=None,last_close=None,dimensions={},last_shock=None)
    if any(state.get(k)!=v for k,v in binding.items()):raise ValueError('Volatility state identity/config/source mismatch')
    if state['last_open'] is not None and start<=state['last_open']:raise ValueError('Volatility candles must be chronological')
    old={key:state['dimensions'].get(key,{}).get('confirmed') or 'UNKNOWN' for key in UNKNOWN}
    f={};invalid=False;flags=[]
    for key in FIELDS:
        value=snapshot['features'].get(key);at=snapshot['field_available_at'].get(key);kind=UNITS[key]
        if value is not None and (snapshot['field_validity'].get(key)!='VALID' or snapshot['units'].get(key)!=kind or type(at) is not int or not 0<=at<=known):value=None;flags.append('INPUT_UNAVAILABLE:'+key)
        if value is not None:
            valid=isinstance(value,str) if kind in ('version','identifier') else (type(value) is bool or finite(value) and value in (0,1)) if kind=='boolean' else finite(value) and value>=0 and int(value)==value if kind=='candles' else finite(value)
            if valid and key in ('atr','prev_atr','candle_range','natr_pct','bb_width_fraction','realized_volatility'):valid=value>=0
            if valid and key=='prev_close':valid=value>0
            if valid and kind=='percentile_0_100':valid=0<=value<=100
            if not valid:value=None;invalid=True;flags.append('INVALID_INPUT:'+key)
            elif kind=='boolean':value=bool(value)
            elif kind=='candles':value=int(value)
        f[key]=value
    prices=[snapshot['candle'].get(key) for key in ('open','high','low','close')]
    raw=all(finite(v) and v>0 for v in prices);raw=raw and prices[1]>=max(prices) and prices[2]<=min(prices)
    parameters=snapshot.get('feature_parameters',{})
    compatible=all(parameters.get(key)==expected for key,expected in (('measurementRankLength',cfg.baseline_length),('measurementChangeLength',cfg.change_length),('measurementReturnLength',cfg.return_length)))
    if not compatible:flags.append('INCOMPATIBLE_FEATURE_PARAMETERS')
    calendar=snapshot.get('market_metadata',{}).get('calendar')
    if calendar!='24/7 UTC':flags.append('UNSUPPORTED_MARKET_CALENDAR')
    gap=state['last_close'] is not None and start!=state['last_close']+1 or f['measurement_gap'] is True
    if gap:state['dimensions']={};state['last_shock']=None;flags.append('CANDLE_GAP')
    shared=f['measurement_version']=='shared-v1' and bool(f['measurement_config_id'])
    if not shared:flags.append('SHARED_FEATURES_UNAVAILABLE')
    usable=raw and compatible and shared and calendar=='24/7 UTC' and not gap
    flat=usable and f['natr_pct']==0 and f['bb_width_fraction']==0 and f['realized_volatility']==0 and f['zero_price_movement'] is True and f['measurement_contiguous_bars'] is not None and f['measurement_contiguous_bars']>=cfg.return_length+1
    if flat:flags.append('ZERO_MOVEMENT_OVERRIDE')
    rank_ok=usable and f['natr_pct'] is not None and f['natr_percentile'] is not None and f['natr_baseline_count'] is not None and f['natr_baseline_count']>=cfg.baseline_length and type(f['natr_baseline_degenerate']) is bool
    bbw_ok=usable and f['bb_width_fraction'] is not None and f['bb_width_percentile'] is not None and f['bb_width_baseline_count'] is not None and f['bb_width_baseline_count']>=cfg.baseline_length and type(f['bb_width_baseline_degenerate']) is bool
    if rank_ok and f['natr_baseline_degenerate']:flags.append('DEGENERATE_NATR_BASELINE')
    if bbw_ok and f['bb_width_baseline_degenerate']:flags.append('DEGENERATE_BBW_BASELINE')
    proposals=dict(level='EXTREMELY_LOW' if flat else level(f['natr_percentile']) if rank_ok else None,state=None,distribution=None,shock=None)
    change_ok=usable and f['natr_change_fraction'] is not None and f['bb_width_change_fraction'] is not None
    if flat:proposals['state']='STABLE'
    elif change_ok:
        a,b=f['natr_change_fraction'],f['bb_width_change_fraction'];d=cfg.change_deadband
        proposals['state']='EXPANDING' if a>=d and b>=d else 'CONTRACTING' if a<=-d and b<=-d else 'STABLE' if abs(a)<d and abs(b)<d else None
        if proposals['state'] is None:flags.append('VOLATILITY_CHANGE_DISAGREEMENT')
    distribution_ok=usable and f['realized_volatility'] is not None and f['realized_volatility']>0 and f['return_skewness'] is not None and f['measurement_contiguous_bars'] is not None and f['measurement_contiguous_bars']>=cfg.return_length+1
    if distribution_ok:proposals['distribution']='SKEWED' if abs(f['return_skewness'])>=cfg.skew_threshold else 'SYMMETRIC'
    elif usable and f['realized_volatility']==0:flags.append('DEGENERATE_RETURN_WINDOW')
    atr_length=parameters.get('atrLen')
    shock_baseline_ready=type(atr_length) is int and atr_length>0 and f['measurement_contiguous_bars'] is not None and f['measurement_contiguous_bars']>=atr_length+1
    if usable and not shock_baseline_ready:flags.append('SHOCK_BASELINE_WARMUP')
    ratio=None;shock_ok=usable and shock_baseline_ready and f['prev_atr'] is not None and f['prev_close'] is not None and f['candle_range'] is not None
    if shock_ok:
        movement=max(f['candle_range'],abs(prices[0]-f['prev_close']))
        if f['prev_atr']>0:
            ratio=movement/f['prev_atr']
            if not finite(ratio):ratio=None;shock_ok=False;flags.append('SHOCK_RATIO_OVERFLOW')
        elif movement==0:ratio=0.
        else:shock_ok=False;flags.append('ZERO_SHOCK_BASELINE')
        if ratio is not None:proposals['shock']='EXTREME' if ratio>=cfg.extreme_shock_atr else 'MODERATE' if ratio>=cfg.moderate_shock_atr else 'NONE'
    if usable and not (rank_ok or flat):flags.append('LEVEL_INPUTS_UNAVAILABLE')
    if usable and not (bbw_ok or flat):flags.append('BBW_BASELINE_UNAVAILABLE')
    if usable and not (change_ok or flat):flags.append('CHANGE_INPUTS_UNAVAILABLE')
    if usable and not distribution_ok:flags.append('RETURN_DISTRIBUTION_UNAVAILABLE')
    if usable and not shock_ok:flags.append('SHOCK_INPUTS_UNAVAILABLE')
    statuses={};classification={}
    for key,proposal in proposals.items():
        bars=cfg.shock_confirmation_bars if key=='shock' else cfg.confirmation_bars;item=state['dimensions'].setdefault(key,{})
        if closed:status,count=confirm(item,proposal,bars)
        else:status,count=('UNAVAILABLE',0) if proposal is None else ('CONFIRMED',bars) if item.get('confirmed')==proposal else ('PENDING',item.get('count',0) if item.get('candidate')==proposal else 0)
        statuses[key]=dict(status=status,candidate_bars=count,required_bars=bars);classification[key]=item.get('confirmed') or 'UNKNOWN'
    coverage=.3*(rank_ok or flat)+.1*(bbw_ok or flat)+.25*(change_ok or flat)+.15*distribution_ok+.2*shock_ok
    progress=lambda key:statuses[key]['candidate_bars']/statuses[key]['required_bars']
    bbw_agreement=1. if flat else max(0,1-.5*abs(LEVELS.index(proposals['level'])-LEVELS.index(level(f['bb_width_percentile'])))) if rank_ok and bbw_ok else 0.
    if rank_ok and bbw_ok and bbw_agreement==0:flags.append('CONFLICTING_LEVEL_MEASURES')
    contributions=dict(natr_level=.3*progress('level')*(.5 if not flat and f['natr_baseline_degenerate'] is True else 1) if rank_ok or flat else 0.,
        bbw_level=.1*progress('level')*bbw_agreement*(.5 if not flat and f['bb_width_baseline_degenerate'] is True else 1) if bbw_ok or flat else 0.,
        change=.25*progress('state') if proposals['state'] else 0.,distribution=.15*progress('distribution') if proposals['distribution'] else 0.,shock=.2*progress('shock') if proposals['shock'] else 0.)
    events=[]
    if closed and classification['shock'] in ('MODERATE','EXTREME') and classification['shock']!=old['shock']:
        event=dict(type='SHOCK_TRANSITION',severity=classification['shock'],origin_time=start,known_time=end+1,ratio=ratio)
        event['id']=hashlib.sha256(json.dumps([identity,cfg.fingerprint,signature,event],sort_keys=True,allow_nan=False).encode()).hexdigest();state['last_shock']=event;events.append(event)
    quality='GAP' if gap else 'INVALID' if invalid or not raw else 'VALID' if coverage>=1-1e-12 else 'PARTIAL' if coverage>0 else 'WARMUP'
    if snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION':flags.append('AVAILABILITY_RECONSTRUCTED')
    result=dict(contract_version='1.0.0',engine='VOLATILITY',engine_version=VERSION,state_schema_version=VERSION,identity=identity,candle_open_time=start,candle_close_time=end,as_of=known,computed_at=computed,available_at=computed if closed else None,mode='CONFIRMED' if closed else 'PROVISIONAL',
        classification=classification if closed else old,candidate_classification={key:value or 'UNKNOWN' for key,value in proposals.items()},strength=0. if flat else f['natr_percentile'] if rank_ok else None,confidence=round(sum(contributions.values()),8),coverage=round(coverage,8),data_quality=quality,quality_flags=sorted(set(flags)),
        measurements={**f,'shock_range_or_gap_atr':ratio,'evidence_contributions':contributions,'dimension_confirmation':statuses,'new_events':events,'last_shock':deepcopy(state['last_shock'])},confirmation=statuses['level'],previous_state=dict(classification=old),evidence=[dict(code='INDEPENDENT_VOLATILITY_DIMENSIONS',inputs=list(FIELDS),description='Relative level, change, return skewness and prior-ATR shock are separate; no directional vote or win probability.')],config_hash=cfg.fingerprint,input_signature=signature,provenance=dict(mode=snapshot['provenance_mode'],source_versions=deepcopy(snapshot['source_versions']),dependency_results=[]))
    state.update(last_open=start,last_close=end)
    return result,state if closed else deepcopy(previous_state)
