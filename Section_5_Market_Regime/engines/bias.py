"""Same-timeframe public-output synthesis; never a decision or confidence engine."""
from copy import deepcopy
import hashlib
import json
import math
from .bias_config import BiasConfig

VERSION='1.0.0'
DEPENDENCIES={name:('1.1.0' if name in ('STRUCTURE','SENTIMENT') else '1.0.0') for name in ('REGIME','TREND','STRUCTURE','MOMENTUM','VOLATILITY','PHASE','PARTICIPATION','LIQUIDITY','SENTIMENT')}
FIELDS=('measurement_gap','measurement_version','measurement_config_id')
UNITS=dict(measurement_gap='boolean',measurement_version='version',measurement_config_id='identifier')
UNKNOWN=dict(direction='UNKNOWN',risk='UNKNOWN',alignment='UNKNOWN')


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def fraction(v):return finite(v) and 0<=v<=1


def admit(snapshot,name,flags):
    dep=snapshot.get('dependencies',{}).get(name);expected=snapshot.get('dependency_expectations',{}).get(name,{});ref=snapshot.get('dependency_refs',{}).get(name)
    if not isinstance(dep,dict):flags.append(name+'_UNAVAILABLE');return None
    bound=all(isinstance(expected.get(k),str) and expected[k] and dep.get(k)==expected[k] for k in ('engine_version','config_hash','input_signature'))
    known=dep.get('as_of');available=dep.get('available_at');end=snapshot['candle_close_time']
    reconstructed=snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION' and dep.get('provenance',{}).get('mode')=='HISTORICAL_RECONSTRUCTION'
    valid=(bound and dep.get('contract_version')=='1.0.0' and dep.get('engine')==name and dep.get('engine_version')==DEPENDENCIES[name]
        and dep.get('identity')==snapshot['identity'] and dep.get('candle_open_time')==snapshot['candle_open_time'] and dep.get('candle_close_time')==end
        and type(known) is int and end<known<=snapshot['as_of'] and type(available) is int and known<=available<=snapshot['computed_at']
        and (available<=snapshot['as_of'] or reconstructed) and dep.get('mode')=='CONFIRMED' and dep.get('data_quality') in ('VALID','PARTIAL')
        and fraction(dep.get('coverage')) and dep['coverage']>0 and fraction(dep.get('confidence')) and dep['confidence']<=dep['coverage']+1e-8
        and isinstance(dep.get('classification'),dict) and isinstance(ref,str) and bool(ref))
    if not valid:flags.append(name+'_DEPENDENCY_REJECTED');return None
    if reconstructed:flags.append('DEPENDENCY_AVAILABILITY_RECONSTRUCTED')
    return dep


def evaluate(snapshot,config=None,previous_state=None):
    cfg=config or BiasConfig()
    if not isinstance(cfg,BiasConfig):raise TypeError('Use BiasConfig')
    identity=deepcopy(snapshot['identity']);start,end,known,computed=(snapshot[k] for k in ('candle_open_time','candle_close_time','as_of','computed_at'))
    if set(identity)!={'venue','market_type','instrument_id','symbol','timeframe','dataset_generation'} or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Complete Bias identity required')
    if any(type(t) is not int or t<0 for t in (start,end,known,computed)) or end<start or computed<known:raise ValueError('Invalid Bias times')
    closed=snapshot['closed']
    if type(closed) is not bool or closed and known<=end or not closed and known<start:raise ValueError('Invalid candle availability')
    if snapshot['provenance_mode'] not in ('LIVE','SIMULATION','HISTORICAL_RECONSTRUCTION'):raise ValueError('Invalid provenance')
    if set(snapshot.get('dependencies',{}))-set(DEPENDENCIES):raise ValueError('Only same-timeframe base engines are admitted; no aggregated duplicate votes')
    signature=snapshot['input_signature']
    if not isinstance(signature,str) or not signature:raise ValueError('Bias signature required')
    binding=dict(identity=identity,config_hash=cfg.fingerprint,input_signature=signature,state_schema_version=VERSION)
    state=deepcopy(previous_state) if previous_state else dict(**binding,last_open=None,last_close=None,confirmed=None,candidate=None,count=0,classification=UNKNOWN.copy())
    if any(state.get(k)!=v for k,v in binding.items()):raise ValueError('Bias state identity/config/source mismatch')
    if state['last_open'] is not None and start<=state['last_open']:raise ValueError('Bias candles must be chronological')
    old=deepcopy(state['classification']);flags=[]
    gap=state['last_close'] is not None and start!=state['last_close']+1
    at=snapshot['field_available_at'].get('measurement_gap');value=snapshot['features'].get('measurement_gap')
    if snapshot['field_validity'].get('measurement_gap')=='VALID' and snapshot['units'].get('measurement_gap')=='boolean' and type(at) is int and 0<=at<=known and (type(value) is bool or finite(value) and value in (0,1)):gap=gap or bool(value)
    else:flags.append('SOURCE_CONTINUITY_UNAVAILABLE')
    if gap:state.update(confirmed=None,candidate=None,count=0);flags.append('CANDLE_GAP')
    deps={name:admit(snapshot,name,flags) for name in DEPENDENCIES} if closed and not gap else dict.fromkeys(DEPENDENCIES)
    classification=UNKNOWN.copy();points={};covered={};confident={};sources={};risks=[]
    sign=lambda direction:1 if direction=='BULLISH' else -1 if direction=='BEARISH' else 0 if direction=='NEUTRAL' else None
    def confirmed(dep):return dep and dep.get('confirmation',{}).get('status')=='CONFIRMED'
    for name in ('TREND','STRUCTURE','MOMENTUM'):
        dep=deps[name];score=None
        if confirmed(dep):
            direction=sign(dep['classification'].get('direction'))
            if direction is not None:
                if name=='STRUCTURE':score=float(direction) if dep['classification'].get('condition')=='CONFIRMED' else None
                elif finite(dep.get('strength')) and 0<=dep['strength']<=100:score=direction*dep['strength']/100
        sources[name]=dict(score=score,coverage=dep['coverage'] if dep and score is not None else 0.,confidence=dep['confidence'] if dep and score is not None else 0.)
    ts=cfg.trend_structure_weight
    for name,weight in (('TREND',ts*cfg.trend_share),('STRUCTURE',ts*(1-cfg.trend_share)),('MOMENTUM',cfg.momentum_weight)):
        item=sources[name];points[name]=weight*item['coverage']*item['score'] if item['score'] is not None else 0.;covered[name]=weight*item['coverage'];confident[name]=weight*item['confidence']
    liquid=deps['LIQUIDITY'];observed=liquid.get('measurements',{}).get('observed') if liquid else None
    flow=observed.get('flow_60s') if isinstance(observed,dict) else None
    contribution=liquid.get('measurements',{}).get('evidence_contributions',{}).get('flow') if liquid else None
    flow_score=flow.get('imbalance') if isinstance(flow,dict) else None
    observed_scope_ok=(isinstance(observed,dict) and isinstance(observed.get('scope'),dict) and observed['scope'].get('symbol')==identity['symbol']
        and observed['scope'].get('venue')==identity['venue'] and isinstance(observed.get('association'),dict)
        and (observed['scope'].get('market_type')==identity['market_type'] and observed['association'].get('kind')=='EXACT_MARKET'
             or identity['market_type']=='spot' and observed['scope'].get('market_type')=='usdt_perpetual' and observed['association'].get('kind')=='RELATED_PERPETUAL_CONTEXT' and finite(observed['association'].get('basis_bps'))))
    flow_ok=(observed_scope_ok and finite(contribution) and contribution>=.05 and finite(flow_score) and -1<=flow_score<=1)
    points['OBSERVED_FLOW']=cfg.observed_flow_weight*flow_score if flow_ok else 0.;covered['OBSERVED_FLOW']=cfg.observed_flow_weight if flow_ok else 0.;confident['OBSERVED_FLOW']=covered['OBSERVED_FLOW']
    sources['OBSERVED_FLOW']=dict(score=flow_score if flow_ok else None,scope=deepcopy(observed.get('scope')) if flow_ok else None)
    if flow_ok and observed['scope']['market_type']!=identity['market_type']:flags.append('RELATED_PERPETUAL_FLOW_NOT_SPOT_EXECUTION')
    phase=deps['PHASE'];phase_score=None
    if confirmed(phase) and phase['classification'].get('development')=='CONFIRMED':
        phase_score=1. if phase['classification'].get('phase') in ('MARKUP','ACCUMULATION','REACCUMULATION') else -1. if phase['classification'].get('phase') in ('MARKDOWN','DISTRIBUTION','REDISTRIBUTION') else None
    points['PHASE']=cfg.phase_weight*phase['coverage']*phase_score if phase_score is not None else 0.;covered['PHASE']=cfg.phase_weight*phase['coverage'] if phase_score is not None else 0.;confident['PHASE']=cfg.phase_weight*phase['confidence'] if phase_score is not None else 0.
    sources['PHASE']=dict(score=phase_score)
    # Current Sentiment v1 only has a derivatives funding proxy. It is never
    # promoted into an independent directional advantage by this synthesis.
    points['INDEPENDENT_SENTIMENT']=covered['INDEPENDENT_SENTIMENT']=confident['INDEPENDENT_SENTIMENT']=0.
    sources['INDEPENDENT_SENTIMENT']=dict(score=None,reason='No independent broad sentiment edge admitted in Bias v1')
    flags.append('FUNDING_TILT_IS_NOT_AN_INDEPENDENT_DIRECTIONAL_EDGE')
    score=sum(points.values());directional_coverage=sum(covered.values())
    family_count=sum(v>0 for v in (covered['TREND']+covered['STRUCTURE'],covered['MOMENTUM'],covered['OBSERVED_FLOW'],covered['PHASE']))
    ready=directional_coverage>=cfg.minimum_directional_coverage and family_count>=2
    proposal=None
    if ready:
        held=state['confirmed']
        proposal=held if held=='BULLISH' and score>=cfg.hold_deadband or held=='BEARISH' and score<=-cfg.hold_deadband else 'BULLISH' if score>=cfg.entry_deadband else 'BEARISH' if score<=-cfg.entry_deadband else 'NEUTRAL'
    if closed:
        if proposal is None:state.update(confirmed=None,candidate=None,count=0)
        elif proposal==state['confirmed']:state.update(candidate=None,count=0)
        else:
            state['count']=state['count']+1 if state['candidate']==proposal else 1;state['candidate']=proposal
            if state['count']>=cfg.confirmation_bars:state.update(confirmed=proposal,candidate=None,count=0)
    status='UNAVAILABLE' if proposal is None else 'CONFIRMED' if state['confirmed']==proposal else 'PENDING'
    count=cfg.confirmation_bars if status=='CONFIRMED' else state['count'] if state['candidate']==proposal else 0
    context_budget=dict(REGIME=.30,VOLATILITY=.30,PARTICIPATION=.20,LIQUIDITY=.10,SENTIMENT=.10)
    regime=deps['REGIME'];vol=deps['VOLATILITY'];part=deps['PARTICIPATION'];sent=deps['SENTIMENT']
    vol_confirmations=vol.get('measurements',{}).get('dimension_confirmation',{}) if vol else {}
    context_ready=dict(REGIME=bool(confirmed(regime) and regime['classification'].get('primary') in ('TRENDING','RANGING','TRANSITIONAL')),
        VOLATILITY=bool(vol and any(vol['classification'].get(dim) not in (None,'UNKNOWN') and (vol_confirmations.get(dim,{}).get('status')=='CONFIRMED' or confirmed(vol)) for dim in ('level','shock'))),
        PARTICIPATION=bool(confirmed(part) and part['classification'].get('activity') not in (None,'UNKNOWN')),
        LIQUIDITY=bool(observed_scope_ok and liquid['classification'].get('book_state') in ('DEEP','NORMAL','THIN','WITHDRAWING')),
        SENTIMENT=bool(sent and sent['classification'].get('risk') in ('MODERATE','HIGH','EXTREME')))
    context_covered={name:weight*deps[name]['coverage'] if context_ready[name] else 0. for name,weight in context_budget.items()}
    context_confident={name:weight*deps[name]['confidence'] if context_ready[name] else 0. for name,weight in context_budget.items()}
    if confirmed(regime) and (regime['classification'].get('primary')=='TRANSITIONAL' or regime['classification'].get('stability') in ('UNSTABLE','TRANSITIONING')):risks.append(('MODERATE','Regime transition'))
    if vol:
        confirmations=vol.get('measurements',{}).get('dimension_confirmation',{})
        available=lambda dim:confirmations.get(dim,{}).get('status')=='CONFIRMED' or confirmed(vol)
        shock=vol['classification'].get('shock') if available('shock') else None
        level=vol['classification'].get('level') if available('level') else None
        if shock=='EXTREME':risks.append(('EXTREME','Extreme volatility shock'))
        elif shock=='MODERATE':risks.append(('HIGH','Volatility shock'))
        elif level=='EXTREME':risks.append(('HIGH','Extreme volatility level'))
        elif level=='HIGH':risks.append(('MODERATE','High volatility level'))
    if confirmed(part) and part['classification'].get('activity') in ('VERY_LOW','LOW'):risks.append(('MODERATE','Low participation'))
    if liquid and liquid['classification'].get('book_state') in ('THIN','WITHDRAWING') and observed_scope_ok:risks.append(('HIGH','Observed execution liquidity '+liquid['classification']['book_state'].lower()))
    if sent and sent['classification'].get('risk') in ('MODERATE','HIGH','EXTREME'):risks.append((sent['classification']['risk'],'Observed derivatives risk'))
    if phase and phase['classification'].get('development')=='INVALIDATED':risks.append(('MODERATE','Phase hypothesis invalidated'))
    context_coverage=sum(context_covered.values());context_confidence=sum(context_confident.values())
    direction=state['confirmed'] or 'UNKNOWN'
    strong=abs(score)>=cfg.strong_threshold and context_coverage>=cfg.strong_context_min and direction==proposal and status=='CONFIRMED'
    label='STRONG_'+direction if strong and direction in ('BULLISH','BEARISH') else direction
    positive=sum(max(0,p) for p in points.values());negative=sum(max(0,-p) for p in points.values());magnitude=positive+negative
    agreement=abs(score)/magnitude if magnitude else 1. if ready else 0.
    alignment='UNKNOWN' if not ready else 'CONFLICTED' if min(positive,negative)>=cfg.conflict_min_points else 'PARTIALLY_ALIGNED' if positive and negative else 'ALIGNED'
    risk=max(risks,key=lambda item:{'MODERATE':1,'HIGH':2,'EXTREME':3}[item[0]])[0] if risks else 'UNKNOWN'
    classification=dict(direction=label,risk=risk,alignment=alignment)
    candidate_label=('STRONG_'+proposal if proposal in ('BULLISH','BEARISH') and abs(score)>=cfg.strong_threshold and context_coverage>=cfg.strong_context_min else proposal) or 'UNKNOWN'
    coverage=.8*directional_coverage+.2*context_coverage
    confidence=.8*sum(confident.values())*agreement*count/cfg.confirmation_bars+.2*context_confidence
    support=[name for name,p in points.items() if p*score>0];opposed=[name for name,p in points.items() if p*score<0]
    if not ready:flags.append('INSUFFICIENT_DIRECTIONAL_COVERAGE')
    if context_coverage<cfg.strong_context_min:flags.append('LIMITED_CONTEXT_COVERAGE')
    if not closed:classification=UNKNOWN.copy();flags.append('CLOSED_DEPENDENCIES_REQUIRED_FOR_PREVIEW')
    events=[]
    if closed and classification!=old and classification!=UNKNOWN:
        event=dict(type='BIAS_TRANSITION',classification=deepcopy(classification),origin_time=start,known_time=end+1)
        event['id']=hashlib.sha256(json.dumps([identity,cfg.fingerprint,signature,event],sort_keys=True,allow_nan=False).encode()).hexdigest();events.append(event)
    if snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION':flags.append('AVAILABILITY_RECONSTRUCTED')
    result=dict(contract_version='1.0.0',engine='BIAS',engine_version=VERSION,state_schema_version=VERSION,identity=identity,candle_open_time=start,candle_close_time=end,as_of=known,computed_at=computed,available_at=computed if closed else None,mode='CONFIRMED' if closed else 'PROVISIONAL',
        classification=classification if closed else old,candidate_classification=dict(classification,direction=candidate_label),strength=100*abs(score) if ready else None,coverage=round(coverage,8),confidence=round(min(coverage,confidence),8),
        data_quality='GAP' if gap else 'PARTIAL' if coverage>0 else 'WARMUP',quality_flags=sorted(set(flags)),
        measurements=dict(direction_score=score,directional_coverage=directional_coverage,context_coverage=context_coverage,directional_confidence=sum(confident.values()),context_confidence=context_confidence,agreement=agreement,contributions=points,coverage_contributions=covered,context_contributions=context_covered,source_scores=sources,
            supporting_sources=support,conflicting_sources=opposed,bullish_sources=[name for name,p in points.items() if p>0],bearish_sources=[name for name,p in points.items() if p<0],risk_reasons=[dict(level=level,reason=reason) for level,reason in risks],new_events=events,independent_sentiment_budget_reserved=cfg.independent_sentiment_weight),
        confirmation=dict(status=status,candidate_bars=count,required_bars=cfg.confirmation_bars),previous_state=dict(classification=old),evidence=[dict(code='CAPPED_SAME_TIMEFRAME_SYNTHESIS',inputs=list(DEPENDENCIES),description='Trend/Structure share a cap; Regime/Volatility are context, funding is not a directional edge. Strength/confidence are evidence scores, never a decision or win probability.')],
        config_hash=cfg.fingerprint,input_signature=signature,provenance=dict(mode=snapshot['provenance_mode'],source_versions=deepcopy(snapshot['source_versions']),dependency_results=[snapshot['dependency_refs'][name] for name,dep in deps.items() if dep]))
    state.update(last_open=start,last_close=end,classification=classification)
    return result,state if closed else deepcopy(previous_state)
