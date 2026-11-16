"""Core-owned versioned analytical history. Never executes stored source text."""
from pathlib import Path
from contextlib import closing
import hashlib
import json
import sqlite3

from ...paths import data_path
from . import adcn_store,json_storage
_DEFAULT_PATH = adcn_store.DB_PATH
LEGACY_DB_PATH = data_path('storage/intelligence.db',Path(__file__).with_name('intelligence.db'))


def _selected_path():
    # Existing installations keep their live writer/reader format until a
    # separately verified cutover. Importing code must never force a migration.
    if not LEGACY_DB_PATH.exists():return _DEFAULT_PATH
    if _DEFAULT_PATH.exists():
        try:
            with closing(sqlite3.connect(_DEFAULT_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)) as conn:
                ready=conn.execute("SELECT value FROM _section5_migration WHERE name='complete'").fetchone()
                if ready and ready[0]=='true':return _DEFAULT_PATH
        except sqlite3.Error:pass
    return LEGACY_DB_PATH


DB_PATH = _selected_path()


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(encode(value).encode()).hexdigest()


def open_db():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    conn=json_storage.connect(DB_PATH,row_factory=sqlite3.Row)
    compact=DB_PATH==_DEFAULT_PATH
    try:
        codec=conn.execute("SELECT value FROM _section5_migration WHERE name='storage_codec'").fetchone()
        if codec and json.loads(codec[0])=='plain':compact=False
    except sqlite3.OperationalError:pass
    conn._section5_compact=compact
    if DB_PATH==_DEFAULT_PATH and LEGACY_DB_PATH.exists():
        try:ready=conn.execute("SELECT value FROM _section5_migration WHERE name='complete'").fetchone()
        except sqlite3.OperationalError:ready=None
        if not ready or ready[0]!='true':
            conn.close()
            raise RuntimeError('Section 5 history needs migration to ADCN.db; run migrate_intelligence.py before restarting writers')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS engine_history_bindings (
            symbol TEXT NOT NULL,timeframe TEXT NOT NULL,engine TEXT NOT NULL,
            generation TEXT NOT NULL,run_id TEXT,metadata TEXT NOT NULL,status TEXT NOT NULL,updated_ms INTEGER NOT NULL,
            PRIMARY KEY(symbol,timeframe,engine));
        CREATE TABLE IF NOT EXISTS engine_live_seeds (
            seed_key TEXT PRIMARY KEY, candle_time INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS engine_runs (
            run_id TEXT PRIMARY KEY, metadata TEXT NOT NULL, cursor INTEGER NOT NULL DEFAULT -1, state TEXT);
        CREATE TABLE IF NOT EXISTS engine_input_bundles (
            bundle_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS engine_results (
            run_id TEXT NOT NULL REFERENCES engine_runs(run_id), candle_time INTEGER NOT NULL,
            bundle_id TEXT NOT NULL REFERENCES engine_input_bundles(bundle_id),
            deterministic TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(run_id,candle_time));
    ''')
    if compact:json_storage.create_schema(conn)
    return conn


def open_readonly(*,timeout=.2):
    return json_storage.connect(DB_PATH,readonly=True,timeout=timeout,row_factory=sqlite3.Row)


def load(conn,run_id):
    row=conn.execute('SELECT cursor,state FROM engine_runs WHERE run_id=?',(run_id,)).fetchone()
    return (row['cursor'],json.loads(row['state']) if row['state'] else None) if row else (-1,None)


def stable_result(result):return {k:v for k,v in result.items() if k not in ('computed_at','available_at')}


def result_checksum(result):
    """Keep the divergence check without storing a second copy of the result."""
    return 'sha256:'+digest(stable_result(result))


def commit_batch(conn,metadata,expected_cursor,batch,state):
    """Atomic bundles + rows + state; optimistic cursor protects concurrent CLIs."""
    run_id=digest(metadata)
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('INSERT OR IGNORE INTO engine_runs(run_id,metadata) VALUES (?,?)',(run_id,json_storage.pack(conn,encode(metadata))))
        current=load(conn,run_id)[0]
        if current!=expected_cursor:raise RuntimeError('Analytical cursor changed; retry the bounded batch')
        previous=current;dictionary_id=None
        if batch and conn._section5_compact:
            snapshot,result=batch[0]
            seed=encode({k:v for k,v in snapshot.items() if k!='computed_at'})+'\n'+encode(stable_result(result))
            dictionary_id=json_storage.seed_dictionary(conn,run_id,seed.encode())
        for snapshot,result in batch:
            if result['mode']!='CONFIRMED' or not snapshot['closed']:raise ValueError('Never persist provisional outputs')
            binding=('identity','engine','engine_version','config_hash','input_signature')
            if any(result.get(key)!=metadata.get(key) for key in binding):raise ValueError('Result/run binding mismatch')
            if any(snapshot.get(key)!=result.get(key) for key in ('identity','input_signature','candle_open_time','candle_close_time','as_of')):raise ValueError('Snapshot/result binding mismatch')
            candle=result['candle_open_time']
            if candle<=previous:raise ValueError('Analytical batch must be chronological')
            previous=candle
            # Execution time is not part of immutable source evidence.
            bundle={k:v for k,v in snapshot.items() if k!='computed_at'}
            bundle_id=digest(bundle);checksum=result_checksum(result)
            old=conn.execute('SELECT bundle_id,deterministic FROM engine_results WHERE run_id=? AND candle_time=?',(run_id,candle)).fetchone()
            # Legacy rows contain canonical JSON here; new rows use its checksum.
            if old and (old['bundle_id']!=bundle_id or (old['deterministic']!=checksum and old['deterministic']!=encode(stable_result(result)))):raise ValueError('Same-key analytical divergence')
            conn.execute('INSERT OR IGNORE INTO engine_input_bundles VALUES (?,?)',(bundle_id,json_storage.pack(conn,encode(bundle),dictionary_id=dictionary_id)))
            conn.execute('INSERT OR IGNORE INTO engine_results VALUES (?,?,?,?,?)',(run_id,candle,bundle_id,checksum,json_storage.pack(conn,encode(result),dictionary_id=dictionary_id)))
        if batch:
            if state.get('last_open')!=previous or state.get('last_close')!=batch[-1][1]['candle_close_time']:raise ValueError('Checkpoint and result cursor differ')
            if any(state.get(key)!=metadata.get(key) for key in ('identity','config_hash','input_signature','state_schema_version')):raise ValueError('Checkpoint/run binding mismatch')
            conn.execute('UPDATE engine_runs SET cursor=?,state=? WHERE run_id=?',(previous,json_storage.pack(conn,encode(state),dictionary_id=dictionary_id),run_id))
    return run_id


def latest(conn,run_id):
    row=conn.execute('SELECT payload FROM engine_results WHERE run_id=? ORDER BY candle_time DESC LIMIT 1',(run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def input_bundle(conn,run_id,candle_time):
    row=conn.execute('SELECT b.payload FROM engine_results r JOIN engine_input_bundles b USING(bundle_id) WHERE r.run_id=? AND r.candle_time=?',(run_id,candle_time)).fetchone()
    return json.loads(row[0]) if row else None
