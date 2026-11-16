"""Verified, resumable Section 5 transfer into the existing ADCN database.

Only Section 5 tables are created/inserted. Existing ADCN decisions/evidence are
never rewritten. Every batch is read back through the lossless codec before its
progress marker commits. The source is never deleted by this module.
"""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import time

from .memory_storage.Storage import engine_store,json_storage

JSON_COLUMNS={
    'engine_runs':('metadata','state'),
    'engine_input_bundles':('payload',),
    'engine_results':('payload',),
    'engine_live_seeds':(),
    'mtf_bindings':('metadata',),
    'mtf_sources':('payload',),
    'mtf_scopes':('metadata',),
    'mtf_input_bundles':('payload',),
    'mtf_results':('payload',),
    'mtf_latest':(),
    'engine_history_bindings':('metadata',),
}


def fingerprint(path):
    stat=path.stat()
    with path.open('rb') as stream:header=stream.read(100)
    return dict(path=str(path),device=stat.st_dev,inode=stat.st_ino,size=stat.st_size,
        modified_ns=stat.st_mtime_ns,header=header.hex())


def recover_source(path):
    """Let SQLite recover a stopped writer's journal before pinning the source."""
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=rw',uri=True,timeout=5)) as conn:
        conn.execute('SELECT name FROM sqlite_master LIMIT 1').fetchall()
        if conn.execute('PRAGMA journal_mode').fetchone()[0]=='wal':
            result=conn.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
            if result[0]:raise RuntimeError('Source WAL is busy; stop all source writers first')


class Migration:
    def __init__(self,source,destination,*,reserve_bytes=8*1024**3):
        self.source_path=Path(source).expanduser().resolve()
        self.destination_path=Path(destination).expanduser().resolve()
        if self.source_path==self.destination_path:raise ValueError('Source and destination must differ')
        if not self.source_path.is_file():raise FileNotFoundError(self.source_path)
        self.reserve_bytes=reserve_bytes
        self.source=json_storage.connect(self.source_path,readonly=True)
        self.dest=None
        try:
            self.source.execute('PRAGMA cache_size=-65536')
            present={r[0] for r in self.source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'engine_runs','engine_input_bundles','engine_results'}<=present:
                raise ValueError('Source does not contain Section 5 history')
            unknown=present-set(JSON_COLUMNS)
            if unknown:raise ValueError('Unrecognized source tables; refusing to omit them: '+', '.join(sorted(unknown)))
            self.tables=[name for name in JSON_COLUMNS if name in present]
            self.pinned=fingerprint(self.source_path)
            self.destination_path.parent.mkdir(parents=True,exist_ok=True)
            self.dest=json_storage.connect(self.destination_path,compact=True)
            self.dest.execute('PRAGMA foreign_keys=ON')
            self.dest.execute('PRAGMA cache_size=-65536')
            existing={r[0] for r in self.dest.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if '_section5_migration' not in existing and existing.intersection(self.tables):
                raise ValueError('Destination already contains Section 5 tables without migration provenance')
            self.dest.execute('CREATE TABLE IF NOT EXISTS _section5_migration (name TEXT PRIMARY KEY,value TEXT NOT NULL)')
            self.dest.commit()
            saved=self.get('source')
            if saved and saved!=self.pinned:raise RuntimeError('Source changed since migration began; refusing an inconsistent resume')
            if not saved:
                with self.dest:self.put('source',self.pinned)
            for table in self.tables:
                if table not in existing:
                    sql=self.source.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()[0]
                    self.dest.execute(sql)
            self.dest.commit()
            json_storage.create_schema(self.dest)
            self.columns={table:[r[1] for r in self.source.execute('PRAGMA table_info('+table+')')] for table in self.tables}
            self.dictionaries=dict(self.dest.execute('SELECT run_id,dictionary_id FROM _section5_run_dictionaries'))
            self.signatures={}
            for run_id,metadata in self.dest.execute('SELECT run_id,metadata FROM engine_runs'):
                if run_id in self.dictionaries:self.signatures[json.loads(metadata)['input_signature']]=self.dictionaries[run_id]
        except BaseException:
            self.close();raise

    def close(self):
        self.source.close()
        if self.dest is not None:self.dest.close()

    def get(self,name):
        row=self.dest.execute('SELECT value FROM _section5_migration WHERE name=?',(name,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self,name,value):
        self.dest.execute('INSERT INTO _section5_migration VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value',
            (name,json.dumps(value,sort_keys=True,separators=(',',':'))))

    def seed_run(self,run_id,metadata):
        if run_id in self.dictionaries:return self.dictionaries[run_id]
        first=self.source.execute('''SELECT b.payload,r.payload FROM engine_results r
            JOIN engine_input_bundles b USING(bundle_id) WHERE r.run_id=? ORDER BY r.candle_time LIMIT 1''',(run_id,)).fetchone()
        if not first:return None
        seed=first[0]+'\n'+engine_store.encode(engine_store.stable_result(json.loads(first[1])))
        key=json_storage.seed_dictionary(self.dest,run_id,seed.encode())
        self.dictionaries[run_id]=key
        self.signatures[json.loads(metadata)['input_signature']]=key
        return key

    def transform(self,table,row):
        values=list(row);columns=['rowid',*self.columns[table]]
        indices={name:i for i,name in enumerate(columns)}
        dictionary_id=None
        if table=='engine_runs':
            dictionary_id=self.seed_run(values[indices['run_id']],values[indices['metadata']])
        elif table=='engine_input_bundles':
            snapshot=json.loads(values[indices['payload']])
            dictionary_id=self.signatures.get(snapshot.get('input_signature'))
        elif table=='engine_results':
            result=json.loads(values[indices['payload']]);old=values[indices['deterministic']]
            check=engine_store.result_checksum(result)
            if old!=check and old!=engine_store.encode(engine_store.stable_result(result)):
                raise ValueError('Result/check copy mismatch at source rowid '+str(values[0]))
            values[indices['deterministic']]=check
            dictionary_id=self.dictionaries.get(values[indices['run_id']])
        expected=tuple(values)
        for column in JSON_COLUMNS[table]:
            i=indices[column]
            values[i]=json_storage.pack(self.dest,values[i],dictionary_id=dictionary_id)
        return tuple(values),expected

    def step(self,*,batch_size=1000):
        if not 1<=batch_size<=2000:raise ValueError('Batch size must be 1..2000')
        if fingerprint(self.source_path)!=self.pinned:raise RuntimeError('Source changed while migrating; source and destination retained')
        if self.get('complete'):return dict(complete=True,table=None)
        if shutil.disk_usage(self.destination_path.parent).free<self.reserve_bytes:
            raise RuntimeError('Stopped before exhausting disk space; migration can resume after freeing space')
        for table in self.tables:
            progress=self.get('table:'+table) or dict(last_rowid=0,rows=0,done=False)
            if progress['done']:continue
            rows=self.source.execute('SELECT rowid,* FROM '+table+' WHERE rowid>? ORDER BY rowid LIMIT ?',
                (progress['last_rowid'],batch_size)).fetchall()
            with self.dest:
                self.dest.execute('BEGIN IMMEDIATE')
                if rows:
                    packed=[];expected=[]
                    for row in rows:
                        item,logical=self.transform(table,row);packed.append(item);expected.append(logical)
                    names=['rowid',*self.columns[table]]
                    self.dest.executemany('INSERT INTO '+table+' ('+','.join(names)+') VALUES ('+','.join('?' for _ in names)+')',packed)
                    actual=self.dest.execute('SELECT rowid,* FROM '+table+' WHERE rowid>? AND rowid<=? ORDER BY rowid',
                        (progress['last_rowid'],rows[-1][0])).fetchall()
                    if actual!=expected:raise RuntimeError('Read-back verification failed for '+table)
                    progress.update(last_rowid=rows[-1][0],rows=progress['rows']+len(rows))
                else:progress['done']=True
                self.put('table:'+table,progress)
            return dict(complete=False,table=table,**progress)
        # Named secondary indexes are copied after data loading. Autoindexes were
        # created with their tables and enforced throughout the transfer.
        for name,sql in self.source.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"):
            if not self.dest.execute("SELECT 1 FROM sqlite_master WHERE name=?",(name,)).fetchone():self.dest.execute(sql)
        self.dest.commit()
        if fingerprint(self.source_path)!=self.pinned:raise RuntimeError('Source changed before final verification')
        check=self.dest.execute('PRAGMA quick_check').fetchall()
        if check!=[('ok',)]:raise RuntimeError('Destination SQLite verification failed: '+repr(check[:5]))
        with self.dest:
            self.put('verified_tables',{table:self.get('table:'+table)['rows'] for table in self.tables})
            self.put('verified_at',time.time())
            self.put('storage_codec','shared-zlib')
            self.put('complete',True)
        return dict(complete=True,table=None,rows=self.get('verified_tables'))


def run(source,destination,*,seconds=30,until_complete=False,batch_size=1000,report=print,reserve_bytes=8*1024**3):
    migration=Migration(source,destination,reserve_bytes=reserve_bytes)
    started=time.monotonic();last_print=started-5;result=None
    try:
        while until_complete or time.monotonic()-started<seconds:
            result=migration.step(batch_size=batch_size)
            now=time.monotonic()
            if result['complete'] or result.get('done') or now-last_print>=5:
                report(json.dumps(result),flush=True);last_print=now
            if result['complete']:break
        return result
    finally:migration.close()
