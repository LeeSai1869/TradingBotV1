"""Read-only local registry and candle/feature progress, e.g. python3 check_coin.py ETHUSDT."""
import argparse
import json
import math
import plistlib
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import subprocess
import sys
from restart_runner import LABEL, LEGACY_LABELS
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


def recorded_runner_start(project,pid):
    try:
        info=json.loads((Path(project)/'Section_1_Global_Core/section_1_9_state.json').read_text()).get('__runner__',{})
        if info.get('pid')!=int(pid) or Path(info.get('project','')).resolve()!=Path(project).resolve():return None
        return datetime.fromisoformat(info['started']).timestamp()
    except (OSError,ValueError,KeyError,TypeError):return None


def print_log_tail(path,count,*,runner_started=None):
    """Read a bounded tail and distinguish old stderr from this runner's errors."""
    try:
        modified=path.stat().st_mtime
        print(f'\nRecent {path.name} (last modified {datetime.fromtimestamp(modified,timezone.utc).isoformat()}; appended across starts):')
        if path.name=='runner-error.log' and runner_started is not None and modified<runner_started:
            print('No stderr updates since this runner started. Older errors remain in the log file.');return
        with path.open('rb') as stream:
            stream.seek(0,2);end=stream.tell();stream.seek(max(0,end-131072))
            lines=stream.read().decode('utf-8',errors='replace').splitlines()
        for line in lines[-count:]:print(line)
    except OSError as error:print(f'Cannot read {path}: {error}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('symbol',nargs='?',default='ETHUSDT')
    parser.add_argument('--verify',nargs='+',choices=data_policy.INTERVALS,help='Read-only exchange comparison of the latest stored candle for each selected timeframe')
    parser.add_argument('--logs',action='store_true',help='Include the recent local runner output and errors in this single diagnostic command')
    args=parser.parse_args(); symbol=args.symbol.upper()
    project=Path(__file__).resolve().parent
    print('Checked project:',project)
    print('Candle database:',Path(klines_store.DB_PATH).resolve())
    runner_started=None
    registry=data_admin.catalog()
    print(f'{symbol}: ' + ', '.join(key for key in ('approved','pending','staged','disapproved','top50') if any(r['symbol']==symbol for r in registry.get(key,[]))))
    print('Runner policy:', 'ACTIVE' if symbol in data_policy.active_symbols() else 'INACTIVE')
    if sys.platform=='darwin':
        result=subprocess.run(['launchctl','list'],capture_output=True,text=True)
        rows=[line.split() for line in result.stdout.splitlines() if line.split() and line.split()[-1] in {LABEL,*LEGACY_LABELS}]
        rows.sort(key=lambda row:row[-1]!=LABEL)
        for row in rows: print('Runner service:',row[-1],'PID:',row[0])
        if len(rows)>1: print('WARNING: multiple runner services are loaded. Run python3 restart_runner.py to consolidate them.')
        print('Runner launchd PID:',rows[0][0] if rows else 'not loaded (a manual runner may still be running)')
        if rows and rows[0][0].isdigit():
            started=subprocess.run(['ps','-p',rows[0][0],'-o','lstart='],capture_output=True,text=True).stdout.strip()
            try:runner_started=datetime.strptime(started,'%a %b %d %H:%M:%S %Y').timestamp()
            except ValueError:pass
            runner_started=recorded_runner_start(project,rows[0][0]) or runner_started
            if runner_started is not None:print('Runner started UTC:',datetime.fromtimestamp(runner_started,timezone.utc).isoformat())
            cwd=subprocess.run(['lsof','-a','-p',rows[0][0],'-d','cwd','-Fn'],capture_output=True,text=True)
            paths=[line[1:] for line in cwd.stdout.splitlines() if line.startswith('n')]
            print('Runner working folder:',paths[0] if paths else 'unknown')
            if paths and Path(paths[0]).resolve()!=project:
                print('WARNING: runner is in a DIFFERENT project folder. These counts may belong to another copy.')
        agents=Path.home()/'Library'/'LaunchAgents'
        plist=next((agents/f'{label}.plist' for label in [LABEL,*LEGACY_LABELS] if (agents/f'{label}.plist').exists()),agents/f'{LABEL}.plist')
        if plist.exists():
            try:
                installed=plistlib.loads(plist.read_bytes()).get('WorkingDirectory')
                print('Login runner configured folder:',installed or 'not set')
                if installed and Path(installed).resolve()!=project:
                    print('WARNING: login runner configuration points to a different or renamed project folder.')
            except (OSError,ValueError,TypeError) as error:
                print('Cannot read runner configuration:',error)

    if sys.platform=='darwin' and not rows:
        print('To install/re-enable the login runner: python3 restart_runner.py')
    print('Run again in 30–60 seconds; increasing 1m counts/timestamps confirm progress; current timestamps can mean already caught up.')
    print('The closest-to-completion symbol gets bulk priority; other active symbols receive bounded background download and feature turns.')
    print('Timeframe   candles       latest candle UTC                 features      latest feature UTC                  policy')
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
        print(f'{iv:6} {candles:10}  {stamp(t):32} {features:10}  {stamp(ft):32}  {"ACTIVE" if data_policy.enabled(symbol,iv) else "PAUSED"}')
    for error in sorted(errors): print('Storage warning:',error)
    print('Fresh pairs download one 1000-bar page per scheduled visit; bounded download and feature passes share the same runner.')
    if Path(klines_store.DB_PATH).exists():
        raw=sqlite3.connect(Path(klines_store.DB_PATH).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
        try:
            if raw.execute("SELECT 1 FROM sqlite_master WHERE name='history_progress'").fetchone():
                for interval,cursor in raw.execute('SELECT interval,next_open_time FROM history_progress WHERE symbol=?',(symbol,)):
                    print(f'{interval:6} historical download cursor: {stamp(cursor)} | recent candles refreshed separately; features do not skip this gap')
        finally:raw.close()
    if Path(features_store.DB_PATH).exists():
        conn=sqlite3.connect(Path(features_store.DB_PATH).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
        try:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_engine_state'").fetchone():
                checkpoints=conn.execute('SELECT interval,last_open_time FROM feature_engine_state WHERE symbol=?',(symbol,)).fetchall()
                if checkpoints:
                    print('Feature counts/latest timestamps can include older formulas; the following checkpoints show actual full replay progress.')
                    print('Complete formula-v3 replay checkpoints (older rows can still use previous formulas):')
                    raw=sqlite3.connect(Path(klines_store.DB_PATH).resolve().as_uri()+'?mode=ro',uri=True,timeout=5) if Path(klines_store.DB_PATH).exists() else None
                    try:
                        for interval,timestamp in checkpoints:
                            pending=raw.execute('SELECT COUNT(*) FROM klines WHERE symbol=? AND interval=? AND open_time>?',(symbol,interval,timestamp)).fetchone()[0] if raw else 'unknown'
                            status='ACTIVE' if data_policy.enabled(symbol,interval) else 'PAUSED by policy'
                            print(f'{interval:6} replayed through {stamp(timestamp)} | pending candles: {pending} | {status}')
                    finally:
                        if raw:raw.close()
                    print('Replay resumes automatically in batches after restart; live features wait for the closed checkpoint to catch up.')
                else:
                    print(f'No formula-v3 checkpoint committed for {symbol} yet. Existing feature counts describe older rows; this symbol is waiting for its first replay batch.')
            else:
                print('No formula-v3 checkpoint table yet. The runner has not initialized the new feature replay memory.')
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_replay_jobs'").fetchone():
                tasks=conn.execute('SELECT interval,last_time,target,columns FROM feature_replay_jobs WHERE symbol=?',(symbol,)).fetchall()
                if tasks:
                    print('Targeted feature recalculation (unrelated columns preserved):')
                    for interval,last,target,columns in tasks:
                        print(f'{interval:6} through {stamp(last) if last>=0 else "not started"}; target {stamp(target)}; columns: {columns}')

        finally:conn.close()
    if Path(klines_store.DB_PATH).exists():
        conn=sqlite3.connect(Path(klines_store.DB_PATH).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
        try:
            for (s,t),close in klines_store.first_close_waits(conn,int(time.time()*1000)).items():
                if s==symbol:print(f'{t}: source has only its first forming candle; first closed candle expected at {stamp(close+1)}')
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

    if args.logs:
        logs=Path.home()/'Library/Logs/TradingBotV1'
        for name,count in [('runner.log',80),('runner-error.log',60)]:
            print_log_tail(logs/name,count,runner_started=runner_started)



if __name__=='__main__': main()
