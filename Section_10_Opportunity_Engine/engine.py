"""Three distinct barrier clusters per direction, with explicit scenario risk.

Targets are obstacles, not guaranteed fills/profit or estimated liquidation maps.
No price level is invented to fill an absent opportunity layer.
"""
from functools import lru_cache
from Section_1_Global_Core.analysis_packet import number,clean

VERSION='opportunity-v1'
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
        eligible=[c for c in candidates if c['low']>close] if direction==1 else [c for c in candidates if c['high']<close]
        eligible.sort(key=lambda c: direction*(c['low'] if direction==1 else c['high']))
        clusters=[]
        for candidate in eligible:
            edge=candidate['low'] if direction==1 else candidate['high']
            # Anchor the merge tolerance at the first barrier: no transitive
            # chaining across a series of unrelated levels.
            if clusters and abs(edge-clusters[-1]['price'])<=.15*atr:
                clusters[-1]['sources'].append(candidate['name']);clusters[-1]['families'].add(candidate['family'])
                clusters[-1]['low']=min(clusters[-1]['low'],candidate['low']);clusters[-1]['high']=max(clusters[-1]['high'],candidate['high'])
            else:clusters.append(dict(price=edge,low=candidate['low'],high=candidate['high'],sources=[candidate['name']],families={candidate['family']}))
        protective=[c for c in candidates if c['high']<close] if direction==1 else [c for c in candidates if c['low']>close]
        # Trend averages/VP levels are targets, not structural stop boundaries.
        protective=[c for c in protective if c['family'] in ('sr','fvg','ob','breaker','structure')]
        protective.sort(key=lambda c:close-c['high'] if direction==1 else c['low']-close)
        stop=(protective[0]['low']-.1*atr if direction==1 else protective[0]['high']+.1*atr) if protective else close-direction*1.5*atr
        stop_source=protective[0]['name'] if protective else 'ATR model (1.5 ATR)'
        if stop<=0 or direction*(close-stop)<=0:continue
        loss=direction*(close-stop)/close*100+(fee_bps+slippage_bps)*(1+stop/close)/100
        if not number(loss) or loss<=0:continue
        layers=[]
        for cluster in clusters[:3]:
            target=cluster['price'];gross=direction*(target-close)/close*100
            cost=(fee_bps+slippage_bps)*(1+target/close)/100
            net=gross-cost
            if not all(number(v) for v in (gross,cost,net,net/loss)):continue
            families=sorted(cluster.pop('families'))
            layers.append({**cluster,'families':families,'confluence_families':len(families),'gross_reward_pct':gross,
                'net_reward_pct':net,'reward_risk':net/loss if loss>0 else None})
        result[side]=dict(entry=close,invalidation=stop,invalidation_source=stop_source,risk_pct=loss,targets=layers,
            status='favorable geometry' if layers and layers[0]['net_reward_pct']>0 and layers[0]['reward_risk']>=1.5 else 'limited reward/risk' if layers else 'no known targets')
    result['status']='ready' if result['buy'] or result['sell'] else 'unavailable'
    return result
