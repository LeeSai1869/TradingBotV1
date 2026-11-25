"""User-login macOS services for the paper worker and its independent dashboard."""
import os
from contextlib import contextmanager
import fcntl
from pathlib import Path
import plistlib
import subprocess
import sys

LABELS=('com.tradingindicator.paperbot','com.tradingindicator.paperbotdashboard')


@contextmanager
def worker_lock(ledger):
    ledger=Path(ledger).expanduser().resolve()
    path=ledger.with_name(ledger.name+'.worker.lock')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('A paper worker is already running for this ledger') from None
        try:yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)


def definitions(root,python,ledger,home):
    root=Path(root).resolve();home=Path(home);ledger=Path(ledger).expanduser().resolve()
    common=[str(python),'-u','-m','Section_15_Execution_Bot','--db',str(ledger)]
    logs=home/'Library/Logs/TradingBotV1'
    result=[]
    for label,command in zip(LABELS,([ '/usr/bin/caffeinate','-i',*common,'run','--poll-seconds','1'],[*common,'dashboard','--port','8002'])):
        env={'PYTHONUNBUFFERED':'1'}
        if os.environ.get('TRADINGBOT_DATA_DIR'):env['TRADINGBOT_DATA_DIR']=os.environ['TRADINGBOT_DATA_DIR']
        result.append(dict(Label=label,ProgramArguments=command,WorkingDirectory=str(root),RunAtLoad=True,
            KeepAlive=True,ThrottleInterval=30,EnvironmentVariables=env,
            StandardOutPath=str(logs/(label+'.log')),StandardErrorPath=str(logs/(label+'-error.log'))))
    return result


def owned(saved,expected):
    # Only replace services installed for this exact checkout and paper ledger.
    return all(saved.get(key)==expected[key] for key in ('Label','WorkingDirectory','ProgramArguments'))


def manage(action,ledger,*,home=None,root=None,python=None):
    if sys.platform!='darwin':raise ValueError('Login services are supported on macOS only')
    home=Path(home) if home is not None else Path.home()
    root=Path(root) if root is not None else Path(__file__).resolve().parent.parent
    configs=definitions(root,python or sys.executable,ledger,home)
    folder=home/'Library/LaunchAgents';domain=f'gui/{os.getuid()}'
    if action=='status':
        result=[]
        for cfg in configs:
            job=subprocess.run(['/bin/launchctl','print',domain+'/'+cfg['Label']],capture_output=True,text=True)
            pid=next((line.split('=',1)[1].strip() for line in job.stdout.splitlines() if line.strip().startswith('pid =')),None)
            result.append(dict(service=cfg['Label'],loaded=job.returncode==0,pid=int(pid) if pid and pid.isdigit() else None))
        return result
    if action not in ('install','uninstall'):raise ValueError('Unknown service action')
    # Validate both before changing either, including uninstall.
    for cfg in configs:
        path=folder/(cfg['Label']+'.plist')
        if path.exists():
            with path.open('rb') as stream:saved=plistlib.load(stream)
            if not owned(saved,cfg):raise ValueError('Service belongs to another checkout or configuration: '+str(path))
    shortcut=home/'Desktop/Paper Bot Dashboard.webloc'
    if action=='install' and shortcut.exists():
        with shortcut.open('rb') as stream:saved=plistlib.load(stream)
        if saved!={'URL':'http://127.0.0.1:8002/'}:raise ValueError('Dashboard shortcut already exists with a different destination')
    for cfg in configs:
        path=folder/(cfg['Label']+'.plist')
        if path.exists():
            # An unloaded job also returns nonzero; no unrelated label is touched.
            subprocess.run(['/bin/launchctl','bootout',domain,str(path)],capture_output=True)
        if action=='uninstall':
            path.unlink(missing_ok=True)
            continue
        folder.mkdir(parents=True,exist_ok=True)
        Path(cfg['StandardOutPath']).parent.mkdir(parents=True,exist_ok=True)
        with path.open('wb') as stream:plistlib.dump(cfg,stream)
        result=subprocess.run(['/bin/launchctl','bootstrap',domain,str(path)],capture_output=True,text=True)
        if result.returncode:raise ValueError('Could not start '+cfg['Label']+': '+result.stderr.strip()+'. Check services status and the paper-service logs')
    if action=='install':
        shortcut.parent.mkdir(parents=True,exist_ok=True)
        with shortcut.open('wb') as stream:plistlib.dump({'URL':'http://127.0.0.1:8002/'},stream)
        return dict(installed=list(LABELS),dashboard='http://127.0.0.1:8002/',shortcut=str(shortcut),
            message='Paper worker and dashboard run at login and restart after exit. Chart and market runner are unchanged.')
    return dict(uninstalled=list(LABELS),message='Paper services stopped. Ledger, history, logs and dashboard shortcut retained.')
