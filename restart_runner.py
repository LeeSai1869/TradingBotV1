"""Install/re-enable this checkout's macOS login runner: python3 restart_runner.py."""
from pathlib import Path
import os
import plistlib
import re
import shlex
import signal
import subprocess
import sys
import time

LABEL = 'com.scalp.liverunner'
ROOT = Path(__file__).resolve().parent
MODULES = ('Section_1_Global_Core.memory_storage.Runner.live_runner',
           'Section_1_Global_Core.orchestrator')


def configuration(python, logs):
    return {'Label': LABEL, 'ProgramArguments': [str(python), '-u', '-m',
            'Section_1_Global_Core.memory_storage.Runner.live_runner'],
            'WorkingDirectory': str(ROOT), 'RunAtLoad': True, 'KeepAlive': True,
            'ThrottleInterval': 15, 'EnvironmentVariables': {'PYTHONUNBUFFERED': '1'},
            'StandardOutPath': str(logs/'runner.log'),
            'StandardErrorPath': str(logs/'runner-error.log')}


def runner_processes():
    result = subprocess.run(['ps','-axo','pid=,stat=,command='], capture_output=True,text=True,check=True)
    found = []
    for line in result.stdout.splitlines():
        try:
            pid, state, command = line.strip().split(None,2)
            args = shlex.split(command)
        except ValueError:
            continue
        if 'Z' in state or '-c' in args:
            continue  # Zombies cannot write; shell/python -c text is not a runner.
        if not any(args[i:i+2] == ['-m',module] for i in range(len(args)-1) for module in MODULES):
            continue
        # ps command strings can contain a parent shell's launch script. Verify
        # the actual executable separately, rather than killing a text match.
        executable = subprocess.run(['ps','-p',pid,'-o','comm='],capture_output=True,text=True).stdout.strip()
        if re.fullmatch(r'python(?:[0-9]+(?:\.[0-9]+)*)?',Path(executable).name,re.IGNORECASE):
            found.append(int(pid))
    return found


def describe_processes(pids):
    if not pids:
        return ''
    return subprocess.run(['ps','-p',','.join(map(str,pids)),'-o','pid=,ppid=,stat=,command='],capture_output=True,text=True).stdout.strip()


def runner_job(label):
    if label == LABEL:
        return True
    try:
        config = plistlib.loads((Path.home()/'Library'/'LaunchAgents'/f'{label}.plist').read_bytes())
        args = config.get('ProgramArguments',[])
        return (Path(config.get('WorkingDirectory','')).resolve()==ROOT
                and any(args[i:i+2]==['-m',module] for i in range(len(args)-1) for module in MODULES))
    except (OSError, ValueError, TypeError):
        return False


def stop_existing(service):
    existing = runner_processes()
    # Verify cwd before stopping either a process or its supervising service.
    for pid in existing:
        result = subprocess.run(['lsof','-a','-p',str(pid),'-d','cwd','-Fn'], capture_output=True,text=True,check=True)
        paths = [line[1:] for line in result.stdout.splitlines() if line.startswith('n')]
        if str(ROOT) not in paths:
            raise SystemExit(f'Runner PID {pid} belongs to another/unknown folder; left it running. Stop it explicitly before retrying.')
    jobs = subprocess.run(['launchctl','list'],capture_output=True,text=True,check=True)
    owners = {}
    for line in jobs.stdout.splitlines():
        fields = line.split()
        if len(fields)==3 and fields[0].isdigit(): owners[int(fields[0])] = fields[2]
    domain = service.rsplit('/',1)[0]
    supervisors = set()
    for pid in existing:
        parent = pid
        for _ in range(8):
            if parent in owners:
                label = owners[parent]
                # Terminal/VS Code can themselves be launchd applications. Never
                # stop a general application just because it owns a manual runner.
                if runner_job(label):
                    supervisors.add(label)
                break
            value = subprocess.run(['ps','-p',str(parent),'-o','ppid='],capture_output=True,text=True).stdout.strip()
            if not value.isdigit() or int(value) <= 1 or int(value)==parent: break
            parent = int(value)
    for label in supervisors:
        job = f'{domain}/{label}'
        # An obsolete login service must not respawn the old writer.
        subprocess.run(['launchctl','disable',job],check=True)
        subprocess.run(['launchctl','bootout',job],capture_output=True)
    subprocess.run(['launchctl','bootout',service],capture_output=True)
    for pid in existing:
        if pid in runner_processes():
            print(f'Stopping existing project runner PID {pid}',flush=True)
            try: os.kill(pid,signal.SIGTERM)
            except ProcessLookupError: pass
    deadline = time.monotonic()+20
    while True:
        remaining = runner_processes()
        if not remaining:
            break
        if time.monotonic() >= deadline:
            raise SystemExit('Python runner(s) still active after stop; no competing writer started.\nPID PPID STATE COMMAND\n'+describe_processes(remaining))
        time.sleep(.25)


def main():
    if sys.platform != 'darwin':
        raise SystemExit('This installer is for macOS launchd. Run the live_runner module directly on other systems.')
    subprocess.run([sys.executable, '-c', 'import pandas, numpy, requests; import Section_4_Features.processor'], cwd=ROOT, check=True)
    domain = f'gui/{os.getuid()}'
    service = f'{domain}/{LABEL}'
    logs = Path.home()/'Library'/'Logs'/'TradingBotV1'
    logs.mkdir(parents=True,exist_ok=True)
    for filename in ('runner.log','runner-error.log'):
        (logs/filename).touch(exist_ok=True)
    stop_existing(service)
    plist = Path.home()/'Library'/'LaunchAgents'/f'{LABEL}.plist'
    plist.parent.mkdir(parents=True,exist_ok=True)
    plist.write_bytes(plistlib.dumps(configuration(Path(sys.executable).absolute(),logs)))
    for command in (['launchctl','enable',service], ['launchctl','bootstrap',domain,str(plist)],
                    ['launchctl','kickstart',service]):
        subprocess.run(command,check=True)
    print('Runner installed and enabled at login. Check startup/errors in:')
    print(logs/'runner.log'); print(logs/'runner-error.log')
    subprocess.run(['launchctl','print',service],check=True)


if __name__ == '__main__':
    main()
