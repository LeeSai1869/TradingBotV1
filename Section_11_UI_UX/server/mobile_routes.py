"""Account-owned mobile subscriptions; no unauthenticated enrollment."""
from .public_access import same_origin
import json
from urllib.parse import urlparse
from . import admin_routes,mobile_push,android_push


def handle_get(path,server):
    if path not in {'/api/mobile/config','/api/mobile/devices','/api/android/config'}:return None,None
    identity=admin_routes.user(server)
    if identity['role']=='guest':return 401,{'error':'Sign in required'}
    if path=='/api/android/config':return 200,android_push.client_config()
    if path=='/api/mobile/config':
        web=mobile_push.status();android=android_push.status()
        return 200,{**web,'ready':web['ready'] or android['ready'],'web_ready':web['ready'],'android_ready':android['ready'],'origin':web['origin'] or android['origin']}
    return 200,mobile_push.devices(identity['username'])


def handle_post(path,body,server):
    if path not in {'/api/mobile/subscribe','/api/mobile/unsubscribe','/api/mobile/test','/api/android/subscribe','/api/android/unsubscribe','/api/mobile/preferences'}:return None,None
    identity=admin_routes.user(server)
    if identity['role']=='guest':return 401,{'error':'Sign in required'}
    origin=server.headers.get('Origin')
    if not same_origin(server,origin):return 403,{'error':'Cross-origin changes forbidden'}
    try:
        data=json.loads(body)
        if not isinstance(data,dict):raise ValueError('JSON object required')
        if path=='/api/android/subscribe':return 200,android_push.register(identity['username'],data)
        if path=='/api/android/unsubscribe':return 200,android_push.remove(identity['username'],data)
        if path=='/api/mobile/preferences':return 200,mobile_push.preferences(identity['username'],data)
        if path=='/api/mobile/test':return 200,mobile_push.send_test(identity['username'],data)
        return 200,(mobile_push.enroll if path.endswith('/subscribe') else mobile_push.remove)(identity['username'],data)
    except (ValueError,TypeError,KeyError) as error:return 400,{'error':str(error)}
