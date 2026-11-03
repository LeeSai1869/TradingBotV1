"""Immutable alert presentation. Unknown evidence is never replaced with zeros."""
import math
from datetime import datetime,timezone
from urllib.parse import urlencode


def number(value):
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) else None


def details(bar,side=None,context=None):
    client=bar.get('client') or {};context=context or {}
    matching=side in ('BUY','SELL') and context.get('side')==side and context.get('open_time')==bar.get('open_time') and context.get('entry')==client.get('close')
    confidence=(context.get('confidence') or {}) if matching else {}
    areas=(context.get('area_map') or (context.get('opportunity') or {}).get('areas') or {}) if matching else {}
    def band(role):
        rows=areas.get(role) or []
        if not rows:return None
        low,high=number(rows[0].get('low')),number(rows[0].get('high'))
        return dict(low=low,high=high) if low is not None and high is not None and 0<low<=high else None
    return dict(side=side,price=number(client.get('close')),confidence=number(confidence.get(str(side).lower()+'_score')),
                upper=band('resistance'),lower=band('support'),signal_ms=(number(client.get('close_time')) or number(bar.get('open_time')) or 0)+1,
                evidence='anchored decision snapshot' if matching else 'unavailable')


def chart_url(event):
    return '/?'+urlencode(dict(symbol=event['symbol'],interval=event['interval'],at=event['bar_time']))


def push_payload(event):
    data=event.get('details') or {};fmt=lambda value:'Unavailable' if number(value) is None else f'{value:g}'
    upper=data.get('upper') or {};lower=data.get('lower') or {}
    title=f"{event['symbol']} {event['interval']} {data.get('side') or event['name']}"
    stamp=datetime.fromtimestamp((data.get('signal_ms') or event['created'])/1000,timezone.utc).isoformat()
    body=f"Time {stamp}\nPrice {fmt(data.get('price'))} · Confidence {fmt(data.get('confidence'))}/100\nSell OZ upper {fmt(upper.get('high'))} · Buy OZ lower {fmt(lower.get('low'))}"
    return dict(title=title,body=body,tag=f"signal-{event['seq']}",timestamp=data.get('signal_ms') or event['created'],
                data=dict(url='/web_root/mobile.html?seq='+str(event['seq']),event={key:event.get(key) for key in ('seq','name','symbol','interval','bar_time','created','details')}))
