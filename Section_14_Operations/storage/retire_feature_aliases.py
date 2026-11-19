"""Rebuild feature storage with 24 virtual aliases, preserving legacy values.

Run only with the feature writer stopped. The original is retained until every
stored value, checkpoint table and SQLite structure has been verified.
"""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
from unittest.mock import patch

from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import features_store as store


def migrate(path,*,report=None):
    path=Path(path).resolve();target=path.with_name('features.canonical.pending.db')
    backup=path.with_name('features.pre-alias-retirement.db')
    report=Path(report or 'Section_12_Research/reports/storage_consolidation/alias_retirement.json')
    report.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() or backup.exists():raise RuntimeError('Migration files already exist; inspect before retrying')
    if shutil.disk_usage(path.parent).free<path.stat().st_size+8*1024**3:
        raise RuntimeError('Insufficient verified working space for feature rebuild')
    with data_policy.locked(),closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)) as source:
        info=source.execute('PRAGMA table_xinfo(features)').fetchall()
        if all(next(r for r in info if r[1]==a)[6]==2 for a in store.STORAGE_ALIASES):
            print('Aliases are already virtual.',flush=True);return
        pairs=store.STORAGE_ALIASES
        conflict=' OR '.join(f'({a} IS NOT NULL AND {s} IS NOT NULL AND {a} IS NOT {s})' for a,s in pairs.items())
        print('Checking all legacy alias pairs for conflicting populated values.',flush=True)
        bad=source.execute('SELECT rowid FROM features WHERE '+conflict+' LIMIT 1').fetchone()
        if bad:raise RuntimeError('Conflicting legacy values at rowid '+str(bad[0])+'; original unchanged')
        with patch.object(store,'DB_PATH',target):
            output=store.open_db();output.close()
        with closing(sqlite3.connect(target.as_uri()+'?mode=rw',uri=True,timeout=5)) as out:
            out.execute('PRAGMA cache_size=-65536')
            out.execute('ATTACH DATABASE ? AS old',(path.as_uri()+'?mode=ro',))
            columns=store.storage_columns(out)
            reverse={s:a for a,s in pairs.items()}
            expression=lambda c,prefix: f'COALESCE({prefix}.{c},{prefix}.{reverse[c]})' if c in reverse else f'{prefix}.{c}'
            last=0;count=0;started=time.monotonic()
            while True:
                ids=out.execute('SELECT rowid FROM old.features WHERE rowid>? ORDER BY rowid LIMIT 10000',(last,)).fetchall()
                if not ids:break
                end=ids[-1][0]
                with out:
                    out.execute('INSERT INTO features(rowid,'+','.join(columns)+') SELECT f.rowid,'+
                        ','.join(expression(c,'f') for c in columns)+' FROM old.features f WHERE f.rowid>? AND f.rowid<=?',(last,end))
                    copied=out.execute('SELECT COUNT(*) FROM features WHERE rowid>? AND rowid<=?',(last,end)).fetchone()[0]
                    if copied!=len(ids):raise RuntimeError('Feature batch count mismatch')
                count+=copied;last=end
                if count%100000==0:print(json.dumps(dict(stage='copy',rows=count,last_rowid=last,seconds=round(time.monotonic()-started))),flush=True)
            tables=[r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='features'")]
            for table in tables:
                schema=source.execute('SELECT sql FROM sqlite_master WHERE name=?',(table,)).fetchone()[0]
                with out:
                    out.execute('DROP TABLE IF EXISTS main."'+table+'"');out.execute(schema)
                    out.execute('INSERT INTO main."'+table+'" SELECT * FROM old."'+table+'"')
                if out.execute('SELECT * FROM main."'+table+'"').fetchall()!=source.execute('SELECT * FROM "'+table+'"').fetchall():
                    raise RuntimeError('Checkpoint/auxiliary table mismatch: '+table)
            print('Verifying every canonical feature value against its original.',flush=True)
            mismatch=' OR '.join('n.'+c+' IS NOT '+expression(c,'o') for c in columns)
            bad=out.execute('SELECT o.rowid FROM old.features o JOIN main.features n ON n.rowid=o.rowid WHERE '+mismatch+' LIMIT 1').fetchone()
            if bad:raise RuntimeError('Feature value mismatch at rowid '+str(bad[0]))
            print('Checking rebuilt SQLite structure.',flush=True)
            if out.execute('PRAGMA main.quick_check').fetchall()!=[('ok',)]:raise RuntimeError('SQLite verification failed')
            actual={r[1]:r[6] for r in out.execute('PRAGMA main.table_xinfo(features)')}
            if not all(actual[a]==2 for a in pairs):raise RuntimeError('Alias still physically stored')
            out.execute('DETACH DATABASE old')
        before=path.stat().st_size;after=target.stat().st_size
        os.link(path,backup)
        os.replace(target,path)
        result=dict(complete=True,rows_verified=count,source_max_rowid=last,virtual_aliases=24,unresolved_fields_preserved=True,
            original_bytes=before,new_bytes=after,backup=str(backup),finished_at=time.time())
        report.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


if __name__=='__main__':migrate(store.DB_PATH)
