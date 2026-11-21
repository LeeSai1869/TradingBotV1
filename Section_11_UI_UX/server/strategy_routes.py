"""Authenticated, same-origin administration for scoped strategy histories."""
import json
from urllib.parse import parse_qs
from . import admin_routes
from .public_access import same_origin
from Section_1_Global_Core import data_admin

PATH='/api/settings/strategies'


def dispatch(path, query, server, body=None):
    if path not in (PATH,PATH+'/history'):return None,None
    identity=admin_routes.user(server)
    if identity['role']!='admin':return (401 if identity['role']=='guest' else 403),dict(error='Administrator access required')
    if body is not None and not same_origin(server,server.headers.get('Origin')):return 403,dict(error='Cross-origin changes forbidden')
    try:
        if body is None:
            if path.endswith('/history'):
                qs=parse_qs(query)
                return 200,data_admin.strategy_management('history',dict(instance_id=qs.get('instance_id',[None])[0],limit=int(qs.get('limit',['100'])[0])))
            return 200,data_admin.strategy_management()
        if path!=PATH:return 405,dict(error='History is read-only')
        data=json.loads(body)
        if not isinstance(data,dict):raise ValueError('JSON object required')
        return 200,data_admin.strategy_management(data.get('action'),data)
    except (ValueError,TypeError,KeyError) as error:return 400,dict(error=str(error))
