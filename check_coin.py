"""Read-only local registry and candle/feature progress, e.g. python3 check_coin.py ETHUSDT."""
import argparse
import json
import math
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys
from Section_1_Global_Core import data_policy, data_admin
from Section_1_Global_Core.memory_storage.Storage import klines_store, features_store


def stamp(value):
    return datetime.fromtimestamp(value/1000, timezone.utc).isoformat() if value is not None else 'none'


def verify_latest(symbol, interval, path=None, fetch=None):
    """Compare one committed local candle with the exchange at the SAME time."""
    path = Path(path or klines_store.DB_PATH)
    if not path.exists():
        return 'NO DATA', 'No local candle database'
    conn = sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
    try:
        row = conn.execute('SELECT open_time,open,high,low,close,volume,close_time FROM klines WHERE symbol=? AND interval=? ORDER BY open_time DESC LIMIT 1',(symbol,interval)).fetchone()
    finally:
        conn.close()
    if row is None:
        return 'NO DATA', 'No local candles for this pair'
    t = int(row[0])
    query = urlencode(dict(symbol=symbol,interval=interval,startTime=t,endTime=t+1,limit=1))
    request = Request('https://api.binance.com/api/v3/klines?'+query,headers={'User-Agent':'TradingBot-ReadOnlyCheck/1.0'})
    if fetch is None:
        with urlopen(request,timeout=8) as response:
            page = json.load(response)
    else:
        page = fetch(request)
    if not isinstance(page,list) or not page or int(page[0][0])!=t:
        return 'UNVERIFIED', f'Exchange did not return the exact stored candle at {stamp(t)}'
    remote = page[0]
    differences = []
    for index, name in enumerate(('open','high','low','close','volume'),1):
        expected, actual = float(remote[index]), float(row[index])
        if not math.isfinite(expected) or not math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-8):
            differences.append(f'{name}: local={actual:g}, exchange={expected:g}')
    if int(row[6]) != int(remote[6]):
        differences.append('close_time differs')
    label = 'MISMATCH' if differences else 'MATCH'
    return label, f'{stamp(t)} | local close={row[4]:g} | '+('; '.join(differences) if differences else 'OHLCV matches exchange for this timestamp')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('symbol',nargs='?',default='ETHUSDT')
    parser.add_argument('--verify',nargs='+',choices=data_policy.INTERVALS,help='Read-only exchange comparison of the latest stored candle for each selected timeframe')
    args=parser.parse_args(); symbol=args.symbol.upper()
    registry=data_admin.catalog()
    print(f'{symbol}: ' + ', '.join(key for key in ('approved','pending','staged','disapproved','top50') if any(r['symbol']==symbol for r in registry.get(key,[]))))
    print('Runner policy:', 'ACTIVE' if symbol in data_policy.active_symbols() else 'INACTIVE')
    if sys.platform=='darwin':
        result=subprocess.run(['launchctl','list'],capture_output=True,text=True)
        rows=[line.split() for line in result.stdout.splitlines() if line.split() and line.split()[-1]=='com.scalp.liverunner']
        print('Runner launchd PID:',rows[0][0] if rows else 'not loaded (a manual runner may still be running)')
    if sys.platform=='darwin' and not rows:
        print('To install/re-enable the login runner: python3 restart_runner.py')
    print('Run again in 30–60 seconds; increasing 1m counts/timestamps confirm progress; current timestamps can mean already caught up.')
    print('Timeframe   candles       latest candle UTC                 features      latest feature UTC')
    errors=set()
    for iv in data_policy.INTERVALS:
        values=[]
        for path,table in [(klines_store.DB_PATH,'klines'),(features_store.DB_PATH,'features')]:
            if not Path(path).exists(): values.append((0,None)); continue
            conn=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
            try: values.append(conn.execute(f'SELECT COUNT(*),MAX(open_time) FROM {table} WHERE symbol=? AND interval=?',(symbol,iv)).fetchone())
            except sqlite3.Error as error:
                values.append((0,None));errors.add(f'{Path(path).name}: {error}')
            finally: conn.close()
        (candles,t),(features,ft)=values
        print(f'{iv:6} {candles:10}  {stamp(t):32} {features:10}  {stamp(ft)}')
    for error in sorted(errors): print('Storage warning:',error)
    print('Fresh pairs download one 1000-bar page per cycle; features and other pairs share the same runner.')
    if Path(klines_store.DB_PATH).exists():
        conn=sqlite3.connect(Path(klines_store.DB_PATH).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
        try:
            print('Latest stored prices (compare dates before interpreting these as current prices):')
            for iv in args.verify or ['1m','5m','15m','1h','2h','4h']:
                row=conn.execute('SELECT open_time,close,close_time FROM klines WHERE symbol=? AND interval=? ORDER BY open_time DESC LIMIT 1',(symbol,iv)).fetchone()
                if row:
                    duration=max(1,row[2]-row[0]+1)
                    state='HISTORY BEHIND CURRENT TIME' if time.time()*1000-row[2]>2*duration else 'recent closed candle'
                    print(f'{iv:4} close={row[1]:g} at {stamp(row[0])} | {state}')
        finally: conn.close()
    if args.verify:
        print('Read-only verification: latest stored sample per timeframe, matched by timestamp. No data will be changed.')
        for iv in args.verify:
            try:
                result,detail=verify_latest(symbol,iv)
                print(f'{iv:4} {result}: {detail}')
            except (OSError,ValueError,TypeError,KeyError,IndexError,sqlite3.Error) as error:
                print(f'{iv:4} UNVERIFIED: {error}')
        print('MATCH verifies the displayed latest sample, not the entire historical dataset.')


if __name__=='__main__': main()
