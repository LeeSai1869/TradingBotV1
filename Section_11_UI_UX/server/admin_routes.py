"""Role checks live here, not in browser controls."""
import json
import sqlite3
from http.cookies import SimpleCookie
from urllib.parse import urlparse
from Section_1_Global_Core import data_admin, data_policy
from . import auth


def token(server):
    cookie = SimpleCookie()
    try:
        cookie.load(server.headers.get('Cookie', ''))
        return cookie[auth.COOKIE].value if auth.COOKIE in cookie else ''
    except Exception:
        return ''


def user(server):
    return auth.identity(token(server))


def handle_get(path, server):
    if path == '/api/session':
        return 200, user(server)
    if path == '/api/settings/timeframes':
        identity = user(server)
        if identity['role'] != 'admin':
            return (401 if identity['role'] == 'guest' else 403), {'error': 'Administrator access required'}
        state = data_policy.read()
        return 200, {'timeframes': [{'interval': iv, 'status': state['timeframes'].get(iv, 'active')} for iv in data_policy.INTERVALS]}
    return None, None


def handle_post(path, body, server):
    if path not in {'/api/login','/api/logout','/api/settings/timeframes','/api/settings/coins','/api/settings/delete'}:
        return None, None
    origin = server.headers.get('Origin')
    if origin and urlparse(origin).netloc != server.headers.get('Host'):
        return 403, {'error': 'Cross-origin changes are forbidden'}
    try:
        data = json.loads(body or '{}')
        if not isinstance(data, dict):
            raise ValueError('JSON object required')
        if path == '/api/login':
            username, password = data.get('username',''), data.get('password','')
            if not isinstance(username, str) or not isinstance(password, str):
                raise ValueError('Username and password required')
            try:
                session = auth.login(username, password)
            except ValueError as error:
                return 401, {'error': str(error)}
            server.response_cookie = f'{auth.COOKIE}={session}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'
            return 200, auth.identity(session)
        if path == '/api/logout':
            auth.SESSIONS.pop(token(server), None)
            server.response_cookie = f'{auth.COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
            return 200, {'ok': True}
        identity = user(server)
        if identity['role'] == 'guest':
            return 401, {'error': 'Sign in to change download policy'}
        if identity['role'] != 'admin':
            return 403, {'error': 'Administrator access required'}
        if path == '/api/settings/timeframes':
            data_admin.set_timeframe(data.get('interval'), data.get('status'))
        elif path == '/api/settings/coins':
            data_admin.set_coin(data.get('symbol'), data.get('action'))
        else:
            interval, symbol = data.get('interval'), data.get('symbol')
            expected = f'DELETE {interval or symbol}'
            if data.get('confirmation') != expected:
                raise ValueError(f'Type {expected} to confirm deletion')
            return 200, {'ok': True, 'deleted': data_admin.delete_data(interval=interval, symbol=symbol)}
        return 200, {'ok': True}
    except (ValueError, TypeError, KeyError) as error:
        return 400, {'error': str(error)}
    except (OSError, sqlite3.Error):
        return 503, {'error': 'Storage operation failed; the item remains paused if deletion began. Retry after checking runner logs.'}

