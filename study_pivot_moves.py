"""Full committed-history pivot swing study; compressed, versioned research reports."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sqlite3
import sys
from Section_1_Global_Core import pivot_research
from inspect_events import utc


def spaced(cases,count):
    if not cases or count<=0:return []
    n=min(count,len(cases))
    return [cases[round(i*(len(cases)-1)/(n-1))] for i in range(n)] if n>1 else [cases[0]]


def push_report(path):
    """Publish only the explicitly generated report, never databases or other files."""
    root=Path(__file__).resolve().parent;path=path.resolve()
    try:relative=path.relative_to(root/'research_reports')
    except ValueError:raise ValueError('--push-report requires output under this project\'s research_reports folder')
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=root,text=True).strip()
    if branch!='main':raise ValueError('Report publishing expects main; report is saved locally. Switch to main before publishing.')
    relative=str(Path('research_reports')/relative)
    subprocess.run(['git','add','-f','--',relative],cwd=root,check=True)
    changed=subprocess.check_output(['git','diff','--cached','--name-only','--',relative],cwd=root,text=True).strip()
    if changed:subprocess.run(['git','commit','--only','-m','Record historical pivot move study','--',relative],cwd=root,check=True)
    subprocess.run(['git','push','origin','main'],cwd=root,check=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol',default='BTCUSDT');parser.add_argument('--timeframe',choices=pivot_research.TIMEFRAMES,default='15m')
    parser.add_argument('--since',type=utc,default=0);parser.add_argument('--until',type=utc)
    parser.add_argument('--horizon-bars',type=int,help='Optional alternative to the default next-opposite-pivot swing')
    parser.add_argument('--threshold-pct',type=float,default=1.)
    parser.add_argument('--before-bars',type=int,default=12);parser.add_argument('--after-bars',type=int,default=24)
    parser.add_argument('--context-cases',type=int,default=20,help='Evenly spaced successful cases plus an equal number of complete failures to embed with ALL feature columns; 0 disables')
    parser.add_argument('--report',type=Path,help='Existing study report for --case-id export')
    parser.add_argument('--case-id',help='Export full feature context for one case in --report instead of rescanning')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--push-report',action='store_true',help='Immediately commit only the output report and push origin main')
    args=parser.parse_args()
    if not 0<=args.before_bars<=100 or not 0<=args.after_bars<=100 or not 0<=args.context_cases<=100:parser.error('Context windows/case counts must be 0..100')
    try:
        if args.case_id:
            if not args.report:parser.error('--case-id requires --report')
            payload=args.report.read_bytes();study=json.loads(gzip.decompress(payload) if args.report.suffix=='.gz' else payload)
            case=next((c for c in study['cases'] if c['id']==args.case_id),None)
            if not case:raise ValueError('Case ID is not in the report')
            packet=pivot_research.case_context(study['symbol'],study['timeframe'],case['id'],case['pivot']['known_time'],source_id=study['source_id'],before=args.before_bars,after=args.after_bars,as_of=study['observed_as_of'])
        else:
            print('Scanning all committed pivot events; read-only, no runner or strategy changes.',flush=True)
            packet=pivot_research.scan(args.symbol.upper(),args.timeframe,since=args.since,until=args.until,horizon=args.horizon_bars,threshold=args.threshold_pct,progress=lambda status:print(status,flush=True))
            hits=[c for c in packet['cases'] if c['origin']['status']=='HIT']
            controls=[c for c in packet['cases'] if c['origin']['status']=='NO_HIT']
            chosen=spaced(hits,args.context_cases)+spaced(controls,args.context_cases)
            packet['context_config']=dict(before=args.before_bars,after=args.after_bars,sampling='Evenly spaced over ordered origin-HIT cases and complete origin-NO_HIT controls, separately; not all contexts are embedded')
            packet['contexts']={}
            for index,case in enumerate(chosen):
                print(f'Context {index+1}/{len(chosen)}',flush=True)
                packet['contexts'][case['id']]=pivot_research.case_context(packet['symbol'],packet['timeframe'],case['id'],case['pivot']['known_time'],source_id=packet['source_id'],before=args.before_bars,after=args.after_bars,as_of=packet['observed_as_of'])
        payload=(json.dumps(packet,separators=(',',':'),allow_nan=False)+'\n').encode()
        args.output.parent.mkdir(parents=True,exist_ok=True)
        if args.output.suffix=='.gz':payload=gzip.compress(payload,mtime=0)
        temp=args.output.with_name(args.output.name+'.partial');temp.write_bytes(payload);temp.replace(args.output)
        print(json.dumps(packet.get('summary',dict(bars=len(packet.get('bars',[])))),indent=2))
        print('Saved:',args.output.resolve(),f'({len(payload)} bytes)')
        if args.push_report:push_report(args.output)
    except (ValueError,OSError,RuntimeError,sqlite3.Error,subprocess.CalledProcessError) as error:parser.exit(1,str(error)+'\n')
    return 0

if __name__=='__main__':raise SystemExit(main())
