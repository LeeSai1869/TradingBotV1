"""Preview or replace duplicate result JSON with checksums in bounded batches.

The full result, input bundles, runs and checkpoints are preserved. This command
does not VACUUM or promise an immediate reduction in the database's file size.
"""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import json
from pathlib import Path
import time

from Section_1_Global_Core.memory_storage.Storage import engine_store
from Section_1_Global_Core.memory_storage.Storage import json_storage


def compact_batch(conn, *, after_rowid=0, limit=200, apply=False):
    if after_rowid<0 or not 1<=limit<=1000:
        raise ValueError('Use a nonnegative cursor and a batch size from 1 to 1000')
    if conn.in_transaction:
        raise RuntimeError('Checksum cleanup needs its own transaction')
    report=dict(scanned=0,duplicates=0,updated=0,json_bytes_removed=0,last_rowid=after_rowid)
    with conn:
        # A small writer transaction protects the verification/update pair. A
        # preview remains read-only and never creates or migrates schema.
        if apply:conn.execute('BEGIN IMMEDIATE')
        rows=conn.execute('''SELECT rowid,deterministic,
            CASE WHEN substr(deterministic,1,7)='sha256:' THEN NULL ELSE payload END
            FROM engine_results WHERE rowid>? ORDER BY rowid LIMIT ?''',
            (after_rowid,limit)).fetchall()
        for rowid,stored,payload in rows:
            report['scanned']+=1;report['last_rowid']=rowid
            if payload is None:continue
            result=json.loads(payload)
            if stored!=engine_store.encode(engine_store.stable_result(result)):
                raise ValueError(f'Result/check copy mismatch at rowid {rowid}; batch rolled back')
            checksum=engine_store.result_checksum(result)
            report['duplicates']+=1
            report['json_bytes_removed']+=len(stored.encode())-len(checksum)
            if apply:
                conn.execute('UPDATE engine_results SET deterministic=? WHERE rowid=?',(checksum,rowid))
                report['updated']+=1
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,default=engine_store.DB_PATH)
    parser.add_argument('--apply',action='store_true',help='Replace verified duplicate JSON; default is read-only preview')
    parser.add_argument('--after-rowid',type=int,default=0,help='Resume after the last committed cursor printed by this command')
    parser.add_argument('--batch-size',type=int,default=200)
    parser.add_argument('--max-rows',type=int,default=2000,help='Maximum rows inspected in this invocation')
    parser.add_argument('--time-budget',type=float,default=5.,help='Soft seconds limit, checked between batches')
    args=parser.parse_args(argv)
    if args.after_rowid<0 or not 1<=args.batch_size<=1000 or args.max_rows<1 or not 0<args.time_budget<=60:
        parser.error('Require cursor >= 0, batch size 1..1000, max rows >= 1, and time budget > 0 and <= 60')
    path=args.database.expanduser().resolve()
    conn=json_storage.connect(path,readonly=not args.apply,timeout=2)
    total=dict(scanned=0,duplicates=0,updated=0,json_bytes_removed=0,last_rowid=args.after_rowid)
    started=time.monotonic()
    try:
        while total['scanned']<args.max_rows and time.monotonic()-started<args.time_budget:
            batch=compact_batch(conn,after_rowid=total['last_rowid'],
                limit=min(args.batch_size,args.max_rows-total['scanned']),apply=args.apply)
            total['last_rowid']=batch['last_rowid']
            for key in ('scanned','duplicates','updated','json_bytes_removed'):total[key]+=batch[key]
            print(json.dumps(dict(mode='apply' if args.apply else 'preview',**total)),flush=True)
            if not batch['scanned']:break
    finally:
        conn.close()
    print('Resume with --after-rowid '+str(total['last_rowid'])+'. File shrinking requires separate compaction.',flush=True)


if __name__=='__main__':main()
