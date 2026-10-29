"""Three distinct barrier clusters per direction, with explicit scenario risk.

Targets are obstacles, not guaranteed fills/profit or estimated liquidation maps.
No price level is invented to fill an absent opportunity layer.
"""
from functools import lru_cache
from Section_1_Global_Core.analysis_packet import number,clean

VERSION='opportunity-v6'
LAYER_SEPARATION_ATR=2.
CONFLUENCE_ATR=1.
FALLBACK_MIN_FAMILIES=3
NATIVE_PRIORITY={'sr':0,'fvg':1,'ob':2,'breaker':3}
ZONES={
 'sr':('support','resistance','inst_support','inst_resistance'),
 'fvg':('nearest_bull_fvg','nearest_bear_fvg'),
 'ob':('active_bull_ob','active_bear_ob','active_strict_bull_ob','active_strict_bear_ob'),
 'breaker':('bull_breaker','bear_breaker'),
 'volume_profile':('vp_hvn','vp_lvn'),
}
POINTS={'structure':('protected_high','protected_low','nearest_swing_high','nearest_swing_low','structure_range_high','structure_range_low'),
        'volume_profile':('vp_poc','vp_va_high','vp_va_low'),'trend':('ema7','ema25','ema50','ema100','ema200','ema300','wma50','vwap','vwap_upper1','vwap_upper2','vwap_lower1','vwap_lower2'),
        'session':('previous_day_high','previous_day_low','nearest_high_price_session','nearest_low_price_session'),
        'fibonacci':('nearest_fib_price',),
        'candle_liquidity':('external_high_liquidity','external_low_liquidity','internal_high_liquidity','internal_low_liquidity','nearest_buy_liquidity_price','nearest_sell_liquidity_price')}
ZONE_FIELDS=[(family,prefix, prefix+('_zone_low' if family=='sr' else '_low'),prefix+('_zone_high' if family=='sr' else '_high')) for family,prefixes in ZONES.items() for prefix in prefixes]
FIELDS=tuple(dict.fromkeys(['atr',*[key for _,_,lo,hi in ZONE_FIELDS for key in (lo,hi)],*[key for fields in POINTS.values() for key in fields]]))
DEFAULT_FEE_BPS=4.
DEFAULT_SLIPPAGE_BPS=2.


def evaluate(close,features,*,fee_bps=DEFAULT_FEE_BPS,slippage_bps=DEFAULT_SLIPPAGE_BPS,zones=(),as_of_ms=None,timeframe='',inventory_status=None,candle=None):
    if not all(number(v) and 0<=v<=100 for v in (fee_bps,slippage_bps)):raise ValueError('Per-side costs must be 0–100 bps')
    extra=tuple((str(z.get('id','')),str(z.get('family','')),str(z.get('name',z.get('id','zone'))),str(z.get('role','dynamic')),clean(z.get('low')),clean(z.get('high')),str(z.get('timeframe',timeframe)),clean(z.get('available_ms'))) for z in zones)
    candle=candle or {}
    high=clean(candle.get('high',close));low=clean(candle.get('low',close))
    return _evaluate(close if number(close) else None,tuple(clean(features.get(k)) for k in FIELDS),fee_bps,slippage_bps,extra,as_of_ms,timeframe,str(inventory_status or 'scalar features only'),high,low)


@lru_cache(maxsize=128)
def _evaluate(close,values,fee_bps,slippage_bps,extra=(),as_of_ms=None,timeframe='',inventory_status='scalar features only',candle_high=None,candle_low=None):
    f=dict(zip(FIELDS,values));atr=f['atr']
    candle_high=close if candle_high is None else candle_high;candle_low=close if candle_low is None else candle_low
    result=dict(version=VERSION,entry=close,buy=None,sell=None,status='unavailable',
        costs=dict(fee_bps_per_side=fee_bps,slippage_bps_per_side=slippage_bps,round_trip_bps=2*(fee_bps+slippage_bps)),
        interpretation='conditional price scenarios; not expected earnings; excludes funding and taxes',
        inputs=dict(timeframe=timeframe,as_of_ms=as_of_ms,inventory_status=inventory_status,scope='same-timeframe zones at the reference candle; no current HTF or live perpetual book'),
        audit=[],context_zones=[],at_entry=[],geometry_policy=dict(native_priority=['sr','fvg','ob','breaker'],native_width='original bounds; no model width cap',fallback_width_atr=1.,fallback_confluence_atr=CONFLUENCE_ATR,fallback_min_families=FALLBACK_MIN_FAMILIES,minimum_layer_spacing_atr=LAYER_SEPARATION_ATR,minimum_candle_clearance_atr=LAYER_SEPARATION_ATR,decision_high=candle_high,decision_low=candle_low))
    if not number(close) or close<=0 or not number(atr) or atr<=0 or not number(LAYER_SEPARATION_ATR*atr) or not number(candle_high) or not number(candle_low) or not 0<candle_low<=close<=candle_high:return result
    candidates=[]
    for identity,family,name,role,low,high,frame,available in extra:
        if family not in ('sr','fvg','ob','breaker','volume_profile') or not number(low) or not number(high) or not 0<low<high:continue
        if timeframe and frame!=timeframe:
            result['audit'].append(dict(source=name,id=identity,low=low,high=high,reason='different_source_timeframe'));continue
        if number(available) and (not number(as_of_ms) or available>as_of_ms):
            result['audit'].append(dict(source=name,id=identity,low=low,high=high,reason='not_available_at_reference'));continue
        candidates.append(dict(family=family,name=name,id=identity,low=low,high=high,role=role,timeframe=frame,origin='inventory'))
    for family,name,low,high in ZONE_FIELDS:
        lo,hi=f[low],f[high]
        if number(lo) and number(hi) and 0<lo<hi:
            role=('support' if 'bull' in name else 'resistance') if family in ('fvg','ob','breaker') else 'dynamic'
            candidates.append(dict(family=family,name=name,low=lo,high=hi,role=role))
    for family,fields in POINTS.items():
        for key in fields:
            value=f[key]
            if number(value) and value>0:
                role='dynamic'  # Broken prior highs/lows can change role relative to the anchor.
                candidates.append(dict(family=family,name=key,low=value,high=value,role=role))
    for c in candidates:
        c.setdefault('id',c['name']);c.setdefault('timeframe',timeframe);c.setdefault('origin','scalar')
        if c['low']>close and c['role']=='support' or c['high']<close and c['role']=='resistance':
            result['audit'].append(dict(source=c['name'],id=c['id'],low=c['low'],high=c['high'],reason='directional_role_not_forward_barrier'))
        if c['low']<=close<=c['high']:
            result['at_entry'].append(dict(c));result['audit'].append(dict(source=c['name'],id=c['id'],low=c['low'],high=c['high'],reason='contains_reference_price'))
    for side,direction in (('buy',1),('sell',-1)):
        eligible=[dict(c) for c in candidates if c['low']>close and c['role']!='support'] if direction==1 else [dict(c) for c in candidates if c['high']<close and c['role']!='resistance']
        clusters=build_bands(eligible,close,atr,direction,audit=result['audit'],context_zones=result['context_zones'],boundary=candle_high if direction==1 else candle_low)
        protective=[c for c in candidates if c['high']<close and c['role']!='resistance'] if direction==1 else [c for c in candidates if c['low']>close and c['role']!='support']
        # Trend averages/VP levels are targets, not structural stop boundaries.
        protective=[c for c in protective if c['family'] in ('sr','fvg','ob','breaker','structure')]
        protective.sort(key=lambda c:close-c['high'] if direction==1 else c['low']-close)
        stop=(protective[0]['low']-.1*atr if direction==1 else protective[0]['high']+.1*atr) if protective else close-direction*1.5*atr
        stop_source=protective[0]['name'] if protective else 'ATR model (1.5 ATR)'
        risk_valid=number(stop) and stop>0 and direction*(close-stop)>0
        loss=direction*(close-stop)/close*100+(fee_bps+slippage_bps)*(1+stop/close)/100 if risk_valid else None
        risk_valid=risk_valid and number(loss) and loss>0
        risk_band=None
        if risk_valid:
            boundary=protective[0] if protective else None
            risk_band=dict(low=boundary['low'] if boundary else stop-.1*atr,high=boundary['high'] if boundary else stop+.1*atr,source=stop_source,modeled=boundary is None)
            if risk_band['low']==risk_band['high']:
                risk_band['low']-=.1*atr;risk_band['high']+=.1*atr;risk_band['modeled']=True
            risk_band['low']=max(0.,risk_band['low'])
        else:stop=None;loss=None;stop_source='no valid modeled invalidation'
        layers=[]
        for cluster in clusters[:3]:
            target=cluster['low'] if direction==1 else cluster['high'];cluster['price']=target
            gross=direction*(target-close)/close*100
            cost=(fee_bps+slippage_bps)*(1+target/close)/100
            net=gross-cost
            if not all(number(v) for v in (gross,cost,net)):continue
            families=sorted(cluster['families'])
            far=cluster['high'] if direction==1 else cluster['low']
            far_net=direction*(far-close)/close*100-(fee_bps+slippage_bps)*(1+far/close)/100
            if not number(far_net):continue
            def net_at(price,position):
                return position*(price-close)/close*100-(fee_bps+slippage_bps)*(1+price/close)/100
            outcomes={position:dict(net_low=min(net_at(cluster['low'],sign),net_at(cluster['high'],sign)),
                                    net_high=max(net_at(cluster['low'],sign),net_at(cluster['high'],sign)))
                      for position,sign in (('BUY',1),('SELL',-1))}
            for value in outcomes.values():
                if not all(number(v) for v in value.values()):value.update(net_low=None,net_high=None)
            layers.append({**cluster,'outcomes':outcomes,'families':families,'confluence_families':len(families),'gross_reward_pct':gross,
                'net_reward_pct':net,'net_reward_far_pct':far_net,'reward_risk':net/loss if loss else None,'reward_risk_far':far_net/loss if loss else None})
        result[side]=dict(entry=close,invalidation=stop,invalidation_source=stop_source,risk_band=risk_band,risk_pct=loss,targets=layers,
            status='favorable geometry' if layers and layers[0]['net_reward_pct']>0 and layers[0]['reward_risk'] is not None and layers[0]['reward_risk']>=1.5 else 'limited reward/risk' if layers else 'no known targets')
    for side,opposite in (('buy','sell'),('sell','buy')):
        if result[side] is not None:
            other=result[opposite]
            result[side]['opposing_band']=dict(other['targets'][0]) if other and other['targets'] else None
    result['areas']={'resistance':result['buy']['targets'] if result['buy'] else [],'support':result['sell']['targets'] if result['sell'] else []}
    result['audit_count']=len(result['audit']);result['audit_truncated']=len(result['audit'])>256
    result['audit']=result['audit'][:256];result['context_zones']=result['context_zones'][:64]
    result['status']='ready' if result['buy'] or result['sell'] else 'unavailable'
    return result


def build_bands(candidates,entry,atr,direction,*,audit=None,context_zones=None,boundary=None):
    """Keep hierarchical native geometry; model only multi-family fallback clusters.

    S/R > FVG > OB > breaker governs a local overlapping region, not the ordering
    of unrelated price levels. Native bounds never shrink, expand or chain-merge.
    All known evidence is retained; family counts use one representative each.
    """
    audit=[] if audit is None else audit;context_zones=[] if context_zones is None else context_zones
    seen=set();native=[];references=[]
    def record(c):
        return dict(id=c.get('id',c['name']),source=c['name'],family=c['family'],low=c['low'],high=c['high'],timeframe=c.get('timeframe',''))
    def note(c,reason,**details):audit.append(dict(record(c),reason=reason,**details))
    def new_core(c,low,high,modeled=False):
        item=record(c)
        return dict(low=low,high=high,sources=[c['name']],families={c['family']},modeled=modeled,
                    geometry_source=item if not modeled else dict(family='line_cluster',source='multi-family cluster'),
                    contributors=[item],evidence=[dict(item,relation='geometry' if not modeled else 'cluster')])
    def attach(core,c,relation):
        item=record(c);core['sources'].append(c['name']);core['evidence'].append(dict(item,relation=relation))
        if c['family'] not in core['families']:
            core['contributors'].append(item);core['families'].add(c['family'])
        note(c,'corroborates_native' if not core['modeled'] else 'cluster_member',
             core_source=core['geometry_source']['source'],core_low=core['low'],core_high=core['high'],relation=relation)
    def overlaps(core,c):
        if c['low']==c['high']:return core['low']<=c['low']<=core['high']
        overlap=min(core['high'],c['high'])-max(core['low'],c['low'])
        return overlap>0 and overlap>=.5*min(core['high']-core['low'],c['high']-c['low'])
    for c in candidates:
        low,high=c['low'],c['high']
        if not number(low) or not number(high) or not 0<low<=high:note(c,'invalid_source_geometry');continue
        identity=(c['family'],low,high)
        if identity in seen:note(c,'duplicate_family_geometry');continue
        seen.add(identity)
        (native if low<high and c['family'] in NATIVE_PRIORITY else references).append(c)
    native.sort(key=lambda c:(NATIVE_PRIORITY[c['family']],direction*(c['low'] if direction==1 else c['high']),-(c['high']-c['low']),c['name']))
    cores=[]
    for c in native:
        core=next((core for core in cores if overlaps(core,c)),None)
        if core is not None:attach(core,c,'contained' if core['low']<=c['low']<=c['high']<=core['high'] else 'overlap')
        else:cores.append(new_core(c,c['low'],c['high']))
    free=[]
    for c in references:
        core=next((core for core in cores if overlaps(core,c)),None)
        if core is not None:attach(core,c,'contained' if core['low']<=c['low']<=c['high']<=core['high'] else 'overlap')
        elif c['high']-c['low']>CONFLUENCE_ATR*atr:
            context_zones.append(dict(c));note(c,'fallback_source_exceeds_cluster_width')
        else:free.append(c)
    free.sort(key=lambda c:direction*(c['low'] if direction==1 else c['high']))
    while free:
        cluster=[];low=free[0]['low'];high=free[0]['high']
        for c in free:
            new_low=min(low,c['low']);new_high=max(high,c['high'])
            if new_high-new_low>CONFLUENCE_ATR*atr:break
            cluster.append(c);low,high=new_low,new_high
        families={c['family'] for c in cluster}
        if len(families)<FALLBACK_MIN_FAMILIES:
            note(free.pop(0),'insufficient_fallback_confluence',families=len(families),required_families=FALLBACK_MIN_FAMILIES);continue
        center=low+(high-low)/2;bottom=center-.5*atr;top=center+.5*atr
        if not number(bottom) or not number(top) or not 0<bottom<top:
            for c in cluster:note(c,'invalid_modeled_geometry')
        elif any(min(top,c['high'])>max(bottom,c['low']) for c in cores if not c['modeled']):
            for c in cluster:note(c,'modeled_cluster_overlaps_native')
        else:
            core=new_core(cluster[0],bottom,top,True)
            for c in cluster[1:]:attach(core,c,'cluster')
            cores.append(core)
        free=free[len(cluster):]
    cores.sort(key=lambda c:direction*(c['low'] if direction==1 else c['high']))
    selected=[];edge=entry if boundary is None else boundary;gap=LAYER_SEPARATION_ATR*atr
    for core in cores:
        if len(selected)>=3:
            for c in core['evidence']:audit.append(dict(c,reason='beyond_nearest_three'))
            continue
        clearance=core['low']-edge if direction==1 else edge-core['high']
        if clearance<gap:
            reason='inside_layer_clearance' if selected else 'inside_decision_candle_clearance'
            for c in core['evidence']:audit.append(dict(c,reason=reason,clearance=clearance,required_gap=gap,core_low=core['low'],core_high=core['high'],core_source=core['geometry_source']['source']))
            continue
        selected.append(core);edge=core['high'] if direction==1 else core['low']
        for c in core['evidence']:audit.append(dict(c,reason='selected',layer=len(selected),core_low=core['low'],core_high=core['high'],core_source=core['geometry_source']['source']))
    return selected



def with_costs(packet,fee_bps,slippage_bps):
    """Reprice saved geometry only; never reread sources or move the anchor."""
    import copy
    if not all(number(v) and 0<=v<=100 for v in (fee_bps,slippage_bps)):raise ValueError('Per-side costs must be 0–100 bps')
    result=copy.deepcopy(packet);entry=result['entry'];cost=fee_bps+slippage_bps
    result['costs']=dict(fee_bps_per_side=fee_bps,slippage_bps_per_side=slippage_bps,round_trip_bps=2*cost)
    def net(price,direction):return direction*(price-entry)/entry*100-cost*(1+price/entry)/100
    for side,direction in (('buy',1),('sell',-1)):
        plan=result.get(side)
        if not plan:continue
        stop=plan.get('invalidation');loss=direction*(entry-stop)/entry*100+cost*(1+stop/entry)/100 if number(stop) else None
        plan['risk_pct']=loss
        for area in plan['targets']:
            target=area['low'] if direction==1 else area['high'];far=area['high'] if direction==1 else area['low']
            area.update(net_reward_pct=net(target,direction),net_reward_far_pct=net(far,direction),
                reward_risk=net(target,direction)/loss if loss else None,reward_risk_far=net(far,direction)/loss if loss else None,
                outcomes={position:dict(net_low=min(net(area['low'],sign),net(area['high'],sign)),net_high=max(net(area['low'],sign),net(area['high'],sign))) for position,sign in (('BUY',1),('SELL',-1))})
        layers=plan['targets']
        plan['status']='favorable geometry' if layers and layers[0]['net_reward_pct']>0 and layers[0]['reward_risk'] is not None and layers[0]['reward_risk']>=1.5 else 'limited reward/risk' if layers else 'no known targets'
    result['areas']=dict(resistance=(result.get('buy') or {}).get('targets',[]),support=(result.get('sell') or {}).get('targets',[]))
    for side,other in (('buy','sell'),('sell','buy')):
        if result.get(side):result[side]['opposing_band']=copy.deepcopy(result[other]['targets'][0]) if result.get(other) and result[other]['targets'] else None
    return result
