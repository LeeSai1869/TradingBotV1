"""Every BTC pivot on five timeframes, 1% until the next opposite pivot."""
import argparse
from pathlib import Path
import subprocess
import sys
from inspect_events import utc

FRAMES=('15m','30m','1h','4h','1d')

def commands(args):
    root=Path(__file__).resolve().parent
    for frame in args.timeframes:
        stem=args.output_dir/f'BTCUSDT_{frame}_all-history_1pct'
        cohort=stem.with_name(stem.name+'_pivots_v1.json.gz');comparison=stem.with_name(stem.name+'_features_v1.json.gz')
        first=[sys.executable,str(root/'study_pivot_moves.py'),'--symbol','BTCUSDT','--timeframe',frame,'--threshold-pct','1',
               '--before-bars',str(args.before_bars),'--after-bars',str(args.after_bars),'--context-cases','3','--output',str(cohort)]
        if args.until:first+=['--until',args.until]
        second=[sys.executable,str(root/'compare_pivot_features.py'),'--report',str(cohort),'--before-bars',str(args.before_bars),
                '--after-bars',str(args.after_bars),'--output',str(comparison)]
        if args.push_report:first+=['--push-report'];second+=['--push-report']
        yield frame,first,second


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=Path('research_reports/BTC_1pct'))
    p.add_argument('--timeframes',nargs='+',choices=FRAMES,default=list(FRAMES));p.add_argument('--until',help='Optional common UTC cutoff; otherwise freeze at batch start')
    p.add_argument('--before-bars',type=int,default=12);p.add_argument('--after-bars',type=int,default=24);p.add_argument('--push-report',action='store_true');a=p.parse_args()
    if not 0<=a.before_bars<=100 or not 0<=a.after_bars<=100:p.error('Choose 0..100 context bars')
    try:
        import numpy
        import os
        if hasattr(os,'nice'):os.nice(5)
        from datetime import datetime,timezone
        a.until=a.until or datetime.now(timezone.utc).isoformat();utc(a.until)
        for frame,first,second in commands(a):
            print(f'BTCUSDT {frame}: ALL pivots, 1% benchmark, common cutoff {a.until}',flush=True)
            subprocess.run(first,check=True);subprocess.run(second,check=True)
    except ImportError:p.exit(1,'Install optional research dependencies: python3 -m pip install -r requirements-research.txt\n')
    except (OSError,ValueError,subprocess.CalledProcessError) as error:p.exit(1,str(error)+'\nEarlier completed reports are preserved; this batch did not finish.\n')

if __name__=='__main__':main()
