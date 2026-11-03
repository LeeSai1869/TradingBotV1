"""MTF metadata/history in the existing intelligence database; no base rewrites."""
import json
from .memory_storage.Storage import engine_store as memory


def open_db():
    conn=memory.open_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS mtf_bindings (
            id INTEGER PRIMARY KEY, symbol TEXT, timeframe TEXT, engine TEXT,
            known_ms INTEGER, generation TEXT, run_id TEXT, metadata TEXT);
        CREATE INDEX IF NOT EXISTS mtf_binding_lookup ON mtf_bindings(symbol,engine,timeframe,known_ms DESC,id DESC);
        CREATE TABLE IF NOT EXISTS mtf_sources (
            ref TEXT PRIMARY KEY,run_id TEXT,candle_time INTEGER,observed_ms INTEGER,payload TEXT,
            UNIQUE(run_id,candle_time));
        CREATE INDEX IF NOT EXISTS mtf_source_lookup ON mtf_sources(run_id,observed_ms DESC,candle_time DESC);
        CREATE TABLE IF NOT EXISTS mtf_scopes (id TEXT PRIMARY KEY,metadata TEXT);
        CREATE TABLE IF NOT EXISTS mtf_input_bundles (id TEXT PRIMARY KEY,payload TEXT);
        CREATE TABLE IF NOT EXISTS mtf_results (
            id TEXT PRIMARY KEY,scope_id TEXT,as_of INTEGER,bundle_id TEXT,payload TEXT,
            FOREIGN KEY(scope_id) REFERENCES mtf_scopes(id),
            FOREIGN KEY(bundle_id) REFERENCES mtf_input_bundles(id));
        CREATE INDEX IF NOT EXISTS mtf_result_lookup ON mtf_results(scope_id,as_of DESC);
        CREATE TABLE IF NOT EXISTS mtf_latest (scope_id TEXT PRIMARY KEY,input_signature TEXT,result_id TEXT);
    ''')
    return conn


def project_result(result):
    projection={key:result[key] for key in ('contract_version','engine','engine_version','identity','candle_open_time','candle_close_time','as_of','available_at','mode','classification','coverage','confidence','data_quality','confirmation','config_hash','input_signature','provenance')}
    values=result.get('measurements',{})
    observed=values.get('observed')
    projection['aggregation_scope']=dict(scope=values.get('scope'),observed_scope=observed.get('scope') if isinstance(observed,dict) else None)
    return projection


def source(conn,result,run_id,observed_ms):
    projection=project_result(result)
    ref=run_id+':'+str(result['candle_open_time'])+':'+memory.digest(memory.stable_result(result))
    prior=conn.execute('SELECT ref FROM mtf_sources WHERE run_id=? AND candle_time=?',(run_id,result['candle_open_time'])).fetchone()
    if prior and prior[0]!=ref:raise ValueError('Divergent indexed engine result')
    old=conn.execute('SELECT payload FROM mtf_sources WHERE ref=?',(ref,)).fetchone()
    encoded=memory.encode(projection)
    if old and old[0]!=encoded:raise ValueError('Divergent aggregation source reference')
    conn.execute('INSERT OR IGNORE INTO mtf_sources VALUES (?,?,?,?,?)',(ref,run_id,result['candle_open_time'],observed_ms,encoded))
    conn.execute('UPDATE mtf_sources SET run_id=?,observed_ms=? WHERE ref=? AND run_id IS NULL',(run_id,observed_ms,ref))
    return ref


def persist(conn,snapshot,result,metadata,*,force=False):
    scope=memory.digest(metadata)
    prior=conn.execute('SELECT input_signature,result_id FROM mtf_latest WHERE scope_id=?',(scope,)).fetchone()
    if not force and prior and prior[0]==result['input_signature']:return prior[1],False
    bundle={key:value for key,value in snapshot.items() if key!='computed_at'}
    bundle['timeframes']=[]
    for slot in snapshot['timeframes']:
        small={key:value for key,value in slot.items() if key!='result'}
        if slot.get('result'):
            # Deduplicate public source payloads across all matrix snapshots.
            ref=slot['result_ref'];encoded=memory.encode(slot['result'])
            old=conn.execute('SELECT payload FROM mtf_sources WHERE ref=?',(ref,)).fetchone()
            if old and old[0]!=encoded:raise ValueError('Input/reference mismatch')
            conn.execute('INSERT OR IGNORE INTO mtf_sources VALUES (?,?,?,?,?)',(ref,None,slot['result']['candle_open_time'],snapshot['computed_at'],encoded))
        bundle['timeframes'].append(small)
    bundle_id=memory.digest(bundle);result_id=memory.digest(dict(scope=scope,as_of=result['as_of'],input_signature=result['input_signature']))
    encoded=memory.encode(result)
    existing=conn.execute('SELECT payload FROM mtf_results WHERE id=?',(result_id,)).fetchone()
    if existing:
        stable=lambda row:{key:value for key,value in row.items() if key not in ('computed_at','available_at')}
        if stable(json.loads(existing[0]))!=stable(result):raise ValueError('Divergent aggregation at the same key')
    conn.execute('INSERT OR IGNORE INTO mtf_scopes VALUES (?,?)',(scope,memory.encode(metadata)))
    conn.execute('INSERT OR IGNORE INTO mtf_input_bundles VALUES (?,?)',(bundle_id,memory.encode(bundle)))
    conn.execute('INSERT OR IGNORE INTO mtf_results VALUES (?,?,?,?,?)',(result_id,scope,result['as_of'],bundle_id,encoded))
    conn.execute('INSERT OR REPLACE INTO mtf_latest VALUES (?,?,?)',(scope,result['input_signature'],result_id))
    return result_id,not bool(existing)


def input_bundle(conn,result_id):
    row=conn.execute('SELECT b.payload FROM mtf_results r JOIN mtf_input_bundles b ON b.id=r.bundle_id WHERE r.id=?',(result_id,)).fetchone()
    if not row:return None
    bundle=json.loads(row[0])
    for slot in bundle['timeframes']:
        if slot.get('result_ref'):
            source=conn.execute('SELECT payload FROM mtf_sources WHERE ref=?',(slot['result_ref'],)).fetchone()
            if source:slot['result']=json.loads(source[0])
    return bundle
