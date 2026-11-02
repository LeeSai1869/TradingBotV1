"""One explicit operator-configured HTTPS origin; no trusted forwarded headers."""
from urllib.parse import urlparse
from . import mobile_push


def public_request(server):
    try:
        origin=mobile_push.configuration().get('origin')
        if not origin:return False
        host=server.headers.get('Host','');parsed=urlparse(origin)
        return host==parsed.netloc or server.headers.get('Origin','').rstrip('/')==origin.rstrip('/') and urlparse('http://'+host).hostname in ('127.0.0.1','localhost')
    except (OSError,ValueError):return False


def same_origin(server,origin):
    if not origin:return True
    if urlparse(origin).netloc==server.headers.get('Host'):return True
    try:return public_request(server) and origin.rstrip('/')==mobile_push.configuration().get('origin','').rstrip('/')
    except (OSError,ValueError):return False
