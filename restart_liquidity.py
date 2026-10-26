"""Install/restart the independent macOS perpetual-liquidity login recorder."""
from pathlib import Path
import os
import plistlib
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
LABEL='com.tradingindicator.liquidity'


def configuration(python,logs):
    return dict(Label=LABEL,ProgramArguments=[str(python),'-u','-m','Section_1_Global_Core.liquidity.runner'],
        WorkingDirectory=str(ROOT),RunAtLoad=True,KeepAlive=True,ThrottleInterval=15,
        EnvironmentVariables={'PYTHONUNBUFFERED':'1'},StandardOutPath=str(logs/'liquidity.log'),StandardErrorPath=str(logs/'liquidity-error.log'))


def main():
    if sys.platform!='darwin':raise SystemExit('Run python3 -m Section_1_Global_Core.liquidity.runner on non-macOS systems.')
    try:__import__('websocket')
    except ImportError:raise SystemExit('Install first: python3 -m pip install -r requirements-liquidity.txt')
    logs=Path.home()/'Library'/'Logs'/'TradingBotV1';logs.mkdir(parents=True,exist_ok=True)
    domain=f'gui/{os.getuid()}';service=f'{domain}/{LABEL}'
    subprocess.run(['launchctl','bootout',service],capture_output=True)
    path=Path.home()/'Library'/'LaunchAgents'/f'{LABEL}.plist';path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(plistlib.dumps(configuration(Path(sys.executable).absolute(),logs)))
    for command in (['launchctl','enable',service],['launchctl','bootstrap',domain,str(path)],['launchctl','kickstart',service]):subprocess.run(command,check=True)
    print(f'Independent liquidity recorder enabled at login. Logs: {logs}/liquidity.log and liquidity-error.log')
    print('Observed USDT perpetual depth/trades only; collection stops during sleep or shutdown.')


if __name__=='__main__':main()
