"""One explicit operator-configured HTTPS origin; no trusted forwarded headers."""
import json
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from Section_1_Global_Core.paths import data_path
from . import mobile_push,android_push

CONFIG_FILE=data_path('accounts/public_access.json',Path.home()/'.tradingbot'/'public_access.json')


def normalize_origin(value):
    if not isinstance(value,str):raise ValueError('Use an HTTPS origin')
    parsed=urlparse(value)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.path not in ('','/') or parsed.query or parsed.fragment:raise ValueError('Use an HTTPS origin without credentials, paths or query parameters')
    host=parsed.hostname.lower()
    return 'https://'+('['+host+']' if ':' in host else host)


def save_origin(value):
    origin=normalize_origin(value)
    existing=[module.configuration().get('origin') for module in (mobile_push,android_push)]
    if any(item and normalize_origin(item)!=origin for item in existing):raise ValueError('Existing push configuration uses a different origin')
    CONFIG_FILE.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with tempfile.NamedTemporaryFile(mode='w',dir=CONFIG_FILE.parent,delete=False) as stream:
        json.dump(dict(origin=origin),stream,indent=2);temp=Path(stream.name)
    temp.replace(CONFIG_FILE)
    return origin


def configured_origin():
    web=mobile_push.configuration().get('origin');android=android_push.configuration().get('origin')
    configured=None
    if CONFIG_FILE.is_file():
        value=json.loads(CONFIG_FILE.read_text())
        if not isinstance(value,dict) or set(value)!={'origin'}:raise ValueError('Invalid HTTPS access configuration')
        configured=normalize_origin(value['origin'])
    origins={normalize_origin(origin) for origin in (web,android,configured) if origin}
    if len(origins)>1:raise ValueError('HTTPS access and push must use the same laptop origin')
    return next(iter(origins),None)


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
