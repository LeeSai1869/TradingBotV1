"""Authenticated account-owned alert operations."""
import json
from urllib.parse import parse_qs, urlparse
from . import alerts, admin_routes
from Section_1_Global_Core import data_admin, data_policy


def handle_get(path,query,server):
    if path not in {'/api/alerts','/api/alerts/catalog','/api/alerts/events'}: return None,None
    identity=admin_routes.user(server)
    if identity['role']=='guest': return 401,{'error':'Sign in required'}
    if path=='/api/alerts/catalog':
        registry=data_admin.catalog()
        symbols=sorted({r['symbol'] for key in ('approved','disapproved','pending','staged','top50') for r in registry.get(key,[])})
        return 200,{'fields':alerts.FIELDS,'operators':sorted(alerts.OPERATORS),'symbols':symbols,'intervals':data_policy.INTERVALS,'sounds':sorted(alerts.SOUNDS)}
    if path=='/api/alerts': return 200,{'rules':alerts.list_rules(identity['username'])}
    try:
        raw=parse_qs(query).get('after',[None])[0]
        after=int(raw) if raw is not None else None
        if after is not None and not 0 <= after <= 9223372036854775807: raise ValueError()
    except ValueError: return 400,{'error':'Invalid event cursor'}
    return 200,alerts.events(identity['username'],after)


def handle_post(path,body,server):
    if path not in {'/api/alerts','/api/alerts/delete'}: return None,None
    identity=admin_routes.user(server)
    if identity['role']=='guest': return 401,{'error':'Sign in required'}
    origin=server.headers.get('Origin')
    if origin and urlparse(origin).netloc!=server.headers.get('Host'): return 403,{'error':'Cross-origin changes forbidden'}
    try:
        data=json.loads(body)
        if not isinstance(data,dict): raise ValueError('JSON object required')
        if path=='/api/alerts/delete': alerts.delete(identity['username'],data.get('id'));return 200,{'ok':True}
        return 200,{'ok':True,'id':alerts.save(identity['username'],data)}
    except (ValueError,TypeError,KeyError) as error: return 400,{'error':str(error)}
