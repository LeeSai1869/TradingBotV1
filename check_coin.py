"""Read-only local registry and candle/feature progress, e.g. python3 check_coin.py ETHUSDT."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys
from Section_1_Global_Core import data_policy, data_admin
from Section_1_Global_Core.memory_storage.Storage import klines_store, features_store


def stamp(value):
    return datetime.fromtimestamp(value/1000, timezone.utc).isoformat() if value is not None else 'none'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('symbol',nargs='?',default='ETHUSDT')
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


if __name__=='__main__': main()
