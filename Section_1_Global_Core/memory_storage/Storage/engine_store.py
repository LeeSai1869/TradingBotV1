"""Core-owned versioned analytical history. Never executes stored source text."""
from pathlib import Path
import hashlib
import json
import sqlite3

DB_PATH=Path(__file__).with_name('intelligence.db')


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(encode(value).encode()).hexdigest()


def open_db():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DB_PATH,timeout=5);conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS engine_runs (
            run_id TEXT PRIMARY KEY, metadata TEXT NOT NULL, cursor INTEGER NOT NULL DEFAULT -1, state TEXT);
        CREATE TABLE IF NOT EXISTS engine_input_bundles (
            bundle_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS engine_results (
            run_id TEXT NOT NULL REFERENCES engine_runs(run_id), candle_time INTEGER NOT NULL,
            bundle_id TEXT NOT NULL REFERENCES engine_input_bundles(bundle_id),
            deterministic TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(run_id,candle_time));
    ''');return conn


def load(conn,run_id):
    row=conn.execute('SELECT cursor,state FROM engine_runs WHERE run_id=?',(run_id,)).fetchone()
    return (row['cursor'],json.loads(row['state']) if row['state'] else None) if row else (-1,None)


def stable_result(result):return {k:v for k,v in result.items() if k not in ('computed_at','available_at')}


def commit_batch(conn,metadata,expected_cursor,batch,state):
    """Atomic bundles + rows + state; optimistic cursor protects concurrent CLIs."""
    run_id=digest(metadata)
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('INSERT OR IGNORE INTO engine_runs(run_id,metadata) VALUES (?,?)',(run_id,encode(metadata)))
        current=load(conn,run_id)[0]
        if current!=expected_cursor:raise RuntimeError('Analytical cursor changed; retry the bounded batch')
        previous=current
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
            bundle_id=digest(bundle);stable=encode(stable_result(result))
            old=conn.execute('SELECT bundle_id,deterministic FROM engine_results WHERE run_id=? AND candle_time=?',(run_id,candle)).fetchone()
            if old and (old['bundle_id']!=bundle_id or old['deterministic']!=stable):raise ValueError('Same-key analytical divergence')
            conn.execute('INSERT OR IGNORE INTO engine_input_bundles VALUES (?,?)',(bundle_id,encode(bundle)))
            conn.execute('INSERT OR IGNORE INTO engine_results VALUES (?,?,?,?,?)',(run_id,candle,bundle_id,stable,encode(result)))
        if batch:
            if state.get('last_open')!=previous or state.get('last_close')!=batch[-1][1]['candle_close_time']:raise ValueError('Checkpoint and result cursor differ')
            if any(state.get(key)!=metadata.get(key) for key in ('identity','config_hash','input_signature','state_schema_version')):raise ValueError('Checkpoint/run binding mismatch')
            conn.execute('UPDATE engine_runs SET cursor=?,state=? WHERE run_id=?',(previous,encode(state),run_id))
    return run_id


def latest(conn,run_id):
    row=conn.execute('SELECT payload FROM engine_results WHERE run_id=? ORDER BY candle_time DESC LIMIT 1',(run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def input_bundle(conn,run_id,candle_time):
    row=conn.execute('SELECT b.payload FROM engine_results r JOIN engine_input_bundles b USING(bundle_id) WHERE r.run_id=? AND r.candle_time=?',(run_id,candle_time)).fetchone()
    return json.loads(row[0]) if row else None
