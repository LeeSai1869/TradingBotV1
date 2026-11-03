"""One explicit operator-configured HTTPS origin; no trusted forwarded headers."""
from urllib.parse import urlparse
from . import mobile_push,android_push


def configured_origin():
    web=mobile_push.configuration().get('origin');android=android_push.configuration().get('origin')
    if web and android and web!=android:raise ValueError('Android and Web Push must use the same laptop origin')
    return web or android


def public_request(server):
    try:
        origin=configured_origin()
        if not origin:return False
        host=server.headers.get('Host','');parsed=urlparse(origin)
        return host==parsed.netloc or server.headers.get('Origin','').rstrip('/')==origin.rstrip('/') and urlparse('http://'+host).hostname in ('127.0.0.1','localhost')
    except (OSError,ValueError):return False


def same_origin(server,origin):
    if not origin:return True
    if urlparse(origin).netloc==server.headers.get('Host'):return True
    try:return public_request(server) and origin.rstrip('/')==(configured_origin() or '').rstrip('/')
    except (OSError,ValueError):return False
