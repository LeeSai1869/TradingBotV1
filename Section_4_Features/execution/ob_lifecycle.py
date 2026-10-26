"""Multiple OB lifetimes; sparse reversible events retain terminal history.

Normal/strict detection is unchanged. Existing scalar outputs remain the latest
selected block; this ledger retains older valid blocks independently. OHLC touch
and close invalidation describe the same candle, not an inferred intrabar order.
"""
import json
from . import runtime as rt


def advance(previous, index, time, low, high, close, births):
    zones={identity:dict(zone) for identity,zone in previous.items()}
    terminal={}
    for identity,zone in list(zones.items()):
        # A return must occur strictly after formation/promotion.
        if index<=zone['created_bar']:continue
        touched=low<=zone['high'] and high>=zone['low']
        invalid=close<zone['low'] if zone['side']=='bull' else close>zone['high']
        if touched and not zone['mitigated']:
            zone.update(mitigated=True,mitigated_bar=index,mitigated_time=time)
        if not invalid:continue
        terminal[identity]={**zone,'invalidated_bar':index,'invalidated_time':time}
        del zones[identity]
        if zone['kind']=='ob':
            side='bear' if zone['side']=='bull' else 'bull'
            breaker_id=identity+':breaker'
            zones[breaker_id]={**zone,'side':side,'kind':'breaker','origin_id':identity,
                'origin_mitigated':zone['mitigated'],'origin_mitigated_bar':zone.get('mitigated_bar'),
                'origin_mitigated_time':zone.get('mitigated_time'),
                'created_bar':index,'created_time':time,'mitigated':False,'mitigated_bar':None,'mitigated_time':None}
    for strict,side,event,zlow,zhigh,has_fvg,strength in births:
        if not rt.truth(event) or rt.is_na(zlow) or rt.is_na(zhigh) or zhigh<=zlow:continue
        identity=f"{'strict' if strict else 'normal'}:{side}:{index}"
        zones[identity]=dict(side=side,kind='ob',strict=strict,low=zlow,high=zhigh,
            created_bar=index,created_time=time,origin_bar=index-1,has_fvg=rt.truth(has_fvg),
            strength=None if rt.is_na(strength) else strength,mitigated=False,mitigated_bar=None,mitigated_time=None)
    events=[dict(id=identity,**zone,before=previous.get(identity)) for identity,zone in zones.items() if previous.get(identity)!=zone]
    events.extend(dict(id=identity,removed=True,before=previous[identity],terminal=terminal[identity]) for identity in sorted(previous.keys()-zones.keys()))
    return zones,json.dumps(events,separators=(',',':'),sort_keys=True,allow_nan=False)
