"""Read-only BTC event-sequence report using the same simulation as the chart."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from Section_1_Global_Core.btc_strategy_history import history


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeframe',choices=('5m','15m','30m','1h'),default='15m')
    parser.add_argument('--days',type=int,choices=(7,30,90,365),default=90)
    parser.add_argument('--before',help='Optional exclusive UTC close boundary, ISO with timezone')
    parser.add_argument('--output',default='btc_strategy_review.json')
    args=parser.parse_args();before=None
    if args.before:
        try:
            point=datetime.fromisoformat(args.before.replace('Z','+00:00'))
            if point.tzinfo is None:raise ValueError('Include a timezone offset')
            before=int(point.timestamp()*1000)
        except ValueError as error:parser.error(str(error))
    packet=history('BTCUSDT',args.timeframe,days=args.days,before=before)
    Path(args.output).write_text(json.dumps(packet,indent=2,allow_nan=False),encoding='utf-8')
    print('BTCUSDT',args.timeframe,packet.get('version',''),packet['status'])
    print(json.dumps(packet.get('summary') or dict(reason=packet.get('reason')),sort_keys=True))
    print('Saved:',Path(args.output).resolve())
    print('Summary spans the selected history; detailed events/levels are the recent chart tail. Simulated results are not live trading performance.')
    return 0 if packet['status']=='READY' else 1

if __name__=='__main__':raise SystemExit(main())
