"""Local account provisioning and expiring, server-side browser sessions."""
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time

USERS_FILE = Path.home() / '.tradingbot' / 'users.json'
SESSIONS = {}
ATTEMPTS = []
COOKIE = 'tradingbot_session'


def users():
    return json.loads(USERS_FILE.read_text()) if USERS_FILE.exists() else {}


def digest(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 260000).hex()


def login(username, password):
    now = time.time()
    ATTEMPTS[:] = [t for t in ATTEMPTS if now - t < 60]
    if len(ATTEMPTS) >= 10:
        raise ValueError('Too many login attempts; wait one minute')
    ATTEMPTS.append(now)
    account = users().get(username)
    salt = account['salt'] if account else '00' * 16
    actual = digest(password, salt)
    if not account or not hmac.compare_digest(actual, account['hash']):
        raise ValueError('Incorrect username or password')
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = (username, account['role'], now + 8 * 3600)
    # Bound session memory and discard expired sessions.
    for key, value in list(SESSIONS.items()):
        if value[2] < now:
            SESSIONS.pop(key, None)
    while len(SESSIONS) > 100:
        SESSIONS.pop(next(iter(SESSIONS)))
    return token


def identity(token):
    session = SESSIONS.get(token)
    if not session or session[2] < time.time():
        SESSIONS.pop(token, None)
        return {'username': None, 'role': 'guest', 'configured': USERS_FILE.exists()}
    return {'username': session[0], 'role': session[1], 'configured': True}


def main():
    USERS_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    accounts = {}
    for username, role in [('admin','admin'), ('user','user')]:
        password = getpass.getpass(f'Set password for {username} (at least 12 characters): ')
        if len(password) < 12:
            raise SystemExit('Password must be at least 12 characters. No accounts changed.')
        if password != getpass.getpass('Repeat password: '):
            raise SystemExit('Passwords do not match. No accounts changed.')
        salt = secrets.token_hex(16)
        accounts[username] = {'role': role, 'salt': salt, 'hash': digest(password, salt)}
    temp = USERS_FILE.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(accounts, stream)
    temp.replace(USERS_FILE)
    print('Created admin and user accounts. Restart the UI server to invalidate old sessions.')


if __name__ == '__main__':
    main()
