"""Authenticated account-owned alert operations."""
from .public_access import same_origin
import json
from urllib.parse import parse_qs, urlparse
from . import alerts, admin_routes
from Section_1_Global_Core import data_admin, data_policy


def handle_get(path,query,server):
    if path not in {'/api/alerts','/api/alerts/catalog','/api/alerts/events','/api/alerts/signals','/api/alerts/sounds','/api/alerts/history'}: return None,None
    identity=admin_routes.user(server)
    if identity['role']=='guest': return 401,{'error':'Sign in required'}
    if path=='/api/alerts/sounds':
        try:return 200,alerts.sounds(identity['username'],parse_qs(query).get('id',[None])[0])
        except ValueError as error:return 404,{'error':str(error)}
    if path=='/api/alerts/history':
        try:
            qs=parse_qs(query);before=qs.get('before',[None])[0];limit=int(qs.get('limit',['50'])[0])
            return 200,alerts.events(identity['username'],None,history_before=int(before) if before is not None else None,history_limit=limit)
        except (ValueError,TypeError):return 400,{'error':'Choose a valid history page (1–100 messages)'}
    if path=='/api/alerts/signals':return 200,alerts.signal_preferences(identity['username'])
    if path=='/api/alerts/catalog':
        registry=data_admin.catalog()
        symbols=sorted({r['symbol'] for key in ('approved','disapproved','pending','staged','top50') for r in registry.get(key,[])})
        return 200,{'fields':alerts.FIELDS,'live_fields':sorted(alerts.LIVE_FIELDS),'operators':sorted(alerts.OPERATORS),'symbols':symbols,'intervals':data_policy.INTERVALS,'sounds':sorted(alerts.SOUNDS)}
    if path=='/api/alerts': return 200,{'rules':alerts.list_rules(identity['username'])}
    try:
        raw=parse_qs(query).get('after',[None])[0]
        after=int(raw) if raw is not None else None
        if after is not None and not 0 <= after <= 9223372036854775807: raise ValueError()
    except ValueError: return 400,{'error':'Invalid event cursor'}
    return 200,alerts.events(identity['username'],after)


def handle_post(path,body,server):
    if path not in {'/api/alerts','/api/alerts/delete','/api/alerts/signals','/api/alerts/sounds','/api/alerts/sounds/delete'}: return None,None
    identity=admin_routes.user(server)
    if identity['role']=='guest': return 401,{'error':'Sign in required'}
    origin=server.headers.get('Origin')
    if not same_origin(server,origin): return 403,{'error':'Cross-origin changes forbidden'}
    try:
        data=json.loads(body)
        if not isinstance(data,dict): raise ValueError('JSON object required')
        if path=='/api/alerts/sounds':return 200,alerts.upload_sound(identity['username'],data)
        if path=='/api/alerts/sounds/delete':return 200,alerts.delete_sound(identity['username'],data.get('id'))
        if path=='/api/alerts/signals':return 200,alerts.signal_preferences(identity['username'],data)
        if path=='/api/alerts/delete': alerts.delete(identity['username'],data.get('id'));return 200,{'ok':True}
        return 200,{'ok':True,'id':alerts.save(identity['username'],data)}
    except (ValueError,TypeError,KeyError) as error: return 400,{'error':str(error)}
