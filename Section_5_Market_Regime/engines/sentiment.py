"""Independent derivatives context and optional scored news/social evidence.

Raw thresholds are explicit experimental provider-period thresholds. Historical
normalization and crowding ratios are not fabricated; headlines are not scored here.
"""
from copy import deepcopy
import hashlib
import json
import math
from .sentiment_config import SentimentConfig

VERSION='1.1.0'
FIELDS=('measurement_gap','measurement_version','measurement_config_id')
UNITS=dict(measurement_gap='boolean',measurement_version='version',measurement_config_id='identifier')
UNKNOWN=dict(sentiment='UNKNOWN',positioning='UNKNOWN',stability='UNKNOWN',risk='UNKNOWN')
BUDGET=dict(funding=.15,funding_change=.05,open_interest=.10,reported_liquidations=.10,
            normalized_positioning=.10,account_ratios=.10,news=.20,crowd_social=.20)


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def fresh(t,at,age):return type(t) is int and t>=0 and 0<=at-t<=age


def context(snapshot,cfg):
    """Validate actual source publication/identity before interpreting fields."""
    flags=[];measurements=dict(scope='DERIVATIVES_FUNDING_TILT_ONLY',source=None,funding_rate=None,funding_change=None,
        open_interest=None,open_interest_change_pct=None,open_interest_window_ms=None,reported_liquidations=None,
        unavailable_sources=['NORMALIZED_POSITIONING','ACCOUNT_RATIOS','NEWS','CROWD_SOCIAL'])
    classification=UNKNOWN.copy();parts={key:0. for key in BUDGET}
    bundle=snapshot.get('sentiment_sources')
    if not isinstance(bundle,dict) or bundle.get('version') not in ('sentiment-projection-v1','sentiment-projection-v2') or bundle.get('status')!='RECORDED':
        return classification,parts,measurements,['SENTIMENT_SOURCES_UNAVAILABLE']
    sample=bundle.get('current');base=bundle.get('baseline');identity=snapshot['identity'];at=snapshot['as_of'];age=cfg.sample_max_age_ms
    source_ok=lambda s:isinstance(s,dict) and s.get('venue')==identity['venue']=='binance' and s.get('market')=='usdt_perpetual' and s.get('symbol')==identity['symbol']==identity['instrument_id'] and s.get('quote')=='USDT' and s.get('observed') is True
    if not source_ok(sample):return classification,parts,measurements,['SOURCE_IDENTITY_REJECTED']
    available,sampled=sample.get('available_ms'),sample.get('sampled_ms');gap=bundle.get('last_gap_ms')
    if not fresh(available,at,age) or not fresh(sampled,at,age) or sampled>available:return classification,parts,measurements,['SOURCE_STALE_OR_FUTURE']
    if gap is not None and (type(gap) is not int or not 0<=gap<=at or gap>=sampled):return classification,parts,measurements,['SOURCE_GAP_OR_INVALID_GAP']
    no_gap=lambda t:gap is None or type(t) is int and gap<t
    association=bundle.get('association')
    if not isinstance(association,dict):return classification,parts,measurements,['SOURCE_ASSOCIATION_UNAVAILABLE']
    if identity['market_type']=='usdt_perpetual' and association.get('kind')=='EXACT_MARKET':link=dict(kind='EXACT_MARKET')
    elif identity['market_type']=='spot' and association.get('kind')=='RELATED_PERPETUAL_CONTEXT':
        mid=sample.get('mid');close=snapshot['candle']['close'];ex=sample.get('exchange_ms');received=sample.get('book_received_ms')
        basis=(mid/close-1)*10000 if finite(mid) and mid>0 else None
        good=(finite(basis) and finite(association.get('basis_bps')) and abs(basis-association['basis_bps'])<1e-7 and abs(basis)<=cfg.max_cross_market_basis_bps
            and association.get('spot_close')==close and association.get('spot_close_time')==snapshot['candle_close_time'] and association.get('perpetual_mid')==mid
            and fresh(ex,at,age) and fresh(received,at,age) and ex<=received<=sampled and no_gap(received) and type(sample.get('sequence')) is int and sample['sequence']>0)
        if not good:return classification,parts,measurements,['CROSS_MARKET_ASSOCIATION_REJECTED']
        link=dict(kind='RELATED_PERPETUAL_CONTEXT',basis_bps=basis);flags.append('PERPETUAL_POSITIONING_CONTEXT_NOT_SPOT_SENTIMENT')
    else:return classification,parts,measurements,['SOURCE_ASSOCIATION_REJECTED']
    measurements['source']=dict(venue=sample['venue'],market_type=sample['market'],symbol=sample['symbol'],sampled_ms=sampled,available_ms=available,association=link)
    c=sample.get('context',{});bc=base.get('context',{}) if source_ok(base) else {}
    def funding(s,limit_at):
        if not source_ok(s) or not fresh(s.get('available_ms'),limit_at,age) or not fresh(s.get('sampled_ms'),limit_at,age) or s['sampled_ms']>s['available_ms']:return None
        values=s.get('context',{});rate=values.get('funding_rate');ex=values.get('mark_exchange_ms');rx=values.get('mark_received_ms')
        if (finite(rate) and all(finite(values.get(k)) and values[k]>0 for k in ('mark_price','index_price'))
            and fresh(ex,s['sampled_ms'],age) and fresh(rx,s['sampled_ms'],age) and ex<=rx and no_gap(ex)):
            return rate
        return None
    rate=funding(sample,at);baseline_rate=funding(base,at-300000)
    if rate is not None:
        parts['funding']=BUDGET['funding'];measurements['funding_rate']=rate
        classification['sentiment']='BULLISH' if rate>=cfg.funding_neutral_fraction else 'BEARISH' if rate<=-cfg.funding_neutral_fraction else 'NEUTRAL'
        if baseline_rate is not None:
            interval=c['mark_exchange_ms']-bc['mark_exchange_ms']
            delta=rate-baseline_rate
            if 280000<=interval<=320000 and finite(delta):
                parts['funding_change']=BUDGET['funding_change'];measurements['funding_change']=dict(delta_fraction=delta,window_ms=interval,baseline_rate=baseline_rate)
                classification['stability']='RAPIDLY_CHANGING' if abs(delta)>=cfg.funding_rapid_change_fraction else 'IMPROVING' if delta>=cfg.funding_change_fraction else 'DETERIORATING' if delta<=-cfg.funding_change_fraction else 'STABLE'
    else:flags.append('FUNDING_UNAVAILABLE')
    oi=c.get('open_interest');ex=c.get('open_interest_exchange_ms');rx=c.get('open_interest_received_ms')
    oi_valid=(finite(oi) and oi>=0 and fresh(ex,sampled,cfg.context_max_age_ms) and fresh(rx,sampled,cfg.context_max_age_ms) and ex<=rx and no_gap(ex))
    if oi_valid:
        measurements['open_interest']=oi
        boi=bc.get('open_interest');bt=bc.get('open_interest_exchange_ms');br=bc.get('open_interest_received_ms');ba=base.get('available_ms') if source_ok(base) else None
        base_ok=(source_ok(base) and fresh(ba,at-300000,age) and finite(boi) and boi>0 and fresh(bt,ba,cfg.context_max_age_ms) and fresh(br,ba,cfg.context_max_age_ms) and bt<=br and no_gap(bt) and 180000<=ex-bt<=420000)
        if base_ok:
            change=(oi/boi-1)*100
            if finite(change):parts['open_interest']=BUDGET['open_interest'];measurements.update(open_interest_change_pct=change,open_interest_window_ms=ex-bt)
    if not parts['open_interest']:flags.append('OI_CHANGE_UNAVAILABLE')
    start=sample.get('window_start_ms');long,short=(sample.get(k) for k in ('reported_long_liquidations_usdt','reported_short_liquidations_usdt'))
    label=sample.get('liquidation_coverage')
    if type(start) is int and start>=0 and 0<sampled-start<=age and no_gap(start) and all(finite(v) and v>=0 for v in (long,short)) and isinstance(label,str) and label.startswith('sampled exchange'):
        total=long+short;speed=total/((sampled-start)/1000)
        if finite(total) and finite(speed):
            parts['reported_liquidations']=BUDGET['reported_liquidations']
            measurements['reported_liquidations']=dict(long_usdt=long,short_usdt=short,reported_usdt_per_second=speed,window_start_ms=start,window_end_ms=sampled,coverage='SAMPLED_REPORTS_NOT_ALL_LIQUIDATIONS')
            if speed>=cfg.extreme_liquidations_usdt_per_second:classification['risk']='EXTREME'
            elif speed>=cfg.high_liquidations_usdt_per_second:classification['risk']='HIGH'
    change=measurements['open_interest_change_pct']
    if classification['risk']=='UNKNOWN' and rate is not None and change is not None and change>=cfg.leverage_build_pct and abs(rate)>=cfg.leverage_funding_fraction:
        classification['risk']='MODERATE'
    flags.extend(['SINGLE_VENUE_DERIVATIVES_PROXY','BROAD_SENTIMENT_AND_CROWDING_UNAVAILABLE','FUNDING_NOT_NORMALIZED_TO_FIXED_INTERVAL'])
    return classification,parts,measurements,flags



def external_context(snapshot,cfg):
    bundle=snapshot.get('sentiment_sources')
    if bundle is None:return None,{},dict(),[]
    if not isinstance(bundle,dict):return None,{},dict(),['EXTERNAL_SCHEMA_REJECTED']
    rows=bundle.get('external',[])
    flags=['EXTERNAL_SOURCE_MEMORY_UNAVAILABLE'] if bundle.get('external_error') else [];valid=[];seen=set();at=snapshot['as_of'];asset=snapshot['identity']['instrument_id']
    if not isinstance(rows,list) or len(rows)>20:return None,{},dict(),['EXTERNAL_SCHEMA_REJECTED']
    for row in rows:
        if not isinstance(row,dict):flags.append('EXTERNAL_SCHEMA_REJECTED');continue
        identifier=row.get('provider_id');category=row.get('category');score=row.get('score');published=row.get('published_ms');received=row.get('received_ms');known=row.get('profile_known_ms');quality=row.get('reliability')
        valid_times=all(type(t) is int and t>=0 for t in (published,received,known)) and known<=at and received<=at and published<=received
        allowed=(row.get('version')=='external-sentiment-v1' and category in ('NEWS','SOCIAL') and isinstance(identifier,str) and identifier and identifier not in seen
            and isinstance(row.get('publisher_group'),str) and row['publisher_group'] and row.get('asset') in (asset,'*') and valid_times
            and finite(quality) and 0<quality<=1 and row.get('kind')=='AGGREGATE_SENTIMENT' and finite(score) and -1<=score<=1
            and all(isinstance(row.get(k),str) and row[k] for k in ('method','terms_url','revision','event_id','profile_revision')))
        if not allowed:flags.append('EXTERNAL_UNSCORED_OR_INVALID');continue
        ttl=cfg.news_ttl_ms if category=='NEWS' else cfg.social_ttl_ms
        if at-published>ttl:flags.append('EXTERNAL_STALE:'+identifier);continue
        seen.add(identifier);item=dict(row);item['effective_quality']=quality*(cfg.market_wide_factor if row['asset']=='*' else 1.)
        if item['effective_quality']<=0:flags.append('EXTERNAL_QUALITY_UNAVAILABLE');continue
        if row['asset']=='*':flags.append('MARKET_WIDE_SENTIMENT_NOT_ASSET_SPECIFIC')
        valid.append(item)
    # Copied/repackaged sources from one publisher group do not earn two budgets.
    grouped={}
    for row in sorted(valid,key=lambda r:(-r['effective_quality'],-r['published_ms'],r['provider_id'])):
        group=row['publisher_group']
        if group in grouped:flags.append('CORRELATED_PUBLISHER_GROUP_EXCLUDED');continue
        grouped[group]=row
    categories={};contributions={};weighted=0.;absolute=0.
    for category,key in (('NEWS','news'),('SOCIAL','crowd_social')):
        selected=[r for r in grouped.values() if r['category']==category]
        if not selected:continue
        total=sum(r['effective_quality'] for r in selected);score=sum(r['score']*r['effective_quality'] for r in selected)/total
        quality=max(r['effective_quality'] for r in selected);weight=BUDGET[key]*quality
        categories[category]=dict(score=score,quality=quality,sources=[{k:r[k] for k in ('provider_id','publisher_group','event_id','revision','profile_revision','published_ms','received_ms','asset','method','terms_url')} for r in selected])
        contributions[key]=weight;weighted+=score*weight;absolute+=abs(score)*weight
    covered=sum(contributions.values())
    if not covered:return None,contributions,dict(categories=categories,agreement=None),flags
    score=weighted/covered;agreement=abs(weighted)/absolute if absolute else 1.
    if agreement<.5 and absolute:flags.append('CONFLICTING_EXTERNAL_SENTIMENT')
    independent=len(categories)==2 and covered>=.30
    label='EXTREMELY_BULLISH' if independent and score>=cfg.external_extreme_band else 'EXTREMELY_BEARISH' if independent and score<=-cfg.external_extreme_band else 'BULLISH' if score>=cfg.external_neutral_band else 'BEARISH' if score<=-cfg.external_neutral_band else 'NEUTRAL'
    return label,contributions,dict(categories=categories,score=score,agreement=agreement,scope='EXTERNAL_NEWS_SOCIAL_SENTIMENT' if len(categories)==2 else 'EXTERNAL_SENTIMENT_PARTIAL'),flags


def evaluate(snapshot,config=None,previous_state=None):
    cfg=config or SentimentConfig()
    if not isinstance(cfg,SentimentConfig):raise TypeError('Use SentimentConfig')
    identity=deepcopy(snapshot['identity']);start,end,known,computed=(snapshot[k] for k in ('candle_open_time','candle_close_time','as_of','computed_at'))
    if set(identity)!={'venue','market_type','instrument_id','symbol','timeframe','dataset_generation'} or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Complete Sentiment identity required')
    if any(type(t) is not int or t<0 for t in (start,end,known,computed)) or end<start or computed<known:raise ValueError('Invalid Sentiment times')
    closed=snapshot['closed']
    if type(closed) is not bool or closed and known<=end or not closed and known<start:raise ValueError('Invalid candle availability')
    if snapshot['provenance_mode'] not in ('LIVE','SIMULATION','HISTORICAL_RECONSTRUCTION'):raise ValueError('Invalid provenance')
    signature=snapshot['input_signature']
    if not isinstance(signature,str) or not signature:raise ValueError('Sentiment signature required')
    binding=dict(identity=identity,config_hash=cfg.fingerprint,input_signature=signature,state_schema_version=VERSION)
    state=deepcopy(previous_state) if previous_state else dict(**binding,last_open=None,last_close=None,classification=UNKNOWN.copy())
    if any(state.get(k)!=v for k,v in binding.items()):raise ValueError('Sentiment state identity/config/source mismatch')
    if state['last_open'] is not None and start<=state['last_open']:raise ValueError('Sentiment candles must be chronological')
    old=deepcopy(state['classification']);flags=[]
    prices=[snapshot['candle'].get(k) for k in ('open','high','low','close')]
    raw=all(finite(v) and v>0 for v in prices);raw=raw and prices[1]>=max(prices) and prices[2]<=min(prices)
    field='measurement_gap';value=snapshot['features'].get(field);at=snapshot['field_available_at'].get(field)
    valid_flag=(type(value) is bool or finite(value) and value in (0,1)) and snapshot['units'].get(field)==UNITS[field] and snapshot['field_validity'].get(field)=='VALID' and type(at) is int and 0<=at<=known
    gap=state['last_close'] is not None and start!=state['last_close']+1 or valid_flag and bool(value)
    if gap:flags.append('CANDLE_GAP')
    calendar=snapshot.get('market_metadata',{}).get('calendar')=='24/7 UTC'
    if not calendar:flags.append('UNSUPPORTED_MARKET_CALENDAR')
    classification=UNKNOWN.copy();parts={key:0. for key in BUDGET};measurements=dict(scope='DERIVATIVES_FUNDING_TILT_ONLY')
    if closed and raw and calendar:
        try:
            classification,parts,measurements,source_flags=context(snapshot,cfg)
            json.dumps(measurements,allow_nan=False);flags.extend(source_flags)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError,ZeroDivisionError):
            classification=UNKNOWN.copy();parts={key:0. for key in BUDGET};measurements=dict(scope='DERIVATIVES_FUNDING_TILT_ONLY');flags.append('SOURCE_SCHEMA_REJECTED')
    external_label=None;external_parts={};external_measurements={}
    if closed and raw and calendar:
        external_label,external_parts,external_measurements,external_flags=external_context(snapshot,cfg)
        flags.extend(external_flags);parts.update(external_parts)
        if external_label is not None:
            classification['sentiment']=external_label
            measurements['funding_scope']='DERIVATIVES_FUNDING_TILT_ONLY'
            measurements['scope']=external_measurements['scope']
            measurements['external_sentiment']=external_measurements
            measurements['unavailable_sources']=['NORMALIZED_POSITIONING','ACCOUNT_RATIOS']+(['NEWS'] if 'news' not in external_parts else [])+(['CROWD_SOCIAL'] if 'crowd_social' not in external_parts else [])
            flags=[flag for flag in flags if flag not in ('SENTIMENT_SOURCES_UNAVAILABLE','BROAD_SENTIMENT_AND_CROWDING_UNAVAILABLE')]
            flags.append('CROWDING_UNAVAILABLE')
            if not parts['funding']:flags.append('DERIVATIVES_SOURCES_UNAVAILABLE')
    coverage=sum(parts.values());strength=None
    if measurements.get('funding_rate') is not None:strength=100*min(1,abs(measurements['funding_rate'])/cfg.funding_strength_fraction)
    if external_label is not None:strength=100*abs(external_measurements['score'])
    confidence=sum(value*(external_measurements.get('agreement',1.) if key in external_parts else 1.) for key,value in parts.items())
    evidence=[dict(code='PARTIAL_DERIVATIVES_SENTIMENT',inputs=['recorded indicative funding','earlier funding/OI observations','reported liquidation windows'],description='Funding tilt, positioning change and observed stress are distinct. Positive funding alone cannot establish crowded longs. Missing inputs remain unknown.')]
    if external_label is not None:evidence.append(dict(code='OPTIONAL_SCORED_EXTERNAL_SENTIMENT',inputs=list(external_measurements['categories']),description='Declared provider aggregate scores with as-of publication/receipt checks, freshness limits and publisher-group deduplication. Not a validated prediction or a locally scored headline.'))
    events=[]
    if closed and classification!=old and classification!=UNKNOWN:
        event=dict(type='SENTIMENT_TRANSITION',classification=deepcopy(classification),origin_time=start,known_time=end+1)
        event['id']=hashlib.sha256(json.dumps([identity,cfg.fingerprint,signature,event],sort_keys=True,allow_nan=False).encode()).hexdigest();events.append(event)
    quality='GAP' if gap else 'INVALID' if not raw else 'PARTIAL' if coverage else 'WARMUP'
    if snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION':flags.append('AVAILABILITY_RECONSTRUCTED')
    result=dict(contract_version='1.0.0',engine='SENTIMENT',engine_version=VERSION,state_schema_version=VERSION,identity=identity,candle_open_time=start,candle_close_time=end,as_of=known,computed_at=computed,available_at=computed if closed else None,mode='CONFIRMED' if closed else 'PROVISIONAL',
        classification=classification if closed else old,candidate_classification=classification,strength=strength,confidence=round(confidence,8),coverage=round(coverage,8),data_quality=quality,quality_flags=sorted(set(flags)),
        measurements={**measurements,'evidence_budget':BUDGET.copy(),'evidence_contributions':parts,'new_events':events,'strength_meaning':'external normalized source-score intensity' if external_label is not None else 'absolute indicative funding tilt intensity, not market-wide sentiment or win probability'},
        confirmation=dict(status='CONFIRMED' if coverage else 'UNAVAILABLE',candidate_bars=1 if coverage else 0,required_bars=1),previous_state=dict(classification=old),
        evidence=evidence,
        config_hash=cfg.fingerprint,input_signature=signature,provenance=dict(mode=snapshot['provenance_mode'],source_versions=deepcopy(snapshot['source_versions']),dependency_results=[]))
    state.update(last_open=start,last_close=end,classification=classification)
    return result,state if closed else deepcopy(previous_state)
