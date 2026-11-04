"""Inspect/export bounded research events from existing committed feature memory."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import Section_1_Global_Core.event_history as history


def utc(text):
    try:
        value=datetime.fromisoformat(text.replace('Z','+00:00'))
        if value.tzinfo is None:
            if len(text)!=10:raise ValueError('Include a timezone, or use a UTC date')
            value=value.replace(tzinfo=timezone.utc)
        return int(value.timestamp()*1000)
    except ValueError as error:raise argparse.ArgumentTypeError(str(error)) from error


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('symbol',nargs='?',default='BTCUSDT')
    parser.add_argument('--timeframe',choices=('1m','5m','15m','30m','1h'),default='5m');parser.add_argument('--bars',type=int,default=250)
    parser.add_argument('--before',type=utc);parser.add_argument('--output',type=Path);parser.add_argument('--summary',action='store_true');args=parser.parse_args()
    try:packet=history.history(args.symbol.upper(),args.timeframe,limit=args.bars,before=args.before)
    except (ValueError,OSError,RuntimeError,sqlite3.Error) as error:parser.exit(1,str(error)+'\n')
    if args.output:args.output.write_text(json.dumps(packet,indent=2,allow_nan=False)+'\n')
    if args.summary:
        print(packet['symbol'],packet['timeframe'],packet['status'],packet.get('reason',''))
        print('Events:',dict(Counter(event['type'] for event in packet['events'])))
        print(packet['interpretation']);print(packet['availability'])
    else:print(json.dumps(packet,indent=2,allow_nan=False))

if __name__=='__main__':main()
