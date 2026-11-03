"""Pure aggregation of one public engine family; no indicators or classifiers."""
from copy import deepcopy
import hashlib
import itertools
import json
import math
from .aggregation_config import AggregationConfig

VERSION='1.0.0'


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def fraction(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and 0<=v<=1


def evaluate(snapshot,config=None):
    cfg=config or AggregationConfig()
    if not isinstance(cfg,AggregationConfig):raise TypeError('Use AggregationConfig')
    identity=deepcopy(snapshot['identity']);engine=snapshot['engine'];at=snapshot['as_of'];computed=snapshot['computed_at']
    if set(identity)!={'venue','market_type','instrument_id','symbol','dataset_generation'} or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Complete aggregation identity required')
    if not isinstance(engine,str) or not engine:raise ValueError('Engine family required')
    if type(at) is not int or type(computed) is not int or not 0<=at<=computed:raise ValueError('Invalid aggregation times')
    slots=deepcopy(snapshot['timeframes'])
    if not isinstance(slots,list) or len({s['timeframe'] for s in slots})!=len(slots):raise ValueError('Distinct registered timeframes required')
    if not set(dict(cfg.timeframe_weights))<={slot['timeframe'] for slot in slots}:raise ValueError('Weight names must match registered timeframes')
    active=[];reports={};admitted=[];flags=[]
    for slot in slots:
        tf=slot['timeframe'];duration=slot['duration_ms'];enabled=slot['active']
        if not isinstance(tf,str) or not tf or type(duration) is not int or duration<=0 or type(enabled) is not bool:raise ValueError('Invalid timeframe descriptor')
        horizon='short' if duration<=cfg.short_max_ms else 'medium' if duration<=cfg.medium_max_ms else 'long'
        report=dict(horizon=horizon,active=enabled,reason='DISABLED' if not enabled else slot.get('reason'),result_ref=slot.get('result_ref'),classification=None,coverage=0.,confidence=0.,scope=None)
        reports[tf]=report
        if not enabled:continue
        active.append((tf,horizon,dict(cfg.timeframe_weights).get(tf,1.)))
        result=slot.get('result');expected=slot.get('expected',{})
        if report['reason']:continue
        if not isinstance(result,dict):report['reason']='MISSING';continue
        report.update(classification=deepcopy(result.get('classification')),scope=deepcopy(slot.get('scope')))
        bound=all(isinstance(expected.get(k),str) and expected[k] and result.get(k)==expected[k] for k in ('engine_version','config_hash','input_signature'))
        source_identity=result.get('identity',{})
        match=all(source_identity.get(k)==identity[k] for k in ('venue','market_type','instrument_id','symbol')) and source_identity.get('timeframe')==tf and source_identity.get('dataset_generation')==expected.get('dataset_generation')
        if not bound or not match or result.get('engine')!=engine or result.get('contract_version')!='1.0.0':report['reason']='INCOMPATIBLE_IDENTITY_OR_VERSION';continue
        start,end,known,available=(result.get(k) for k in ('candle_open_time','candle_close_time','as_of','available_at'))
        if any(type(v) is not int or v<0 for v in (start,end,known,available)) or not start<=end<known or available<known:report['reason']='INVALID_SOURCE_TIMES';continue
        if known>at or cfg.availability=='ACTUAL' and available>at:report['reason']='NOT_YET_AVAILABLE';continue
        fresh_until=slot.get('fresh_until')
        if type(fresh_until) is not int or fresh_until<=end or at>fresh_until:report['reason']='STALE';continue
        classification=result.get('classification');confirmation=result.get('confirmation',{}).get('status')
        if result.get('mode')!='CONFIRMED' or result.get('data_quality') not in ('VALID','PARTIAL') or confirmation not in (('CONFIRMED','PENDING') if cfg.allow_pending else ('CONFIRMED',)):
            report['reason']='UNCONFIRMED_OR_UNUSABLE';continue
        if not isinstance(classification,dict) or not classification or any(not isinstance(k,str) or not isinstance(v,str) for k,v in classification.items()):report['reason']='INVALID_CLASSIFICATION';continue
        if not fraction(result.get('coverage')) or not fraction(result.get('confidence')) or result['coverage']<=0 or result['confidence']>result['coverage']+1e-8:report['reason']='INVALID_EVIDENCE';continue
        if not isinstance(slot.get('result_ref'),str) or not slot['result_ref']:report['reason']='MISSING_REFERENCE';continue
        report.update(reason=None,coverage=result['coverage'],confidence=result['confidence'],known_time=known,available_at=available,age_ms=at-known)
        admitted.append((tf,horizon,result))
        if result.get('provenance',{}).get('mode')=='HISTORICAL_RECONSTRUCTION':flags.append('RECONSTRUCTED_SOURCE_HISTORY')
    # An explicit family/config cohort is mandatory, not the newest arbitrary run.
    cohorts={(r['engine_version'],r['config_hash']) for _,_,r in admitted}
    if len(cohorts)>1:
        for tf,_,_ in admitted:reports[tf]['reason']='INCOMPATIBLE_CONFIG_COHORT'
        admitted=[];flags.append('INCOMPATIBLE_CONFIG_COHORT')
    horizon_budget={};weights={};configured_groups={group for _,group,_ in active};hw=dict(cfg.horizon_weights)
    budget_total=sum(hw[group] for group in configured_groups)
    for group in configured_groups:
        horizon_budget[group]=hw[group]/budget_total
        group_total=sum(w for _,g,w in active if g==group)
        for tf,g,w in active:
            if g==group:weights[tf]=horizon_budget[group]*w/group_total
    coverage=sum(weights[tf]*result['coverage'] for tf,_,result in admitted)
    confidence=sum(weights[tf]*result['confidence'] for tf,_,result in admitted)
    summaries={};conflicts=[]
    for group in ('short','medium','long'):
        members=[(tf,r) for tf,g,r in admitted if g==group];dimensions={}
        for key in sorted({k for _,r in members for k in r['classification']}):
            support={}
            for tf,r in members:
                value=r['classification'].get(key,'UNKNOWN')
                if value=='UNKNOWN':continue
                support[value]=support.get(value,0.)+weights[tf]*r['coverage']/horizon_budget[group]
            winning=[value for value,share in support.items() if share>=cfg.consensus_share]
            dimensions[key]=dict(state=winning[0] if len(winning)==1 else 'MIXED' if len(support)>1 else 'UNKNOWN',support={k:round(v,8) for k,v in support.items()})
        summaries[group]=dict(configured=group in configured_groups,budget=horizon_budget.get(group,0.),coverage=round(sum(weights[tf]*r['coverage'] for tf,r in members)/horizon_budget[group],8) if group in configured_groups else 0.,timeframes=[tf for tf,_ in members],dimensions=dimensions)
    for (tf1,g1,r1),(tf2,g2,r2) in itertools.combinations(admitted,2):
        for dimension in sorted(r1['classification'].keys() & r2['classification'].keys()):
            a,b=r1['classification'][dimension],r2['classification'][dimension]
            if a=='UNKNOWN' or b=='UNKNOWN' or a==b:continue
            directional=dimension=='direction' and {a,b}=={'BULLISH','BEARISH'}
            conflict=dict(dimension=dimension,type='COUNTERTREND' if directional and g1!=g2 else 'DIRECTIONAL_OPPOSITION' if directional else 'STATE_DISAGREEMENT',
                timeframes=[tf1,tf2],states=[a,b],horizons=[g1,g2],known_times=[r1['as_of'],r2['as_of']])
            if directional:
                ordered=sorted((tf1,tf2),key=lambda tf:next(s['duration_ms'] for s in slots if s['timeframe']==tf))
                conflict.update(shorter_timeframe=ordered[0],longer_timeframe=ordered[1])
            conflicts.append(conflict)
    directional=any(c['type'] in ('COUNTERTREND','DIRECTIONAL_OPPOSITION') for c in conflicts)
    incomplete=len(admitted)!=len(active)
    known_members=sum(any(v!='UNKNOWN' for v in r['classification'].values()) for _,_,r in admitted)
    if coverage<cfg.minimum_coverage or known_members<2:alignment='UNKNOWN'
    elif directional:alignment='CONFLICTED'
    elif conflicts or incomplete:alignment='PARTIALLY_ALIGNED'
    else:alignment='ALIGNED'
    if len(admitted)<2:flags.append('INSUFFICIENT_TIMEFRAMES')
    elif known_members<2:flags.append('INSUFFICIENT_KNOWN_STATES')
    if coverage<cfg.minimum_coverage:flags.append('INSUFFICIENT_FULL_SCOPE_COVERAGE')
    if cfg.availability=='RECONSTRUCTED_CLOSE':flags.append('SIMULATED_CLOSE_AVAILABILITY_NOT_ORIGINAL_PUBLICATION')
    # Time age itself does not create new history every timer tick. References,
    # exclusions, scope and policy changes do; the requested as_of stays explicit.
    signature=digest(dict(identity=identity,engine=engine,policy=cfg.fingerprint,slots=[{k:v for k,v in reports[s['timeframe']].items() if k!='age_ms'} for s in slots],producer=snapshot.get('producer_generation')))
    return dict(contract_version='1.0.0',aggregator_version=VERSION,identity=identity,engine=engine,as_of=at,computed_at=computed,available_at=computed,
        availability_policy=cfg.availability,alignment=alignment,coverage=round(coverage,8),confidence=round(confidence,8),data_quality='VALID' if admitted and not incomplete and coverage>=1-1e-12 else 'PARTIAL' if admitted else 'WARMUP',
        timeframes=reports,horizons=summaries,conflicts=conflicts,result_refs=[reports[tf]['result_ref'] for tf,_,_ in admitted],weights=weights,
        quality_flags=sorted(set(flags)),config_hash=cfg.fingerprint,input_signature=signature,
        interpretation='Per-family categorical alignment, not a BUY/SELL decision, probability or averaged directional prediction.')
