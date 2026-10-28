"""Three distinct barrier clusters per direction, with explicit scenario risk.

Targets are obstacles, not guaranteed fills/profit or estimated liquidation maps.
No price level is invented to fill an absent opportunity layer.
"""
from functools import lru_cache
from Section_1_Global_Core.analysis_packet import number,clean

VERSION='opportunity-v2'
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
        'fibonacci':('nearest_fib_price',)}
ZONE_FIELDS=[(family,prefix, prefix+('_zone_low' if family=='sr' else '_low'),prefix+('_zone_high' if family=='sr' else '_high')) for family,prefixes in ZONES.items() for prefix in prefixes]
FIELDS=tuple(dict.fromkeys(['atr',*[key for _,_,lo,hi in ZONE_FIELDS for key in (lo,hi)],*[key for fields in POINTS.values() for key in fields]]))
DEFAULT_FEE_BPS=4.
DEFAULT_SLIPPAGE_BPS=2.


def evaluate(close,features,*,fee_bps=DEFAULT_FEE_BPS,slippage_bps=DEFAULT_SLIPPAGE_BPS):
    if not all(number(v) and 0<=v<=100 for v in (fee_bps,slippage_bps)):raise ValueError('Per-side costs must be 0–100 bps')
    return _evaluate(close if number(close) else None,tuple(clean(features.get(k)) for k in FIELDS),fee_bps,slippage_bps)


@lru_cache(maxsize=8192)
def _evaluate(close,values,fee_bps,slippage_bps):
    f=dict(zip(FIELDS,values));atr=f['atr']
    result=dict(version=VERSION,entry=close,buy=None,sell=None,status='unavailable',
        costs=dict(fee_bps_per_side=fee_bps,slippage_bps_per_side=slippage_bps,round_trip_bps=2*(fee_bps+slippage_bps)),
        interpretation='conditional price scenarios; not expected earnings; excludes funding and taxes')
    if not number(close) or close<=0 or not number(atr) or atr<=0:return result
    candidates=[]
    for family,name,low,high in ZONE_FIELDS:
        lo,hi=f[low],f[high]
        if number(lo) and number(hi) and 0<lo<hi:candidates.append(dict(family=family,name=name,low=lo,high=hi))
    for family,fields in POINTS.items():
        for key in fields:
            value=f[key]
            if number(value) and value>0:candidates.append(dict(family=family,name=key,low=value,high=value))
    for side,direction in (('buy',1),('sell',-1)):
        eligible=[dict(c) for c in candidates if c['low']>close] if direction==1 else [dict(c) for c in candidates if c['high']<close]
        clusters=build_bands(eligible,close,atr,direction)
        protective=[c for c in candidates if c['high']<close] if direction==1 else [c for c in candidates if c['low']>close]
        # Trend averages/VP levels are targets, not structural stop boundaries.
        protective=[c for c in protective if c['family'] in ('sr','fvg','ob','breaker','structure')]
        protective.sort(key=lambda c:close-c['high'] if direction==1 else c['low']-close)
        stop=(protective[0]['low']-.1*atr if direction==1 else protective[0]['high']+.1*atr) if protective else close-direction*1.5*atr
        stop_source=protective[0]['name'] if protective else 'ATR model (1.5 ATR)'
        if stop<=0 or direction*(close-stop)<=0:continue
        loss=direction*(close-stop)/close*100+(fee_bps+slippage_bps)*(1+stop/close)/100
        if not number(loss) or loss<=0:continue
        boundary=protective[0] if protective else None
        risk_band=dict(low=boundary['low'] if boundary else stop-.1*atr,high=boundary['high'] if boundary else stop+.1*atr,source=stop_source,modeled=boundary is None)
        if risk_band['low']==risk_band['high']:
            risk_band['low']-=.1*atr;risk_band['high']+=.1*atr;risk_band['modeled']=True
        risk_band['low']=max(0.,risk_band['low'])
        layers=[]
        for cluster in clusters[:3]:
            target=cluster['low'] if direction==1 else cluster['high'];cluster['price']=target
            gross=direction*(target-close)/close*100
            cost=(fee_bps+slippage_bps)*(1+target/close)/100
            net=gross-cost
            if not all(number(v) for v in (gross,cost,net,net/loss)):continue
            families=sorted(cluster['families'])
            far=cluster['high'] if direction==1 else cluster['low']
            far_net=direction*(far-close)/close*100-(fee_bps+slippage_bps)*(1+far/close)/100
            if not number(far_net):continue
            layers.append({**cluster,'families':families,'confluence_families':len(families),'gross_reward_pct':gross,
                'net_reward_pct':net,'net_reward_far_pct':far_net,'reward_risk':net/loss if loss>0 else None,'reward_risk_far':far_net/loss})
        result[side]=dict(entry=close,invalidation=stop,invalidation_source=stop_source,risk_band=risk_band,risk_pct=loss,targets=layers,
            status='favorable geometry' if layers and layers[0]['net_reward_pct']>0 and layers[0]['reward_risk']>=1.5 else 'limited reward/risk' if layers else 'no known targets')
    for side,opposite in (('buy','sell'),('sell','buy')):
        if result[side] is not None:
            other=result[opposite]
            result[side]['opposing_band']=dict(other['targets'][0]) if other and other['targets'] else None
    result['status']='ready' if result['buy'] or result['sell'] else 'unavailable'
    return result


def build_bands(candidates,entry,atr,direction):
    """Preserve real bounds; model point-reference bands; merge before choosing 3.

    Original distance scales: 1 ATR confluence, 2 ATR layer spacing, 3 ATR
    susceptible area. Gap merges are bounded; actual overlaps always coalesce.
    """
    bands=[];epsilon=entry*1e-12
    for c in candidates:
        low,high=c['low'],c['high'];modeled=low==high
        if modeled:
            low=max(entry+epsilon,low-.1*atr) if direction==1 else max(epsilon,low-.1*atr)
            high=high+.1*atr if direction==1 else min(entry-epsilon,high+.1*atr)
        if not number(low) or not number(high) or not 0<low<high:continue
        bands.append(dict(low=low,high=high,sources=[c['name']],families={c['family']},
                          modeled=modeled,nearby_sources=[]))
    bands.sort(key=lambda c:c['low'])
    merged=[]
    for band in bands:
        previous=merged[-1] if merged else None
        gap=band['low']-previous['high'] if previous else float('inf')
        span=max(previous['high'],band['high'])-previous['low'] if previous else 0
        if previous and (gap<=0 or gap<=atr and span<=3*atr):
            previous['high']=max(previous['high'],band['high'])
            previous['sources']=list(dict.fromkeys(previous['sources']+band['sources']))
            previous['families']|=band['families'];previous['modeled']|=band['modeled']
        else:merged.append(band)
    ordered=merged if direction==1 else list(reversed(merged));selected=[]
    for band in ordered:
        previous=selected[-1] if selected else None
        gap=(band['low']-previous['high'] if direction==1 else previous['low']-band['high']) if previous else float('inf')
        if previous and gap<2*atr:
            span=max(previous['high'],band['high'])-min(previous['low'],band['low'])
            if span<=3*atr:
                previous['low']=min(previous['low'],band['low']);previous['high']=max(previous['high'],band['high'])
                previous['sources']=list(dict.fromkeys(previous['sources']+band['sources']));previous['families']|=band['families'];previous['modeled']|=band['modeled']
            else:previous['nearby_sources']+=band['sources']
        else:selected.append(band)
    return selected[:3]
