"""Read-only Mac app/server/runner process comparison. Run while reproducing lag."""
import argparse
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import time


def run(args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=10)
    return result.stdout.strip() or result.stderr.strip()


def snapshot():
    lines=run(['ps','-axo','pid=,ppid=,%cpu=,rss=,etime=,command=']).splitlines()
    terms=('Trading Indicator','scalp-indicator-app','WebKit','ui_server','live_runner','Section_15_Execution_Bot')
    return [line.strip() for line in lines if any(term in line for term in terms)]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seconds',type=int,default=10)
    args=parser.parse_args()
    if sys.platform!='darwin':parser.exit(2,'Run this diagnostic on the Mac hosting the app.\n')
    if not 1<=args.seconds<=30:parser.error('Use 1..30 seconds')
    print(json.dumps({'time_ms':int(time.time()*1000),'before':snapshot()}),flush=True)
    for name in ('chart','liverunner'):
        path=Path.home()/'Library/LaunchAgents'/f'com.tradingindicator.{name}.plist'
        if not path.exists():continue
        with path.open('rb') as f:config=plistlib.load(f)
        print(json.dumps(dict(service=name,working_directory=config.get('WorkingDirectory'),program_arguments=config.get('ProgramArguments'))),flush=True)
    time.sleep(args.seconds)
    print(json.dumps({'time_ms':int(time.time()*1000),'after':snapshot()}),flush=True)
    print('CPU is an OS recent average; RSS is KiB. Compare app/WebKit against server and runner. No service was changed.')


if __name__=='__main__':main()
