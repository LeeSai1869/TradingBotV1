"""Install/re-enable this checkout's macOS login runner: python3 restart_runner.py."""
from pathlib import Path
import os
import plistlib
import subprocess
import sys
import time

LABEL = 'com.scalp.liverunner'
ROOT = Path(__file__).resolve().parent


def configuration(python, logs):
    return {'Label': LABEL, 'ProgramArguments': [str(python), '-u', '-m',
            'Section_1_Global_Core.memory_storage.Runner.live_runner'],
            'WorkingDirectory': str(ROOT), 'RunAtLoad': True, 'KeepAlive': True,
            'ThrottleInterval': 15, 'EnvironmentVariables': {'PYTHONUNBUFFERED': '1'},
            'StandardOutPath': str(logs/'runner.log'),
            'StandardErrorPath': str(logs/'runner-error.log')}


def main():
    if sys.platform != 'darwin':
        raise SystemExit('This installer is for macOS launchd. Run the live_runner module directly on other systems.')
    # launchd must use the same interpreter in which the pipeline dependencies work.
    subprocess.run([sys.executable, '-c', 'import pandas, numpy, requests; import Section_4_Features.processor'], cwd=ROOT, check=True)
    domain = f'gui/{os.getuid()}'
    service = f'{domain}/{LABEL}'
    subprocess.run(['launchctl','bootout',service], capture_output=True)
    # Do not start a second writer alongside an independently started runner.
    time.sleep(1)
    processes = subprocess.run(['ps','-axo','pid=,command='], capture_output=True,text=True,check=True)
    manual = [line for line in processes.stdout.splitlines()
              if (' -m Section_1_Global_Core.memory_storage.Runner.live_runner' in line
                  or ' -m Section_1_Global_Core.orchestrator' in line)]
    if manual:
        raise SystemExit('A runner is still running. Stop it with Ctrl+C in its terminal, then retry:\n'+'\n'.join(manual))
    logs = Path.home()/'Library'/'Logs'/'TradingBotV1'
    logs.mkdir(parents=True,exist_ok=True)
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
