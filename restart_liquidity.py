"""Install/restart the independent macOS perpetual-liquidity login recorder."""
from pathlib import Path
import os
import plistlib
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
LABEL='com.tradingindicator.liquidity'


def configuration(python,logs):
    return dict(Label=LABEL,ProgramArguments=[str(python),'-u','-m','Section_1_Global_Core.liquidity.runner'],
        WorkingDirectory=str(ROOT),RunAtLoad=True,KeepAlive=True,ThrottleInterval=15,
        EnvironmentVariables={'PYTHONUNBUFFERED':'1'},StandardOutPath=str(logs/'liquidity.log'),StandardErrorPath=str(logs/'liquidity-error.log'))



def launchctl(*arguments):
    return subprocess.run(['launchctl',*arguments],capture_output=True,text=True)


def restart_service(domain,path):
    """Wait for asynchronous removal before loading the replacement job."""
    service=f'{domain}/{LABEL}'
    unloaded=launchctl('bootout',service)
    for _ in range(100):
        if launchctl('print',service).returncode!=0:break
        time.sleep(.1)
    else:
        detail=(unloaded.stderr or unloaded.stdout).strip()
        raise SystemExit(f'Liquidity service is still registered after unload. {detail}\n'
                         f'Inspect: launchctl print {service}\nThe candle runner and UI were not restarted.')
    for args in (('enable',service),('bootstrap',domain,str(path)),('kickstart',service)):
        result=launchctl(*args)
        if result.returncode:
            detail=(result.stderr or result.stdout).strip()
            raise SystemExit(f'Liquidity launchctl {args[0]} failed ({result.returncode}): {detail}\n'
                f'Inspect: launchctl print {service}\n'
                f'Validate: plutil -lint "{path}"\n'
                'Check liquidity-error.log in ~/Library/Logs/TradingBotV1. '
                'Run this as your logged-in user; do not use sudo.')
    state=launchctl('print',service)
    if state.returncode:
        raise SystemExit('Liquidity service did not remain registered. Check liquidity-error.log.')


def main():
    if sys.platform!='darwin':raise SystemExit('Run python3 -m Section_1_Global_Core.liquidity.runner on non-macOS systems.')
    try:__import__('websocket')
    except ImportError:raise SystemExit('Install first: python3 -m pip install -r requirements-liquidity.txt')
    logs=Path.home()/'Library'/'Logs'/'TradingBotV1';logs.mkdir(parents=True,exist_ok=True)
    domain=f'gui/{os.getuid()}';service=f'{domain}/{LABEL}'
    path=Path.home()/'Library'/'LaunchAgents'/f'{LABEL}.plist';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(plistlib.dumps(configuration(Path(sys.executable).absolute(),logs)))
    restart_service(domain,path)
    print(f'Independent liquidity recorder enabled at login. Logs: {logs}/liquidity.log and liquidity-error.log')
    print('Observed USDT perpetual depth/trades only; collection stops during sleep or shutdown.')


if __name__=='__main__':main()
