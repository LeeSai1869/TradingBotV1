"""Verified, resumable ATR slope retirement. Default: bounded read-only dry run."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time

from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import features_store as store,klines_store
from Section_1_Global_Core.memory_storage.Storage import atr_slope_reads as slopes

JOB = 'atr_slopes_v1'
COUNTERS = ('rows_checked','rows_cleared','values_cleared','values_retained')


def sources():
    result = {}
    for name,path in (('features',store.DB_PATH),('raw',klines_store.DB_PATH)):
        stat = path.stat()
        result[name] = dict(path=str(path.resolve()),device=stat.st_dev,inode=stat.st_ino)
    return result


def load_state(conn):
    row = conn.execute('SELECT state FROM feature_storage_retirements WHERE name=?',(JOB,)).fetchone()
    return json.loads(row[0]) if row else None


def start(conn):
    """Initialize metadata only after proving that current writes omit slopes."""
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('CREATE TABLE IF NOT EXISTS feature_storage_retirements '
                     '(name TEXT PRIMARY KEY,state TEXT NOT NULL)')
        old = load_state(conn)
        if old is not None:
            if old['sources']!=sources():
                raise RuntimeError('Source database changed; refusing stale cleanup progress')
            if old['complete']:
                return old
        recent = conn.execute('SELECT symbol,interval,open_time,'+','.join(slopes.FIELDS)+
            ' FROM features WHERE formula_version=3 ORDER BY rowid DESC LIMIT 3').fetchall()
        lengths = slopes.known_lengths(conn)
        ready = 0
        for row in recent:
            derived = slopes.read_values(conn,*row[:3],lengths)
            ready += len(derived)
            if any(old_value is not None for field,old_value in zip(slopes.FIELDS,row[3:]) if field in derived):
                raise RuntimeError('Recent writes still store reconstructible ATR slopes. '
                                   'Restart the writer, wait for new rows, and retry; no historical values cleared.')
        if not ready:
            raise RuntimeError('Cannot verify current writer output; no historical values cleared')
        if old is not None:
            return old
        state = dict(version=1,sources=sources(),target_rowid=conn.execute(
            'SELECT max(rowid) FROM features').fetchone()[0] or 0,last_rowid=0,
            **dict.fromkeys(COUNTERS,0),complete=False)
        conn.execute('INSERT INTO feature_storage_retirements VALUES (?,?)',(JOB,json.dumps(state)))
    return state


def advance(conn,batch_size=500):
    """Commit verified clears and the exact progress cursor atomically."""
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        state = load_state(conn)
        if state is None:
            raise RuntimeError('Cleanup job is not initialized')
        if state['sources']!=sources():
            raise RuntimeError('Source database changed; batch unchanged')
        if state['complete']:
            return state
        slopes.register_configurations(conn)
        rows = conn.execute('SELECT rowid,symbol,interval,open_time FROM features '
            'WHERE rowid>? AND rowid<=? ORDER BY rowid LIMIT ?',
            (state['last_rowid'],state['target_rowid'],batch_size)).fetchall()
        report = slopes.clear_verified(conn,[row[1:] for row in rows],
                                       slopes.known_lengths(conn),apply=True)
        state['last_rowid'] = rows[-1][0] if rows else state['target_rowid']
        for key in COUNTERS:
            state[key] += report[key]
        state['complete'] = state['last_rowid']>=state['target_rowid']
        if state['complete']:
            state['finished_at'] = time.time()
        conn.execute('UPDATE feature_storage_retirements SET state=? WHERE name=?',
                     (json.dumps(state),JOB))
    return state


def mirror(state):
    path=Path('research_reports/storage_consolidation/atr_slope_retirement.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,indent=2))
    temporary.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--apply',action='store_true',help='Clear verified history; keep columns and unresolved values')
    mode.add_argument('--dry-run',action='store_true',help='Read-only sample (default)')
    mode.add_argument('--status',action='store_true',help='Read committed cleanup progress without scanning history')
    parser.add_argument('--limit',type=int,default=1000,help='Dry-run sample size')
    parser.add_argument('--latest',action='store_true',help='Sample latest rows instead of earliest rows')
    parser.add_argument('--batch-size',type=int,default=500)
    args=parser.parse_args()
    if not 1<=args.limit<=10000 or not 1<=args.batch_size<=1000:
        parser.error('Use limit 1..10000 and batch size 1..1000')
    if (args.apply or args.status) and args.latest:
        parser.error('--latest is only for dry runs')
    if args.status:
        with closing(sqlite3.connect(store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)) as conn:
            conn.execute('PRAGMA query_only=ON')
            exists=conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_storage_retirements'").fetchone()
            state=load_state(conn) if exists else None
        print(json.dumps(dict(state=state,sources_match=bool(state and state['sources']==sources())),indent=2),flush=True)
        return
    if not args.apply:
        with closing(sqlite3.connect(store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=5)) as conn:
            if not slopes.install(conn):
                parser.error('Raw candle store is unavailable')
            conn.execute('PRAGMA query_only=ON');conn.execute('BEGIN')
            order='DESC' if args.latest else 'ASC'
            rows=conn.execute('SELECT symbol,interval,open_time FROM features ORDER BY rowid '+order+' LIMIT ?',
                              (args.limit,)).fetchall()
            report=slopes.clear_verified(conn,rows,slopes.known_lengths(conn),apply=False)
        print(json.dumps(dict(mode='dry_run',would_clear_rows=report['rows_cleared'],
            would_clear_values=report['values_cleared'],values_retained=report['values_retained'],
            rows_checked=report['rows_checked'])),flush=True)
        print('No database values or settings changed.')
        return
    with closing(store.open_db()) as conn:
        if not slopes.install(conn):
            parser.error('Raw candle store is unavailable')
        with data_policy.locked(timeout=2):
            state=start(conn)
        print(json.dumps(state),flush=True)
        printed=time.monotonic()
        while not state['complete']:
            try:
                with data_policy.locked(timeout=.1):
                    state=advance(conn,args.batch_size)
            except TimeoutError:
                time.sleep(.05);continue
            except sqlite3.OperationalError as error:
                if getattr(error,'sqlite_errorcode',None) not in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED):
                    raise
                time.sleep(.1);continue
            if state['complete'] or time.monotonic()-printed>=15:
                mirror(state);print(json.dumps(state),flush=True);printed=time.monotonic()
            time.sleep(.01)
        mirror(state)
        print('Cleanup complete. Physical columns and unresolved values retained.',flush=True)


if __name__=='__main__':
    main()
