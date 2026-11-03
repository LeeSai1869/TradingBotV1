"""Run bounded, independent Regime v1 history without changing live scheduling."""
import argparse
from datetime import datetime,timezone
import json
import sqlite3
import Section_1_Global_Core.data_policy as data_policy
import Section_1_Global_Core.regime_research as regime_research
from Section_5_Market_Regime.config import RegimeConfig


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols',nargs='+');parser.add_argument('--intervals',nargs='+')
    parser.add_argument('--max-bars',type=int,default=1000,help='Global work budget, 1–10000; processed in transactions of at most 200')
    parser.add_argument('--since',help='UTC ISO date/time; creates a separately seeded research run')
    parser.add_argument('--config',help='JSON RegimeConfig overrides; does not modify Section 2')
    parser.add_argument('--revision',default='initial',help='New identity after an out-of-band raw correction; preserves older runs')
    parser.add_argument('--summary',action='store_true');parser.add_argument('--diagnostics',action='store_true')
    args=parser.parse_args()
    try:
        symbols=sorted(set(args.symbols or data_policy.active_symbols()));intervals=list(dict.fromkeys(args.intervals or data_policy.active_intervals()))
        if any(iv not in data_policy.INTERVALS for iv in intervals):raise ValueError('Unsupported configured timeframe')
        pairs=[(s,iv) for s in symbols for iv in intervals]
        if not pairs:raise ValueError('No configured pairs')
        if not len(pairs)<=args.max_bars<=10000:raise ValueError('Budget must cover one candle per pair and be <=10000; select fewer pairs if needed')
        since=0
        if args.since:
            date=datetime.fromisoformat(args.since.replace('Z','+00:00'));since=int((date if date.tzinfo else date.replace(tzinfo=timezone.utc)).timestamp()*1000)
        if since<0:raise ValueError('History start must be >=1970')
        if not args.revision or len(args.revision)>200:raise ValueError('Revision must be 1–200 characters')
        from pathlib import Path
        cfg=RegimeConfig(**(json.loads(Path(args.config).read_text()) if args.config else {}))
        quota=args.max_bars//len(pairs);results=[]
        for symbol,interval in pairs:
            remaining=quota;processed=0
            while remaining>0:
                row=regime_research.catch_up(symbol,interval,limit=min(200,remaining),since=since,config=cfg,revision=args.revision)
                processed+=row['processed'];remaining-=row['processed']
                if not row['processed']:break
            row['processed']=processed
            if args.diagnostics and row.get('run_id'):row['diagnostics']=regime_research.diagnostics(row['run_id'])
            results.append(row)
        if args.summary:
            print('Regime v1 shadow history; no BUY/SELL or UI/scheduler changes.')
            for row in results:
                result=row.get('latest') or {};labels=result.get('classification') or {}
                stamp=datetime.fromtimestamp(result['candle_open_time']/1000,timezone.utc).isoformat() if result else 'unavailable'
                print(row['symbol'],row['timeframe'],'+'+str(row['processed']),row['status'],'through='+stamp,json.dumps(labels),result.get('data_quality',''),
                    'evidence='+str(result.get('confidence','unavailable')),'coverage='+str(result.get('coverage','unavailable')))
                if row.get('diagnostics'):print(json.dumps(row['diagnostics'],sort_keys=True))
        else:print(json.dumps(dict(engine='REGIME',version='1.0.0',mode='on-demand shadow',pairs=results),indent=2,allow_nan=False))
    except (ValueError,TypeError,OSError,RuntimeError,sqlite3.Error) as error:parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()
