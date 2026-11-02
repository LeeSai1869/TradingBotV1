"""Account-owned mobile subscriptions; no unauthenticated enrollment."""
from .public_access import same_origin
import json
from urllib.parse import urlparse
from . import admin_routes,mobile_push


def handle_get(path,server):
    if path not in {'/api/mobile/config','/api/mobile/devices'}:return None,None
    identity=admin_routes.user(server)
    if identity['role']=='guest':return 401,{'error':'Sign in required'}
    return (200,mobile_push.status()) if path.endswith('config') else (200,mobile_push.devices(identity['username']))


def handle_post(path,body,server):
    if path not in {'/api/mobile/subscribe','/api/mobile/unsubscribe','/api/mobile/test'}:return None,None
    identity=admin_routes.user(server)
    if identity['role']=='guest':return 401,{'error':'Sign in required'}
    origin=server.headers.get('Origin')
    if not same_origin(server,origin):return 403,{'error':'Cross-origin changes forbidden'}
    try:
        data=json.loads(body)
        if not isinstance(data,dict):raise ValueError('JSON object required')
        if path=='/api/mobile/test':return 200,mobile_push.send_test(identity['username'],data)
        return 200,(mobile_push.enroll if path.endswith('/subscribe') else mobile_push.remove)(identity['username'],data)
    except (ValueError,TypeError,KeyError) as error:return 400,{'error':str(error)}
