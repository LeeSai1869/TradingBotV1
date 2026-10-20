"""Restart only this project's chart backend on macOS; leave the runner alone."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

PORT = 8000
ROOT = Path(__file__).resolve().parent


def listeners():
    result = subprocess.run(['lsof','-nP','-t',f'-iTCP:{PORT}','-sTCP:LISTEN'],capture_output=True,text=True)
    return sorted(set(result.stdout.split()))


def ready():
    try:
        with urlopen(f'http://127.0.0.1:{PORT}/api/session',timeout=1) as response:
            data=json.load(response)
        return data.get('role') in {'guest','user','admin'} and isinstance(data.get('configured'),bool)
    except (OSError, ValueError):
        return False


def is_chart_server(command):
    return 'Section_11_UI_UX.server.ui_server' in command or 'Section_11_UI_UX/server/ui_server.py' in command


def main():
    os.chdir(ROOT)
    try: pids=listeners()
    except FileNotFoundError: raise SystemExit('lsof is required to identify the UI server safely.')
    jobs={}
    if sys.platform=='darwin':
        result=subprocess.run(['launchctl','list'],capture_output=True,text=True)
        services={}
        for line in result.stdout.splitlines():
            fields=line.split()
            if len(fields)==3 and fields[0].isdigit(): services[fields[0]]=fields[2]
        for pid in pids:
            owner=pid
            for _ in range(8):
                if owner in services:
                    jobs[pid]=services[owner]
                    break
                parent=subprocess.run(['ps','-p',owner,'-o','ppid='],capture_output=True,text=True).stdout.strip()
                if not parent.isdigit() or parent in {'0','1',owner}: break
                owner=parent
    # Validate all listeners before stopping any of them.
    for pid in pids:
        command=subprocess.run(['ps','-p',pid,'-o','command='],capture_output=True,text=True).stdout
        if not is_chart_server(command):
            raise SystemExit(f'Port {PORT} belongs to a different process (PID {pid}). No process was stopped.')
    for pid in pids:
        print(f'Restarting UI backend PID {pid}',flush=True)
        if pid in jobs:
            result=subprocess.run(['launchctl','kickstart','-k',f'gui/{os.getuid()}/{jobs[pid]}'])
            if result.returncode: raise SystemExit('Could not restart the UI launchd service.')
        else:
            try: os.kill(int(pid),signal.SIGTERM)
            except ProcessLookupError: pass
    # Give launchd time to restart its service; do not launch a competing server.
    deadline=time.monotonic()+(15 if jobs else 2)
    while time.monotonic()<deadline:
        if not set(pids).intersection(listeners()) and ready():
            print('Updated UI backend is ready. Reopen the app or hard-refresh to sign in.')
            return
        time.sleep(.2)
    if jobs:
        raise SystemExit('The UI service did not become ready. Check its launchd logs; the runner was not stopped.')
    if listeners():
        raise SystemExit('Port 8000 is still occupied but the account API is unavailable. Check the UI backend logs.')
    print('Starting updated UI backend. Keep this terminal open.',flush=True)
    os.execv(sys.executable,[sys.executable,'-u','-m','Section_11_UI_UX.server.ui_server'])


if __name__=='__main__':
    main()
