"""Separate inferred levels, sweep sequences and observed execution context.

Pure interpretation only. Core supplies immutable as-of recorder projections;
no SQL, fetches, depth reconstruction or trade decisions belong in this module.
"""
from copy import deepcopy
import hashlib
import json
import math
from .liquidity_config import LiquidityConfig

VERSION = '1.0.0'
FIELDS = ('prev_high_liquidity','prev_low_liquidity','previous_day_high','previous_day_low','prev_close','atr',
          'structure_events','structure_events_version','structure_event_status',
          'measurement_contiguous_bars','measurement_gap','measurement_version','measurement_config_id')
UNITS = {key:'price' for key in FIELDS}
UNITS.update(structure_events='source_enum',structure_event_status='source_enum',structure_events_version='version',
             measurement_contiguous_bars='candles',measurement_gap='boolean',measurement_version='version',measurement_config_id='identifier')
UNKNOWN = dict(structural_side='UNKNOWN',sweep='UNKNOWN',sweep_status='UNKNOWN',book_state='UNKNOWN',derivatives_state='UNKNOWN')


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def nonnegative(v):return finite(v) and v>=0

def fresh(stamp, at, age):return type(stamp) is int and stamp>=0 and 0<=at-stamp<=age


def observed(snapshot,cfg):
    """Interpret a named source; never silently treat perpetual depth as spot."""
    flags=[];out=dict(scope=None,association=None,book=None,flow_60s=None,derivatives=None,reported_liquidations=None)
    parts=dict(book=0.,flow=0.,oi=0.,funding=0.,liquidations=0.)
    book_state=derivatives_state='UNKNOWN'
    bundle=snapshot.get('observations')
    if not isinstance(bundle,dict) or bundle.get('version')!='liquidity-projection-v1' or bundle.get('status')!='RECORDED':
        return book_state,derivatives_state,parts,out,['OBSERVED_DATA_UNAVAILABLE']
    sample=bundle.get('sample');identity=snapshot['identity'];at=snapshot['as_of'];age=cfg.sample_max_age_ms
    if not isinstance(sample,dict):return book_state,derivatives_state,parts,out,['OBSERVED_DATA_UNAVAILABLE']
    valid_identity=(sample.get('venue')==identity['venue']=='binance' and sample.get('market')=='usdt_perpetual'
                    and sample.get('symbol')==identity['symbol']==identity['instrument_id'] and sample.get('quote')=='USDT' and sample.get('observed') is True)
    if not valid_identity:return book_state,derivatives_state,parts,out,['OBSERVED_IDENTITY_REJECTED']
    available,sampled=sample.get('available_ms'),sample.get('sampled_ms')
    if not fresh(available,at,age) or not fresh(sampled,at,age) or sampled>available:
        return book_state,derivatives_state,parts,out,['OBSERVATION_STALE_OR_FUTURE']
    gap=bundle.get('last_gap_ms')
    if gap is not None and (type(gap) is not int or not 0<=gap<=at):return book_state,derivatives_state,parts,out,['INVALID_GAP_PROVENANCE']
    if gap is not None and gap>=sampled:return book_state,derivatives_state,parts,out,['OBSERVATION_GAP']
    no_gap=lambda start:gap is None or type(start) is int and gap<start
    metrics=sample.get('metrics',{});coverage=sample.get('coverage',{});association=bundle.get('association')
    received,exchange=sample.get('book_received_ms'),sample.get('exchange_ms')
    sequence=sample.get('sequence')
    synchronized=(fresh(received,at,age) and fresh(exchange,at,age) and exchange<=received<=sampled
                  and type(sequence) is int and sequence>0 and no_gap(received))
    mid,bid,ask=metrics.get('mid'),metrics.get('best_bid'),metrics.get('best_ask')
    prices_ok=all(finite(v) and v>0 for v in (mid,bid,ask)) and bid<ask and abs(mid-(bid+ask)/2)<=mid*1e-10
    if not isinstance(association,dict):return book_state,derivatives_state,parts,out,['OBSERVED_ASSOCIATION_UNAVAILABLE']
    if identity['market_type']=='usdt_perpetual' and association.get('kind')=='EXACT_MARKET':
        out['association']=dict(kind='EXACT_MARKET')
    elif identity['market_type']=='spot' and association.get('kind')=='RELATED_PERPETUAL_CONTEXT' and synchronized and prices_ok:
        close=snapshot['candle']['close'];basis=(mid/close-1)*10000
        actual=association.get('basis_bps')
        accepted=(finite(basis) and finite(actual) and abs(basis-actual)<1e-7 and abs(basis)<=cfg.max_cross_market_basis_bps
                  and association.get('spot_close')==close and association.get('perpetual_mid')==mid and association.get('spot_close_time')==snapshot['candle_close_time'])
        if not accepted:return book_state,derivatives_state,parts,out,['CROSS_MARKET_BASIS_REJECTED']
        out['association']=dict(kind='RELATED_PERPETUAL_CONTEXT',basis_bps=basis,spot_close=close,perpetual_mid=mid)
        flags.append('PERPETUAL_CONTEXT_IS_NOT_SPOT_DEPTH')
    else:return book_state,derivatives_state,parts,out,['OBSERVED_ASSOCIATION_REJECTED']
    out['scope']=dict(venue=sample['venue'],market_type=sample['market'],symbol=sample['symbol'],quote='USDT',available_ms=available,sampled_ms=sampled)
    depths=[metrics.get(f'{side}_depth_{cfg.depth_bps}bps_usdt') for side in ('bid','ask')]
    slip=[metrics.get(f'{side}_slippage_{cfg.execution_notional_usdt}_usdt_bps') for side in ('buy','sell')]
    spread=metrics.get('spread_bps')
    covered=all(nonnegative(coverage.get(side+'_bps')) and coverage[side+'_bps']>=cfg.depth_bps for side in ('bid','ask'))
    book_ok=(synchronized and prices_ok and covered and all(nonnegative(v) for v in depths+slip) and nonnegative(spread)
             and abs(spread-(ask-bid)/mid*10000)<1e-6)
    if book_ok:
        capacity=min(depths)/cfg.execution_notional_usdt
        book_state='THIN' if capacity<cfg.normal_depth_multiple or spread>cfg.max_spread_bps or max(slip)>cfg.max_slippage_bps else 'DEEP' if capacity>=cfg.deep_depth_multiple else 'NORMAL'
        window_start=sample.get('book_window_start_ms')
        withdrawing=False;fractions={}
        if cfg.depth_bps==10 and type(window_start) is int and window_start>=0 and 0<sampled-window_start<=age and no_gap(window_start):
            for side,current in zip(('bid','ask'),depths):
                delta=metrics.get(side+'_depth_10bps_change_usdt')
                previous=current-delta if finite(delta) else None
                fractions[side]=(current/previous-1) if finite(previous) and previous>0 else None
                if fractions[side] is not None and fractions[side]<=-cfg.withdrawal_fraction:withdrawing=True
        if withdrawing:book_state='WITHDRAWING'
        parts['book']=.25
        out['book']=dict(depth_bps=cfg.depth_bps,execution_notional_usdt=cfg.execution_notional_usdt,bid_depth_usdt=depths[0],ask_depth_usdt=depths[1],buy_slippage_bps=slip[0],sell_slippage_bps=slip[1],spread_bps=spread,depth_change_fraction=fractions,capacity_multiple=capacity,sequence=sequence,observed_coverage_bps={key:coverage[key] for key in ('bid_bps','ask_bps')})
    else:flags.append('BOOK_UNAVAILABLE_OR_INSUFFICIENT_COVERAGE')
    flow=sample.get('flow_60s',{});duration=flow.get('observed_window_ms')
    flow_ok=(synchronized and sample.get('trade_coverage')=='continuous' and flow.get('complete') is True and finite(flow.get('coverage')) and .99<=flow['coverage']<=1
             and finite(duration) and 59500<=duration<=70000 and sampled>=duration and no_gap(sampled-duration)
             and all(nonnegative(flow.get(k)) for k in ('aggressive_buy_usdt','aggressive_sell_usdt')) and finite(flow.get('price_change_bps')))
    if flow_ok:
        buy,sell=flow['aggressive_buy_usdt'],flow['aggressive_sell_usdt'];total=buy+sell
        if finite(total):
            imbalance=(buy-sell)/total if total else None
            out['flow_60s']=dict(buy_usdt=buy,sell_usdt=sell,imbalance=imbalance,observed_window_ms=duration,
                                buy_absorption_evidence=imbalance is not None and imbalance>=.6 and abs(flow['price_change_bps'])<=2,
                                sell_absorption_evidence=imbalance is not None and imbalance<=-.6 and abs(flow['price_change_bps'])<=2)
            parts['flow']=.05
    if not parts['flow']:flags.append('CONTINUOUS_FLOW_UNAVAILABLE')
    context=sample.get('context',{});base=bundle.get('oi_baseline');oi=context.get('open_interest')
    oi_time,oi_received=context.get('open_interest_exchange_ms'),context.get('open_interest_received_ms')
    oi_fresh=(nonnegative(oi) and fresh(oi_time,sampled,cfg.context_max_age_ms) and fresh(oi_received,sampled,cfg.context_max_age_ms) and oi_time<=oi_received and no_gap(oi_time))
    oi_change=None;oi_window=None
    if oi_fresh and isinstance(base,dict) and all(base.get(k)==sample.get(k) for k in ('venue','market','symbol','quote','observed')):
        bc=base.get('context',{});boi=bc.get('open_interest');bt=bc.get('open_interest_exchange_ms');br=bc.get('open_interest_received_ms');ba=base.get('available_ms')
        good=(finite(boi) and boi>0 and fresh(ba,at-300000,age) and fresh(bt,ba,cfg.context_max_age_ms)
              and fresh(br,ba,cfg.context_max_age_ms) and bt<=br and 180000<=oi_time-bt<=420000 and no_gap(bt))
        if good:
            change=(oi/boi-1)*100
            if finite(change):oi_change=change;oi_window=oi_time-bt;parts['oi']=.10
    if oi_change is not None:
        derivatives_state='BUILDING' if oi_change>=cfg.oi_change_threshold_pct else 'UNWINDING' if oi_change<=-cfg.oi_change_threshold_pct else 'STABLE'
    else:flags.append('OI_CHANGE_UNAVAILABLE')
    mark,index,funding=(context.get(k) for k in ('mark_price','index_price','funding_rate'))
    mark_time,mark_received=context.get('mark_exchange_ms'),context.get('mark_received_ms')
    mark_fresh=(all(finite(v) and v>0 for v in (mark,index)) and finite(funding) and fresh(mark_time,sampled,age) and fresh(mark_received,sampled,age) and mark_time<=mark_received and no_gap(mark_time))
    mark_basis=(mark/index-1)*10000 if mark_fresh else None
    if mark_basis is not None and finite(mark_basis):parts['funding']=.05
    else:mark_fresh=False;mark_basis=None;flags.append('MARK_FUNDING_UNAVAILABLE')
    out['derivatives']=dict(open_interest=oi if oi_fresh else None,open_interest_change_pct=oi_change,open_interest_window_ms=oi_window,
                            funding_rate=funding if mark_fresh else None,mark_price=mark if mark_fresh else None,index_price=index if mark_fresh else None,mark_index_basis_bps=mark_basis)
    start=sample.get('window_start_ms');liquidations=[sample.get(k) for k in ('reported_long_liquidations_usdt','reported_short_liquidations_usdt')]
    label=sample.get('liquidation_coverage')
    if type(start) is int and start>=0 and 0<sampled-start<=age and no_gap(start) and all(nonnegative(v) for v in liquidations) and isinstance(label,str) and label.startswith('sampled exchange'):
        out['reported_liquidations']=dict(long_usdt=liquidations[0],short_usdt=liquidations[1],window_start_ms=start,window_end_ms=sampled,coverage='SAMPLED_EXCHANGE_REPORTS_NOT_ALL_LIQUIDATIONS')
        parts['liquidations']=.05
    return book_state,derivatives_state,parts,out,flags


def evaluate(snapshot,config=None,previous_state=None):
    cfg=config or LiquidityConfig()
    if not isinstance(cfg,LiquidityConfig):raise TypeError('Use LiquidityConfig')
    identity=deepcopy(snapshot['identity']);start,end,known,computed=(snapshot[k] for k in ('candle_open_time','candle_close_time','as_of','computed_at'))
    if set(identity)!={'venue','market_type','instrument_id','symbol','timeframe','dataset_generation'} or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Complete Liquidity identity required')
    if any(type(v) is not int or v<0 for v in (start,end,known,computed)) or end<start or computed<known:raise ValueError('Invalid Liquidity times')
    closed=snapshot['closed']
    if type(closed) is not bool or closed and known<=end or not closed and known<start:raise ValueError('Invalid candle availability')
    if snapshot['provenance_mode'] not in ('LIVE','SIMULATION','HISTORICAL_RECONSTRUCTION'):raise ValueError('Invalid provenance')
    signature=snapshot['input_signature']
    if not isinstance(signature,str) or not signature:raise ValueError('Liquidity signature required')
    binding=dict(identity=identity,config_hash=cfg.fingerprint,input_signature=signature,state_schema_version=VERSION)
    state=deepcopy(previous_state) if previous_state else dict(**binding,last_open=None,last_close=None,index=-1,pivots={},pending={},classification=UNKNOWN.copy())
    if any(state.get(k)!=v for k,v in binding.items()):raise ValueError('Liquidity state identity/config/source mismatch')
    if state['last_open'] is not None and start<=state['last_open']:raise ValueError('Liquidity candles must be chronological')
    old=deepcopy(state['classification']);flags=[];f={};invalid=False
    for key in FIELDS:
        value=snapshot['features'].get(key);at=snapshot['field_available_at'].get(key);kind=UNITS[key]
        if value is not None and (snapshot['field_validity'].get(key)!='VALID' or snapshot['units'].get(key)!=kind or type(at) is not int or not 0<=at<=known):value=None;flags.append('INPUT_UNAVAILABLE:'+key)
        if value is not None:
            valid=isinstance(value,str) if kind in ('source_enum','version','identifier') else (type(value) is bool or finite(value) and value in (0,1)) if kind=='boolean' else finite(value)
            if valid and kind=='price':valid=value>=0 if key=='atr' else value>0
            if valid and kind=='candles':valid=value>=0 and int(value)==value
            if not valid:value=None;invalid=True;flags.append('INVALID_INPUT:'+key)
            elif kind=='boolean':value=bool(value)
            elif kind=='candles':value=int(value)
        f[key]=value
    prices=[snapshot['candle'].get(k) for k in ('open','high','low','close')]
    raw=all(finite(v) and v>0 for v in prices);raw=raw and prices[1]>=max(prices) and prices[2]<=min(prices)
    gap=state['last_close'] is not None and start!=state['last_close']+1 or f['measurement_gap'] is True
    compatible=snapshot.get('feature_parameters',{}).get('liquidityLookback')==cfg.liquidity_length
    if not compatible:flags.append('INCOMPATIBLE_FEATURE_PARAMETERS')
    shared=f['measurement_version']=='shared-v1' and bool(f['measurement_config_id'])
    if not shared:flags.append('SHARED_FEATURES_UNAVAILABLE')
    calendar=snapshot.get('market_metadata',{}).get('calendar')=='24/7 UTC'
    if not calendar:flags.append('UNSUPPORTED_MARKET_CALENDAR')
    if gap:state.update(pivots={},pending={});flags.append('CANDLE_GAP')
    usable=closed and raw and not invalid and not gap and compatible and shared and calendar
    state['index']+=1
    classification=UNKNOWN.copy();levels={'BSL':[],'SSL':[]};events=[];nearest={'BSL':None,'SSL':None};parts=dict(structural=0.,sweep=0.,book=0.,flow=0.,oi=0.,funding=0.,liquidations=0.);records=[]
    obs=None
    def emit(kind,**details):
        item=dict(type=kind,origin_time=start,known_time=end+1,**details)
        item['id']=hashlib.sha256(json.dumps([identity,cfg.fingerprint,signature,item],sort_keys=True,allow_nan=False).encode()).hexdigest();events.append(item);return item
    if usable:
        warm=f['measurement_contiguous_bars'] is not None and f['measurement_contiguous_bars']>=cfg.liquidity_length+1
        for side,key,session_key in (('BSL','prev_high_liquidity','previous_day_high'),('SSL','prev_low_liquidity','previous_day_low')):
            if warm and f[key] is not None:levels[side].append(dict(price=f[key],source=key,known_time=start))
            if f[session_key] is not None:levels[side].append(dict(price=f[session_key],source=session_key,known_time=start))
            pivot=state['pivots'].get(side)
            if pivot and state['index']-pivot['index']<=cfg.pivot_max_age_bars:levels[side].append({k:v for k,v in pivot.items() if k!='index'})
            # Exact equal references cannot generate duplicate sweep events.
            levels[side]=list({item['price']:item for item in levels[side]}.values())
            forward=[v for v in levels[side] if (v['price']>=prices[3] if side=='BSL' else v['price']<=prices[3])]
            if forward:nearest[side]=min(forward,key=lambda v:abs(v['price']-prices[3]))
        valid_sides=sum(bool(v) for v in levels.values());parts['structural']=.125*valid_sides
        distances={side:abs(v['price']/prices[3]-1)*10000 for side,v in nearest.items() if v}
        at_level=any(abs(v['price']/prices[3]-1)*10000<=cfg.at_level_bps for values in levels.values() for v in values)
        if at_level:classification['structural_side']='AT_LEVEL'
        elif distances:
            nearest_distance=min(distances.values())
            tied=len(distances)==2 and abs(distances['BSL']-distances['SSL'])<1e-8
            classification['structural_side']='MID_RANGE' if nearest_distance>cfg.near_level_bps or tied else 'BUY_SIDE_NEAR' if distances.get('BSL',math.inf)<distances.get('SSL',math.inf) else 'SELL_SIDE_NEAR'
        if valid_sides<2:flags.append('STRUCTURAL_LEVEL_COVERAGE_PARTIAL')
        sweep_ready=f['prev_close'] is not None
        sweep_sides={side for side,values in levels.items() if sweep_ready and values}|set(state['pending'])
        parts['sweep']=.125*len(sweep_sides)
        resolved=set()
        for side,pending in list(state['pending'].items()):
            pending['age']+=1;price=pending['level']['price'];buffer=price*cfg.at_level_bps/10000
            proposal=('CONFIRMED_REJECTION' if prices[3]<price-buffer else 'ACCEPTANCE_ABOVE' if prices[3]>price+buffer else None) if side=='BSL' else ('CONFIRMED_REJECTION' if prices[3]>price+buffer else 'ACCEPTANCE_BELOW' if prices[3]<price-buffer else None)
            pending['count']=pending['count']+1 if proposal and pending.get('candidate')==proposal else 1 if proposal else 0;pending['candidate']=proposal
            if proposal and pending['count']>=cfg.sweep_confirmation_bars:
                event=emit('SWEEP_RESOLVED',side=side,status=proposal,sweep_origin_time=pending['origin_time'],sweep_id=pending['id'],level=deepcopy(pending['level']))
                records.append(event);resolved.add(side);del state['pending'][side]
            elif pending['age']>cfg.sweep_max_bars:
                emit('SWEEP_EXPIRED',side=side,sweep_id=pending['id'],sweep_origin_time=pending['origin_time']);del state['pending'][side];resolved.add(side)
        if sweep_ready:
            for side in levels:
                if side in state['pending'] or side in resolved:continue
                eligible=[]
                for level in levels[side]:
                    price=level['price'];buffer=price*cfg.at_level_bps/10000
                    crossed=f['prev_close']<=price+buffer and prices[1]>price+buffer if side=='BSL' else f['prev_close']>=price-buffer and prices[2]<price-buffer
                    if crossed:eligible.append(level)
                if eligible:
                    level=min(eligible,key=lambda v:abs(v['price']-f['prev_close']))
                    event=emit('POTENTIAL_SWEEP',side=side,status='POTENTIAL',level=deepcopy(level))
                    state['pending'][side]=dict(id=event['id'],origin_time=start,level=deepcopy(level),age=0,count=0,candidate=None)
        records.extend(dict(side=side,status='POTENTIAL',sweep_id=item['id'],sweep_origin_time=item['origin_time'],level=deepcopy(item['level'])) for side,item in state['pending'].items())
        if len(records)==1:classification.update(sweep=records[0]['side']+'_SWEEP',sweep_status=records[0]['status'])
        elif len(records)>1:flags.append('TWO_SIDED_SWEEP_AMBIGUITY')
        elif sweep_ready and valid_sides==2:classification.update(sweep='NONE',sweep_status='NONE')
        # Confirmed producer pivots become eligible only on the next candle.
        lineage=f['structure_events_version']=='structure-events-v1' and f['structure_event_status']=='READY'
        if lineage:
            try:
                batch=json.loads(f['structure_events'])
                if not isinstance(batch,list) or len(batch)>8:raise ValueError('Invalid events')
                next_pivots={}
                for event in batch:
                    if not isinstance(event,dict):raise ValueError('Invalid event')
                    if event.get('type') not in ('PIVOT_HIGH','PIVOT_LOW'):continue
                    origin=event.get('origin_time');price=event.get('price')
                    if event.get('source_version')!='structure-events-v1' or not isinstance(event.get('id'),str) or not event['id'] or type(origin) is not int or not 0<=origin<start or event.get('known_time')!=end+1 or event.get('confirmation_time')!=start or not finite(price) or price<=0:raise ValueError('Invalid pivot lineage')
                    side='BSL' if event['type']=='PIVOT_HIGH' else 'SSL'
                    next_pivots[side]=dict(price=price,source='confirmed_pivot',known_time=end+1,origin_time=origin,id=event['id'],index=state['index'])
                state['pivots'].update(next_pivots)
            except (ValueError,TypeError):flags.append('PIVOT_LINEAGE_UNAVAILABLE')
        else:flags.append('PIVOT_LINEAGE_UNAVAILABLE')
    else:
        state.update(pending={},pivots={})
        if not closed:flags.append('CLOSED_CANDLE_REQUIRED')
    if closed and raw and calendar:
        try:
            book,derivatives,observed_parts,obs,observed_flags=observed(snapshot,cfg)
            json.dumps(obs,allow_nan=False)
            classification.update(book_state=book,derivatives_state=derivatives);parts.update(observed_parts);flags.extend(observed_flags)
        except (TypeError,ValueError,KeyError,AttributeError,OverflowError,ZeroDivisionError):
            obs=None;flags.append('OBSERVATION_SCHEMA_REJECTED')
    coverage=sum(parts.values())
    confidence=coverage
    strength=None
    if obs and obs['book']:
        capacity=obs['book']['capacity_multiple'];strength=100*min(1,capacity/cfg.deep_depth_multiple)
    if closed and classification!=old and classification!=UNKNOWN:emit('LIQUIDITY_TRANSITION',classification=deepcopy(classification))
    quality='GAP' if gap else 'INVALID' if invalid or not raw else 'WARMUP' if not coverage else 'VALID' if coverage>=1-1e-12 else 'PARTIAL'
    if snapshot['provenance_mode']=='HISTORICAL_RECONSTRUCTION':flags.append('AVAILABILITY_RECONSTRUCTED')
    result=dict(contract_version='1.0.0',engine='LIQUIDITY',engine_version=VERSION,state_schema_version=VERSION,identity=identity,candle_open_time=start,candle_close_time=end,as_of=known,computed_at=computed,available_at=computed if closed else None,mode='CONFIRMED' if closed else 'PROVISIONAL',
                classification=classification if closed else old,candidate_classification=classification,strength=strength,confidence=round(confidence,8),coverage=round(coverage,8),data_quality=quality,quality_flags=sorted(set(flags)),
                measurements={**f,'inferred_levels':levels,'nearest_inferred_levels':nearest,'sweep_records':records,'new_events':events if closed else [],'observed':obs,'evidence_contributions':parts,'strength_meaning':'observed depth capacity relative to configured execution size, not reversal strength'},
                confirmation=dict(status='CONFIRMED' if coverage else 'UNAVAILABLE',candidate_bars=1 if coverage else 0,required_bars=1),previous_state=dict(classification=old),evidence=[dict(code='SEPARATE_LIQUIDITY_DIMENSIONS',inputs=list(FIELDS),description='Inferred pre-existing levels and later sweep outcomes are separate from explicitly scoped, fresh observed execution/derivatives data. Evidence availability is not a win probability.')],
                config_hash=cfg.fingerprint,input_signature=signature,provenance=dict(mode=snapshot['provenance_mode'],source_versions=deepcopy(snapshot['source_versions']),dependency_results=[]))
    state.update(last_open=start,last_close=end,classification=classification)
    return result,state if closed else deepcopy(previous_state)
