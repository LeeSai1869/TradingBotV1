"""Export macOS system-service configurations for review; never installs services."""
import argparse
import os
from pathlib import Path
import plistlib
import pwd
import sys

ROOT=Path(__file__).resolve().parent
SERVICES={
    'com.tradingindicator.liverunner':'Section_1_Global_Core.memory_storage.Runner.live_runner',
    'com.tradingindicator.backend':'Section_11_UI_UX.server.ui_server',
    'com.tradingindicator.liquidity':'Section_1_Global_Core.liquidity.runner',
}


def configuration(label,module,*,username,home,python,root=ROOT):
    logs=Path(home)/'Library'/'Logs'/'TradingBotV1'
    name={'com.tradingindicator.liverunner':'runner','com.tradingindicator.backend':'backend','com.tradingindicator.liquidity':'liquidity'}[label]
    return {'Label':label,'UserName':username,'ProgramArguments':[str(python),'-u','-m',module],
        'WorkingDirectory':str(root),'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':15,
        'EnvironmentVariables':{'HOME':str(home),'PYTHONUNBUFFERED':'1'},
        'StandardOutPath':str(logs/f'{name}.log'),'StandardErrorPath':str(logs/f'{name}-error.log')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--user',default=pwd.getpwuid(os.getuid()).pw_name)
    parser.add_argument('--python',type=Path,default=Path(sys.executable).resolve())
    args=parser.parse_args();account=pwd.getpwnam(args.user)
    if account.pw_uid==0:parser.error('Choose a normal account; market services must not run as root')
    if not args.python.is_absolute() or not args.python.is_file():parser.error('Choose an existing absolute Python executable')
    args.output.mkdir(parents=True,exist_ok=True)
    for label,module in SERVICES.items():
        path=args.output/f'{label}.plist'
        path.write_bytes(plistlib.dumps(configuration(label,module,username=args.user,home=account.pw_dir,python=args.python)))
        print(path)
    print('Exported only. Review SERVER_MODE.md before installing; do not run system and login copies together.')

if __name__=='__main__':main()
