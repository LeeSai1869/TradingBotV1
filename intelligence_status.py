"""Inspect readiness of all analytical engines without changing their state."""
import argparse
import json
import sqlite3
from pathlib import Path
import Section_1_Global_Core.intelligence_audit as audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols',nargs='+');parser.add_argument('--intervals',nargs='+')
    parser.add_argument('--max-pairs',type=int,default=1000);parser.add_argument('--output',type=Path);parser.add_argument('--summary',action='store_true')
    args=parser.parse_args()
    try:report=audit.report(args.symbols,args.intervals,max_pairs=args.max_pairs)
    except (ValueError,OSError,RuntimeError,sqlite3.Error) as error:parser.exit(1,str(error)+'\n')
    if args.output:args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    if args.summary:
        print('Analytical readiness; status does not establish predictive performance.')
        print('Selected symbols:',', '.join(report['symbols']))
        print('Selected timeframes:',', '.join(report['timeframes']))
        for engine,counts in report['counts'].items():print(engine,json.dumps(counts,sort_keys=True))
        print('Full-history calculation coverage (separate from live readiness):')
        for engine,counts in report['history_counts'].items():
            scopes=[pair['engines'][engine]['history'] for pair in report['pairs']]
            rows=sum(scope.get('classified_candles',0) for scope in scopes)
            pending=sum(scope.get('pending_candles',0) for scope in scopes)
            unknown=sum('pending_candles' not in scope for scope in scopes)
            print(engine,json.dumps(counts,sort_keys=True),f'classified={rows} pending={pending} scopes_without_target={unknown}')
        print('Pairs:',report['pairs_checked'],'of',report['pairs_requested'],'TRUNCATED' if report['truncated'] else '')
    else:print(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__':main()
