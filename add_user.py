"""Add one normal app user without replacing existing accounts."""
import argparse
import fcntl
import getpass
import json
import os
import re
import secrets
import tempfile
from Section_11_UI_UX.server import auth


def add_user(username,password):
    if not re.fullmatch(r'[A-Za-z0-9_-]{2,32}',username):raise ValueError('Use a username of 2–32 letters, digits, underscores or hyphens')
    if not isinstance(password,str) or len(password)<12:raise ValueError('Password must contain at least 12 characters')
    auth.USERS_FILE.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with os.fdopen(os.open(auth.USERS_FILE.with_suffix('.lock'),os.O_WRONLY|os.O_CREAT,0o600),'a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX)
        users=auth.users()
        if username in users:raise ValueError('That user already exists; no accounts changed')
        salt=secrets.token_hex(16);users[username]=dict(role='user',salt=salt,hash=auth.digest(password,salt))
        with tempfile.NamedTemporaryFile('w',dir=auth.USERS_FILE.parent,delete=False) as stream:
            json.dump(users,stream);temporary=stream.name
        os.replace(temporary,auth.USERS_FILE)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('username');args=parser.parse_args()
    password=getpass.getpass('New password (12+ characters): ')
    if password!=getpass.getpass('Repeat password: '):parser.exit(1,'Passwords did not match; no accounts changed.\n')
    try:add_user(args.username,password)
    except ValueError as error:parser.exit(1,str(error)+'\n')
    print('Created normal user:',args.username)

if __name__=='__main__':main()
