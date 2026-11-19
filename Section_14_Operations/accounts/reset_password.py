"""Reset one existing local app password without replacing users or account data."""
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import fcntl
import getpass
import json
import os
import secrets
import tempfile
from Section_11_UI_UX.server import auth


def reset_password(username,password):
    if not isinstance(password,str) or len(password)<12:raise ValueError('Use at least 12 characters')
    if not auth.USERS_FILE.is_file():raise ValueError('Accounts file is missing; no accounts changed')
    lock=auth.USERS_FILE.with_suffix('.lock')
    with os.fdopen(os.open(lock,os.O_WRONLY|os.O_CREAT,0o600),'a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX)
        accounts=auth.users()
        if username not in accounts:raise ValueError('Unknown account; use --list to see existing usernames')
        salt=secrets.token_hex(16)
        accounts[username]={**accounts[username],'salt':salt,'hash':auth.digest(password,salt)}
        temporary=None
        try:
            with tempfile.NamedTemporaryFile('w',dir=auth.USERS_FILE.parent,delete=False) as stream:
                temporary=stream.name;json.dump(accounts,stream);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,auth.USERS_FILE);temporary=None
        finally:
            if temporary is not None:os.unlink(temporary)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username',nargs='?')
    parser.add_argument('--list',action='store_true',help='List usernames/roles only, never credentials')
    args=parser.parse_args()
    if args.list:
        for username,account in auth.users().items():print(f'{username}\t{account.get("role", "unknown")}')
        return
    if not args.username:parser.error('Choose an existing username or use --list')
    if args.username not in auth.users():parser.exit(1,'Unknown account; use --list. No accounts changed.\n')
    password=getpass.getpass('New password (12+ characters): ')
    if password!=getpass.getpass('Repeat password: '):parser.exit(1,'Passwords do not match; no accounts changed.\n')
    try:reset_password(args.username,password)
    except ValueError as error:parser.exit(1,str(error)+'\n')
    print('Password reset for '+args.username+'. Restart the chart backend to clear old active sessions.')


if __name__=='__main__':main()
