"""Retire verified cheap Trend values online; never delete a candle/checkpoint."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time

from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import features_store as store


def clear_batch(conn,after_rowid,*,limit=1000):
    physical={r[1] for r in conn.execute('PRAGMA table_xinfo(features)') if r[6]==0}
    fields=[f for f in store.FORMULA_COLUMNS if f in physical]
    report=dict(last_rowid=after_rowid,scanned=0,rows_cleared=0,values_cleared=0,legacy_values_retained=0)
    if not fields:return report
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        rows=conn.execute('SELECT rowid,formula_version,'+','.join('f.'+f for f in fields)+','+
            ','.join(store.read_expression(f,preserve_legacy=False) for f in fields)+
            ' FROM features f WHERE rowid>? ORDER BY rowid LIMIT ?',(after_rowid,limit)).fetchall()
        groups={};n=len(fields)
        for row in rows:
            rowid,version=row[:2];old=row[2:2+n];derived=row[2+n:]
            clear=[]
            for name,value,expected in zip(fields,old,derived):
                if value is None:continue
                if value!=expected:
                    if version==3:raise ValueError(f'Trend formula mismatch at rowid {rowid}: {name}; batch rolled back')
                    report['legacy_values_retained']+=1;continue
                clear.append(name)
            if clear:
                groups.setdefault(tuple(clear),[]).append(rowid)
                report['rows_cleared']+=1;report['values_cleared']+=len(clear)
            report['scanned']+=1;report['last_rowid']=rowid
        for names,ids in groups.items():
            conn.execute('UPDATE features SET '+','.join(f+'=NULL' for f in names)+
                ' WHERE rowid IN ('+','.join('?' for _ in ids)+')',ids)
            remaining=conn.execute('SELECT rowid FROM features WHERE rowid IN ('+','.join('?' for _ in ids)+
                ') AND ('+' OR '.join(f+' IS NOT NULL' for f in names)+') LIMIT 1',ids).fetchone()
            if remaining:raise RuntimeError('Trend retirement read-back failed')
    return report


def main():
    path=store.DB_PATH.resolve();progress=Path('Section_12_Research/reports/storage_consolidation/trend_storage_retirement.json')
    progress.parent.mkdir(parents=True,exist_ok=True)
    state=json.loads(progress.read_text()) if progress.exists() else dict(source_inode=path.stat().st_ino,
        last_rowid=0,scanned=0,rows_cleared=0,values_cleared=0,legacy_values_retained=0,complete=False)
    if state['source_inode']!=path.stat().st_ino:raise RuntimeError('Feature database changed; refusing stale cursor')
    with closing(sqlite3.connect(path.as_uri()+'?mode=rw',uri=True,timeout=2)) as conn:
        conn.execute('PRAGMA cache_size=-16384')
        target=state.get('target_rowid') or conn.execute('SELECT max(rowid) FROM features').fetchone()[0]
        state['target_rowid']=target;last_print=0
        while state['last_rowid']<target:
            try:
                with data_policy.locked(timeout=.05):batch=clear_batch(conn,state['last_rowid'])
            except TimeoutError:time.sleep(.05);continue
            state['last_rowid']=batch['last_rowid']
            for key in ('scanned','rows_cleared','values_cleared','legacy_values_retained'):state[key]+=batch[key]
            if not batch['scanned']:break
            temp=progress.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2));temp.replace(progress)
            now=time.monotonic()
            if now-last_print>=15:print(json.dumps(state),flush=True);last_print=now
            time.sleep(.03)
        state['complete']=True
        state['sqlite_free_GiB']=round(conn.execute('PRAGMA freelist_count').fetchone()[0]*conn.execute('PRAGMA page_size').fetchone()[0]/1024**3,3)
        temp=progress.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2));temp.replace(progress)
        print(json.dumps(state),flush=True)


if __name__=='__main__':main()
