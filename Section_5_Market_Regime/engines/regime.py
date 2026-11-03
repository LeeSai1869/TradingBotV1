"""Regime v1: pure one-pair interpretations of timestamped Section 4 inputs."""
from copy import deepcopy
import math
from ..config import RegimeConfig

VERSION='1.0.0'
FIELDS=('adx','di_plus','di_minus','di_signed_dominance','efficiency_ratio',
    'natr_pct','natr_percentile','natr_baseline_count','natr_baseline_degenerate',
    'bb_width_percentile','natr_change_fraction','bb_width_change_fraction',
    'zero_price_movement','directional_movement_zero','measurement_gap',
    'measurement_contiguous_bars','measurement_version','measurement_config_id')
UNITS={key:'dimensionless' for key in FIELDS}
UNITS.update(adx='index_0_100',di_plus='index_0_100',di_minus='index_0_100',
    natr_pct='percent',natr_percentile='percentile_0_100',bb_width_percentile='percentile_0_100',
    natr_baseline_count='candles',measurement_contiguous_bars='candles',
    measurement_version='version',measurement_config_id='identifier')
for _field in ('natr_baseline_degenerate','zero_price_movement','directional_movement_zero','measurement_gap'):UNITS[_field]='boolean'
BUDGET={'adx':.20,'efficiency_ratio':.20,'di_signed_dominance':.15,'di_plus':.05,'di_minus':.05}


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def confirm(item,proposal,required):
    if proposal is None:
        item.update(confirmed=None,candidate=None,count=0)
        return 'UNAVAILABLE',0
    if item.get('confirmed')==proposal:
        item.update(candidate=None,count=0)
        return 'CONFIRMED',required
    count=item.get('count',0)+1 if item.get('candidate')==proposal else 1
    item.update(candidate=proposal,count=count)
    if count>=required:
        item.update(confirmed=proposal,candidate=None,count=0)
        return 'CONFIRMED',required
    return 'PENDING',count


def labels(dimensions):
    primary=dimensions.get('primary',{}).get('confirmed') or ['UNKNOWN','UNKNOWN']
    return dict(primary=primary[0],direction=primary[1],
        volatility_level=dimensions.get('level',{}).get('confirmed') or 'UNKNOWN',
        volatility_change=dimensions.get('change',{}).get('confirmed') or 'UNKNOWN',
        stability='UNKNOWN' if primary[0]=='UNKNOWN' else 'TRANSITIONING' if dimensions.get('primary',{}).get('candidate') else 'STABLE')


def evaluate(snapshot,config=None,previous_state=None):
    """Return (result, new state). Preview never advances committed state.

    Inputs and previous_state are never mutated. Core must persist confirmed
    records/checkpoints atomically and preserve the minimal input bundle.
    """
    cfg=config or RegimeConfig()
    if not isinstance(cfg,RegimeConfig):raise TypeError('Use a validated RegimeConfig')
    identity=deepcopy(snapshot['identity'])
    required={'venue','market_type','instrument_id','symbol','timeframe','dataset_generation'}
    if set(identity)!=required or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Complete source identity required')
    start,end,as_of,computed=(snapshot[k] for k in ('candle_open_time','candle_close_time','as_of','computed_at'))
    if any(type(t) is not int or t<0 for t in (start,end,as_of,computed)) or end<start or computed<as_of:raise ValueError('Invalid snapshot time ordering')
    closed=snapshot['closed']
    if type(closed) is not bool or closed and as_of<=end or not closed and as_of<start:raise ValueError('Invalid candle availability')
    signature=snapshot['input_signature']
    if not isinstance(signature,str) or not signature:raise ValueError('Input signature required')
    binding=dict(identity=identity,config_hash=cfg.fingerprint,input_signature=signature,state_schema_version=VERSION)
    state=deepcopy(previous_state) if previous_state else {**binding,'dimensions':{},'last_open':None,'last_close':None,'last_change':None}
    if any(state.get(k)!=v for k,v in binding.items()):raise ValueError('State belongs to another identity, configuration or source generation')
    if state['last_open'] is not None and start<=state['last_open']:raise ValueError('Regime candles must be strictly chronological')
    old=labels(state['dimensions']);old_change=state['last_change']
    flags=list(snapshot.get('quality_flags',[]));features=snapshot['features'];known=snapshot['field_available_at']
    values={};invalid=False
    ranges={'adx':(0,100),'di_plus':(0,100),'di_minus':(0,100),'di_signed_dominance':(-1,1),
        'efficiency_ratio':(0,1),'natr_pct':(0,float('inf')),'natr_percentile':(0,100),'bb_width_percentile':(0,100)}
    for key in FIELDS:
        value=features.get(key);available=known.get(key)
        if value is not None and snapshot.get('field_validity',{}).get(key)!='VALID':
            flags.append('INPUT_UNAVAILABLE:'+key);value=None
        if value is not None and (type(available) is not int or available<0 or available>as_of):
            flags.append('INPUT_NOT_AVAILABLE:'+key);value=None
        if value is not None and snapshot.get('units',{}).get(key)!=UNITS[key]:
            flags.append('UNIT_MISMATCH:'+key);value=None;invalid=True
        if isinstance(value,float) and not math.isfinite(value):flags.append('INVALID_INPUT:'+key);value=None;invalid=True
        if key in ranges and value is not None and (not finite(value) or not ranges[key][0]<=value<=ranges[key][1]):
            flags.append('INVALID_INPUT:'+key);value=None;invalid=True
        kind='bool' if UNITS[key]=='boolean' else 'int' if UNITS[key]=='candles' else 'string' if UNITS[key] in ('version','identifier') else None
        if value is not None and ((kind=='bool' and type(value) is not bool) or (kind=='int' and (type(value) is not int or value<0)) or (kind=='string' and (not isinstance(value,str) or not value))):
            flags.append('INVALID_INPUT:'+key);value=None;invalid=True
        values[key]=value
    for key in ('natr_change_fraction','bb_width_change_fraction'):
        if values[key] is not None and not finite(values[key]):values[key]=None;flags.append('INVALID_INPUT:'+key);invalid=True
    candle=snapshot['candle'];prices=[candle.get(k) for k in ('open','high','low','close')]
    raw_valid=all(finite(v) and v>0 for v in prices)
    if raw_valid:raw_valid=prices[1]>=max(prices[0],prices[2],prices[3]) and prices[2]<=min(prices[0],prices[1],prices[3])
    gap=state['last_close'] is not None and start!=state['last_close']+1 or values.get('measurement_gap') is True
    if gap:flags.append('CANDLE_GAP');state['dimensions']={}
    if not raw_valid:flags.append('INVALID_OHLC');invalid=True
    supported=values['measurement_version']=='shared-v1' and isinstance(values['measurement_config_id'],str) and bool(values['measurement_config_id'])
    parameters=snapshot.get('feature_parameters',{})
    if any(parameters.get(key)!=expected for key,expected in (('measurementERLength',cfg.er_length),('measurementRankLength',cfg.baseline_length),('measurementChangeLength',cfg.change_length))):
        supported=False;flags.append('INCOMPATIBLE_FEATURE_PARAMETERS')
    if not supported:flags.append('SHARED_FEATURES_UNAVAILABLE')
    usable=raw_valid and supported and not gap
    valid_direction={key:usable and values[key] is not None for key in BUDGET}
    directional=all(valid_direction.values())
    d=values['di_signed_dominance'];adx=values['adx'];er=values['efficiency_ratio']
    prior=state['dimensions'].get('primary',{}).get('confirmed')
    proposal=None;rule='DIRECTIONAL_INPUTS_UNAVAILABLE'
    if directional:
        direction='BULLISH' if d>0 else 'BEARISH'
        if prior and prior[0]=='TRENDING' and prior[1]==direction and adx>=cfg.adx_trend_hold and er>=cfg.er_trend_hold and abs(d)>=cfg.dominance_hold:
            proposal=['TRENDING',direction];rule='TREND_HOLD'
        elif adx>=cfg.adx_trend_entry and er>=cfg.er_trend_entry and abs(d)>=cfg.dominance_entry:
            proposal=['TRENDING',direction];rule='TREND_ENTRY'
        elif adx<=cfg.adx_range_max and er<=cfg.er_range_max and abs(d)<=cfg.dominance_entry:
            proposal=['RANGING','NEUTRAL'];rule='RANGE_ENTRY'
        else:
            proposal=['TRANSITIONAL','NEUTRAL' if abs(d)<=cfg.dominance_entry else direction];rule='CONFLICTING_OR_DEVELOPING'
    baseline=values['natr_baseline_count'];degenerate=values['natr_baseline_degenerate']
    level_valid=usable and values['natr_pct'] is not None and values['natr_percentile'] is not None and type(baseline) is int and baseline>=cfg.baseline_length and type(degenerate) is bool
    level=None
    if level_valid:
        p=values['natr_percentile']
        level='EXTREMELY_LOW' if values['natr_pct']==0 and values['zero_price_movement'] is True else 'EXTREMELY_LOW' if p<10 else 'LOW' if p<25 else 'NORMAL' if p<75 else 'HIGH' if p<90 else 'EXTREME'
        if degenerate:flags.append('DEGENERATE_NATR_BASELINE')
    change_valid=usable and all(finite(values[k]) for k in ('natr_change_fraction','bb_width_change_fraction'))
    change=None
    if change_valid:
        a,b=values['natr_change_fraction'],values['bb_width_change_fraction'];limit=cfg.change_deadband
        change='EXPANDING' if a>=limit and b>=limit else 'CONTRACTING' if a<=-limit and b<=-limit else 'STABLE' if abs(a)<limit and abs(b)<limit else None
        if change is None:flags.append('VOLATILITY_CHANGE_DISAGREEMENT')
    if usable and not directional:flags.append('DIRECTIONAL_INPUTS_UNAVAILABLE')
    if usable and not level_valid:flags.append('VOLATILITY_BASELINE_UNAVAILABLE')
    if usable and not change_valid:flags.append('VOLATILITY_CHANGE_UNAVAILABLE')
    if values['directional_movement_zero'] is True:flags.append('DIRECTIONAL_MOVEMENT_ZERO')
    dimension_status={}
    for name,value,bars in (('primary',proposal,cfg.confirmation_bars),('level',level,cfg.volatility_confirmation_bars),('change',change,cfg.volatility_confirmation_bars)):
        item=state['dimensions'].setdefault(name,{})
        if closed:
            status,count=confirm(item,value,bars)
        else:
            status='UNAVAILABLE' if value is None else 'CONFIRMED' if item.get('confirmed')==value else 'PENDING'
            count=bars if status=='CONFIRMED' else item.get('count',0) if item.get('candidate')==value else 0
            if value is None:item.clear()
            elif item.get('confirmed')!=value:item['candidate']=value
        dimension_status[name]=dict(status=status,candidate_bars=count,required_bars=bars)
    confirmed=labels(state['dimensions'])
    candidate=dict(primary=proposal[0] if proposal else 'UNKNOWN',direction=proposal[1] if proposal else 'UNKNOWN',volatility_level=level or 'UNKNOWN',volatility_change=change or 'UNKNOWN',stability=confirmed['stability'])
    coverage=sum(weight for key,weight in BUDGET.items() if valid_direction[key])+.20*level_valid+.15*change_valid
    progress=lambda name:dimension_status[name]['candidate_bars']/dimension_status[name]['required_bars']
    scores=dict(primary=.65*progress('primary')*(.5 if proposal and proposal[0]=='TRANSITIONAL' else 1) if proposal else 0.,
        volatility_level=.20*progress('level')*(.5 if degenerate and values['natr_pct']!=0 else 1) if level else 0.,
        volatility_change=.15*progress('change') if change else 0.)
    confidence=sum(scores.values());strength=100*(min(adx/50,1)+er+abs(d))/3 if directional else None
    if any(confirmed[k]!=old[k] for k in ('primary','direction','volatility_level','volatility_change')):state['last_change']=as_of
    state.update(last_open=start,last_close=end)
    bars=values['measurement_contiguous_bars']
    warming=not supported or type(bars) is int and bars<cfg.er_length+1
    quality='GAP' if gap else 'INVALID' if invalid else 'VALID' if coverage>=1-1e-12 else 'WARMUP' if warming and not directional else 'PARTIAL'
    if quality=='WARMUP':flags.append('INSUFFICIENT_HISTORY')
    provenance_mode=snapshot['provenance_mode']
    if provenance_mode not in ('LIVE','HISTORICAL_RECONSTRUCTION','SIMULATION'):raise ValueError('Invalid provenance mode')
    if provenance_mode=='HISTORICAL_RECONSTRUCTION':flags.append('AVAILABILITY_RECONSTRUCTED')
    result=dict(contract_version=VERSION,engine='REGIME',engine_version=VERSION,state_schema_version=VERSION,
        identity=identity,candle_open_time=start,candle_close_time=end,as_of=as_of,computed_at=computed,
        available_at=computed if closed else None,mode='CONFIRMED' if closed else 'PROVISIONAL',
        classification=confirmed,candidate_classification=candidate,strength=strength,confidence=round(confidence,8),coverage=round(coverage,8),
        data_quality=quality,quality_flags=sorted(set(flags)),measurements={**values,'evidence_contributions':scores,'dimension_confirmation':dimension_status},
        confirmation=dimension_status['primary'],previous_state=dict(classification=old,last_change=old_change),
        evidence=[dict(code=rule,inputs=list(BUDGET),observed={key:values[key] for key in BUDGET},
            thresholds=dict(adx_entry=cfg.adx_trend_entry,adx_hold=cfg.adx_trend_hold,er_entry=cfg.er_trend_entry,er_hold=cfg.er_trend_hold,dominance_entry=cfg.dominance_entry,dominance_hold=cfg.dominance_hold)),
            dict(code='RULE_EVIDENCE_NOT_PROBABILITY',inputs=[],description='Fixed evidence budget; no BUY/SELL decision or prediction.')],
        config_hash=cfg.fingerprint,input_signature=signature,provenance=dict(mode=provenance_mode,source_versions=deepcopy(snapshot['source_versions']),dependency_results=[]))
    return result,state if closed else deepcopy(previous_state)
