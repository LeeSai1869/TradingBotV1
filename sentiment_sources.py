"""Opt-in normalized news/social source configuration, import and fetch. No polling."""
import argparse
import json
import sqlite3
from pathlib import Path
import Section_1_Global_Core.sentiment_external as sources


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    configure=sub.add_parser('configure');configure.add_argument('file',type=Path)
    ingest=sub.add_parser('import');ingest.add_argument('provider');ingest.add_argument('file',type=Path)
    fetch=sub.add_parser('fetch');fetch.add_argument('provider')
    status=sub.add_parser('status');status.add_argument('--symbol',default='BTCUSDT')
    args=parser.parse_args()
    try:
        if args.action=='configure':sources.configure(json.loads(args.file.read_text()));print('Provider configuration saved. No network call or automatic polling was started.')
        elif args.action=='import':print('New observations:',sources.import_records(args.provider,json.loads(args.file.read_text())))
        elif args.action=='fetch':print('New observations:',sources.fetch(args.provider))
        else:
            import time
            with sources.reader() as conn:rows=sources.project(conn,args.symbol,int(time.time()*1000))
            print(json.dumps(dict(symbol=args.symbol,observations=rows,note='No observations means unavailable, not neutral.'),indent=2,allow_nan=False))
    except (ValueError,TypeError,OSError,RuntimeError,sqlite3.Error) as error:parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()
