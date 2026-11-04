"""Study saved analytical direction outputs without altering live trading rules."""
import argparse
from datetime import datetime,timezone
import json
import sqlite3
from pathlib import Path
import Section_1_Global_Core.intelligence_evaluation as research


def timestamp(text):
    try:
        date=datetime.fromisoformat(text.replace('Z','+00:00'))
        if date.tzinfo is None:
            if len(text)!=10:raise ValueError('Datetime needs timezone; date-only is UTC midnight')
            date=date.replace(tzinfo=timezone.utc)
        return int(date.timestamp()*1000)
    except ValueError as error:raise argparse.ArgumentTypeError(str(error)) from error


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine',default='BIAS',choices=['BIAS','TREND','STRUCTURE','MOMENTUM','REGIME'])
    parser.add_argument('--symbols',nargs='+');parser.add_argument('--intervals',nargs='+');parser.add_argument('--horizons',type=int,nargs='+',default=[1,3,6])
    parser.add_argument('--cost-bps',type=float,default=12.);parser.add_argument('--since',type=timestamp);parser.add_argument('--until',type=timestamp);parser.add_argument('--split-at',type=timestamp)
    parser.add_argument('--reconstructed-close',action='store_true');parser.add_argument('--every-close',action='store_true')
    parser.add_argument('--min-confidence',type=float,default=0.);parser.add_argument('--min-coverage',type=float,default=0.)
    parser.add_argument('--max-rows',type=int,default=100000);parser.add_argument('--max-events',type=int,default=20000)
    parser.add_argument('--output',type=Path);parser.add_argument('--summary',action='store_true');args=parser.parse_args()
    try:
        report=research.evaluate(args.symbols,args.intervals,engine=args.engine,horizons=tuple(sorted(set(args.horizons))),cost_bps=args.cost_bps,since=args.since,until=args.until,split=args.split_at,
            availability='RECONSTRUCTED_CLOSE' if args.reconstructed_close else 'ACTUAL',event_mode='EVERY_CLOSE' if args.every_close else 'TRANSITIONS',min_confidence=args.min_confidence,min_coverage=args.min_coverage,max_rows=args.max_rows,max_events=args.max_events)
    except (ValueError,OSError,RuntimeError,sqlite3.Error) as error:parser.exit(1,str(error)+'\n')
    if args.output:args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    if args.summary:
        print(report['method']);print('Publication policy:',report['parameters']['availability'],'; assumed costs:',args.cost_bps,'bps')
        for pair in report['pairs']:
            print(pair['symbol'],pair['timeframe'],pair['status'],pair.get('conclusion',''), 'TRUNCATED' if pair.get('truncated') else '')
            for group in pair.get('groups',[]):print(' ',group['period'],group['direction'],'bars='+str(group['horizon_bars']),'N='+str(group['observations']),'gross_bps='+str(round(group['mean_gross_bps'],3)),'net_bps='+str(round(group['mean_net_bps'],3)))
    else:print(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__':main()
