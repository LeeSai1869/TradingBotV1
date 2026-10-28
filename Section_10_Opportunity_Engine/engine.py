"""Three distinct barrier clusters per direction, with explicit scenario risk.

Targets are obstacles, not guaranteed fills/profit or estimated liquidation maps.
No price level is invented to fill an absent opportunity layer.
"""
from functools import lru_cache
from Section_1_Global_Core.analysis_packet import number,clean

VERSION='opportunity-v4'
ZONES={
 'sr':('support','resistance','inst_support','inst_resistance'),
 'fvg':('nearest_bull_fvg','nearest_bear_fvg'),
 'ob':('active_bull_ob','active_bear_ob','active_strict_bull_ob','active_strict_bear_ob'),
 'breaker':('bull_breaker','bear_breaker'),
 'volume_profile':('vp_hvn','vp_lvn'),
}
POINTS={'structure':('protected_high','protected_low','nearest_swing_high','nearest_swing_low','structure_range_high','structure_range_low'),
        'volume_profile':('vp_poc','vp_va_high','vp_va_low'),'trend':('ema50','ema200','vwap'),
        'session':('previous_day_high','previous_day_low','nearest_high_price_session','nearest_low_price_session'),
        'fibonacci':('nearest_fib_price',),
        'candle_liquidity':('external_high_liquidity','external_low_liquidity','internal_high_liquidity','internal_low_liquidity','nearest_buy_liquidity_price','nearest_sell_liquidity_price')}
ZONE_FIELDS=[(family,prefix, prefix+('_zone_low' if family=='sr' else '_low'),prefix+('_zone_high' if family=='sr' else '_high')) for family,prefixes in ZONES.items() for prefix in prefixes]
FIELDS=tuple(dict.fromkeys(['atr',*[key for _,_,lo,hi in ZONE_FIELDS for key in (lo,hi)],*[key for fields in POINTS.values() for key in fields]]))
DEFAULT_FEE_BPS=4.
DEFAULT_SLIPPAGE_BPS=2.


def evaluate(close,features,*,fee_bps=DEFAULT_FEE_BPS,slippage_bps=DEFAULT_SLIPPAGE_BPS,zones=(),as_of_ms=None,timeframe='',inventory_status=None):
    if not all(number(v) and 0<=v<=100 for v in (fee_bps,slippage_bps)):raise ValueError('Per-side costs must be 0–100 bps')
    extra=tuple((str(z.get('id','')),str(z.get('family','')),str(z.get('name',z.get('id','zone'))),str(z.get('role','dynamic')),clean(z.get('low')),clean(z.get('high')),str(z.get('timeframe',timeframe)),clean(z.get('available_ms'))) for z in zones)
    return _evaluate(close if number(close) else None,tuple(clean(features.get(k)) for k in FIELDS),fee_bps,slippage_bps,extra,as_of_ms,timeframe,str(inventory_status or 'scalar features only'))


@lru_cache(maxsize=128)
def _evaluate(close,values,fee_bps,slippage_bps,extra=(),as_of_ms=None,timeframe='',inventory_status='scalar features only'):
    f=dict(zip(FIELDS,values));atr=f['atr']
    result=dict(version=VERSION,entry=close,buy=None,sell=None,status='unavailable',
        costs=dict(fee_bps_per_side=fee_bps,slippage_bps_per_side=slippage_bps,round_trip_bps=2*(fee_bps+slippage_bps)),
        interpretation='conditional price scenarios; not expected earnings; excludes funding and taxes',
        inputs=dict(timeframe=timeframe,as_of_ms=as_of_ms,inventory_status=inventory_status,scope='same-timeframe zones at the reference candle; no current HTF or live perpetual book'),
        audit=[],context_zones=[],at_entry=[],geometry_policy=dict(max_entry_band_atr=.5,max_entry_band_pct=1.,point_half_width_atr=.05,point_half_width_pct=.05,minimum_layer_spacing_atr=0))
    if not number(close) or close<=0 or not number(atr) or atr<=0:return result
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
        clusters=build_bands(eligible,close,atr,direction,audit=result['audit'],context_zones=result['context_zones'])
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


def build_bands(candidates,entry,atr,direction,*,audit=None,context_zones=None):
    """One non-expanding grouping pass; distinct nearby levels are never discarded.

    Native geometry is authoritative. Broad sources are context-only, not cropped
    into invented entry zones. One representative per family may corroborate a
    core. Points are padded conservatively and cannot bridge neighboring points.
    """
    audit=[] if audit is None else audit;context_zones=[] if context_zones is None else context_zones
    cap=min(.5*atr,.01*entry);bands=[];seen=set()
    point_values=sorted({c['low'] for c in candidates if c['low']==c['high']})
    def note(c,reason,**details):
        audit.append(dict(source=c['name'],id=c.get('id',c['name']),family=c['family'],
            low=c['low'],high=c['high'],timeframe=c.get('timeframe',''),reason=reason,**details))
    for c in candidates:
        low,high=c['low'],c['high'];modeled=low==high
        identity=(c['family'],low,high)
        if identity in seen:note(c,'duplicate_family_geometry');continue
        seen.add(identity)
        if modeled:
            neighbors=[abs(low-p) for p in point_values if p!=low]
            half=min(.05*atr,.0005*entry,.25*abs(low-entry),.05*low)
            if neighbors:half=min(half,.25*min(neighbors))
            low,high=low-half,high+half
        if not number(low) or not number(high) or not 0<low<high:note(c,'invalid_modeled_geometry');continue
        if high-low>cap:
            context_zones.append(dict(c,width=high-low,width_pct=clean((high-low)/entry*100)))
            note(c,'broad_context_only',width=high-low,max_action_width=cap);continue
        bands.append(dict(low=low,high=high,sources=[c['name']],families={c['family']},modeled=modeled,
            contributors=[dict(id=c.get('id',c['name']),source=c['name'],family=c['family'],low=c['low'],high=c['high'],timeframe=c.get('timeframe',''))]))
    # Native narrow cores first. Attaching corroboration never changes a core's bounds.
    bands.sort(key=lambda b:(b['modeled'],b['high']-b['low'],abs((b['low']+b['high'])/2-entry),b['sources'][0]))
    cores=[]
    for band in bands:
        matched=None;duplicate=None
        for core in cores:
            overlap=min(core['high'],band['high'])-max(core['low'],band['low'])
            small=min(core['high']-core['low'],band['high']-band['low'])
            if overlap>=.5*small:
                if core['families']&band['families']:duplicate=core
                else:matched=core
                break
        if duplicate is not None:
            for c in band['contributors']:audit.append(dict(c,reason='same_family_alternative',core_low=duplicate['low'],core_high=duplicate['high']))
            continue
        if matched is not None:
            matched['sources']+=band['sources'];matched['families']|=band['families'];matched['contributors']+=band['contributors']
            for c in band['contributors']:audit.append(dict(c,reason='corroborates_core',core_low=matched['low'],core_high=matched['high']))
        else:cores.append(band)
    cores.sort(key=lambda b:direction*(b['low'] if direction==1 else b['high']))
    for index,core in enumerate(cores):
        for c in core['contributors']:audit.append(dict(c,reason='selected' if index<3 else 'beyond_nearest_three',layer=index+1))
    return cores[:3]
