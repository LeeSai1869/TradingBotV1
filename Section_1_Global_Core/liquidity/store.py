"""Separate WAL memory; no candle/feature database writes or historical replay."""
import json
from pathlib import Path
import sqlite3
import time
import zlib

ROOT=Path(__file__).resolve().parents[1]/'memory_storage'/'Storage'/'liquidity'
DB_PATH=ROOT/'liquidity.db'
STALE_MS=10000


def pack(value):return zlib.compress(json.dumps(value,separators=(',',':'),allow_nan=False).encode(),3)
def unpack(value):return json.loads(zlib.decompress(value))


def open_writer(path=None):
    path=Path(path or DB_PATH);path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path,timeout=2)
    try:
        conn.execute('PRAGMA journal_mode=WAL');conn.execute('PRAGMA synchronous=NORMAL')
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS samples(symbol TEXT, available_ms INTEGER, sampled_ms INTEGER, payload BLOB,
            PRIMARY KEY(symbol,available_ms));
        CREATE TABLE IF NOT EXISTS status(symbol TEXT PRIMARY KEY, updated_ms INTEGER, state TEXT, reason TEXT);
        CREATE TABLE IF NOT EXISTS candle_features(symbol TEXT, open_ms INTEGER, available_ms INTEGER, payload BLOB,
            PRIMARY KEY(symbol,open_ms));
        CREATE TABLE IF NOT EXISTS gaps(symbol TEXT, started_ms INTEGER, reason TEXT);
        CREATE INDEX IF NOT EXISTS gaps_time ON gaps(symbol,started_ms);
        CREATE INDEX IF NOT EXISTS gaps_retention ON gaps(started_ms);
        CREATE INDEX IF NOT EXISTS samples_retention ON samples(available_ms);
        CREATE INDEX IF NOT EXISTS candles_retention ON candle_features(available_ms);
        ''')
        return conn
    except BaseException:conn.close();raise


def set_status(conn,symbol,state,reason='',now_ms=None):
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    conn.execute('INSERT OR REPLACE INTO status VALUES (?,?,?,?)',(symbol,now_ms,state,reason[:500]))
    if state!='live':conn.execute('INSERT INTO gaps VALUES (?,?,?)',(symbol,now_ms,reason[:500]))


def write_sample(conn,sample,available_ms=None):
    available_ms=int(time.time()*1000) if available_ms is None else available_ms
    available_ms=max(available_ms,sample['available_ms'])
    sample={**sample,'sampled_ms':sample['available_ms'],'available_ms':available_ms}
    conn.execute('INSERT OR REPLACE INTO samples VALUES (?,?,?,?)',(sample['symbol'],available_ms,sample['sampled_ms'],pack(sample)))
    set_status(conn,sample['symbol'],'live',now_ms=available_ms)
    return sample


def write_candle(conn,packet):
    conn.execute('INSERT OR REPLACE INTO candle_features VALUES (?,?,?,?)',(packet['symbol'],packet['open_ms'],packet['available_ms'],pack(packet)))


def prune(conn,now_ms):
    # Only this recorder's own short-lived observations; candle summaries retain
    # 90 days. Raw archive retention is handled independently by its owner.
    conn.execute('DELETE FROM samples WHERE available_ms<?',(now_ms-6*3600000,))
    conn.execute('DELETE FROM candle_features WHERE available_ms<?',(now_ms-90*86400000,))
    conn.execute('DELETE FROM gaps WHERE started_ms<?',(now_ms-7*86400000,))


def reader():
    if not DB_PATH.exists():return None
    return sqlite3.connect(DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)


def snapshot(symbol,*,now_ms=None,limit=240):
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    result=dict(venue='binance',market='usdt_perpetual',symbol=symbol,quote='USDT',status='not recording',reason='Start the liquidity recorder',latest=None,history=[],observed=True)
    conn=reader()
    if conn is None:return result
    try:
        conn.execute('BEGIN')
        state=conn.execute("SELECT updated_ms,state,reason FROM status WHERE symbol IN (?, '*') ORDER BY symbol=? DESC LIMIT 1",(symbol,symbol)).fetchone()
        rows=conn.execute('SELECT available_ms,payload FROM samples WHERE symbol=? AND available_ms<=? ORDER BY available_ms DESC LIMIT ?',(symbol,now_ms,max(1,min(240,limit)))).fetchall()
        result['history']=[unpack(row[1]) for row in reversed(rows)]
        latest=result['history'][-1] if rows else None
        fresh=latest and 0<=now_ms-latest['book_received_ms']<=STALE_MS and now_ms-latest['available_ms']<=STALE_MS and abs(now_ms-latest['exchange_ms'])<=STALE_MS
        live=state and state[1]=='live' and 0<=now_ms-state[0]<=STALE_MS and fresh
        result.update(status='live' if live else 'stale' if latest else state[1] if state else 'not recording',
            reason='' if live else state[2] if state and state[2] else 'No fresh synchronized book',latest=latest if live else None,
            last_observed_ms=latest['book_received_ms'] if latest else None)
        return result
    finally:conn.close()


def features_at(symbol,available_before_ms):
    """Training/prediction as-of join: no later observation or stale forward fill."""
    conn=reader()
    if conn is None:return None
    try:
        conn.execute('BEGIN')
        row=conn.execute('SELECT payload FROM samples WHERE symbol=? AND available_ms<=? ORDER BY available_ms DESC LIMIT 1',(symbol,available_before_ms)).fetchone()
        if not row:return None
        sample=unpack(row[0])
        if not 0<=available_before_ms-sample['book_received_ms']<=STALE_MS or abs(available_before_ms-sample['exchange_ms'])>STALE_MS:return None
        gap=conn.execute('SELECT 1 FROM gaps WHERE symbol=? AND started_ms>? AND started_ms<=? LIMIT 1',(symbol,sample.get('sampled_ms',sample['available_ms']),available_before_ms)).fetchone()
        return None if gap else sample
    finally:conn.close()


def candle_features_at(symbol,open_ms,available_before_ms):
    conn=reader()
    if conn is None:return None
    try:
        row=conn.execute('SELECT payload FROM candle_features WHERE symbol=? AND open_ms=? AND available_ms<=?',(symbol,open_ms,available_before_ms)).fetchone()
        return unpack(row[0]) if row else None
    finally:conn.close()


def market_context_at(symbol,available_before_ms):
    """Causal same-venue perpetual comparison; never substitutes spot prices.

    Missing/unrecorded benchmarks remain unavailable. Reading three bounded
    histories uses one SQLite snapshot and never calls an exchange.
    """
    import math
    conn=reader()
    if conn is None:return None
    try:
        conn.execute('BEGIN');series={}
        for asset in dict.fromkeys((symbol.upper(),'BTCUSDT','ETHUSDT')):
            rows=conn.execute('SELECT payload FROM samples WHERE symbol=? AND available_ms>? AND available_ms<=? ORDER BY available_ms',
                (asset,available_before_ms-310000,available_before_ms)).fetchall()
            samples=[unpack(row[0]) for row in rows]
            samples=[s for s in samples if 0<=s['available_ms']-s['exchange_ms']<=STALE_MS]
            gap=conn.execute('SELECT MAX(started_ms) FROM gaps WHERE symbol=? AND started_ms<=?',(asset,available_before_ms)).fetchone()[0]
            if gap is not None:samples=[s for s in samples if s.get('sampled_ms',s['available_ms'])>=gap]
            series[asset]={s['exchange_ms']//5000:s['metrics']['mid'] for s in samples}
        own=series[symbol.upper()];comparisons={}
        for benchmark in ('BTCUSDT','ETHUSDT'):
            other=series[benchmark];aligned=sorted(own.keys()&other.keys())
            fresh=bool(aligned) and 0<=available_before_ms-aligned[-1]*5000<=10000
            complete=fresh and len(aligned)>=61 and aligned[-1]-aligned[0]>=60 and all(b-a==1 for a,b in zip(aligned,aligned[1:]))
            result=dict(complete=complete,aligned_samples=len(aligned),correlation_5m=None,relative_return_5m_bps=None)
            if complete:
                aligned=aligned[-61:]
                x=[math.log(own[b]/own[a]) for a,b in zip(aligned,aligned[1:])]
                y=[math.log(other[b]/other[a]) for a,b in zip(aligned,aligned[1:])]
                mx=sum(x)/len(x);my=sum(y)/len(y)
                denominator=math.sqrt(sum((v-mx)**2 for v in x)*sum((v-my)**2 for v in y))
                result['correlation_5m']=max(-1,min(1,sum((a-mx)*(b-my) for a,b in zip(x,y))/denominator)) if denominator else None
                result['relative_return_5m_bps']=((own[aligned[-1]]/own[aligned[0]]-1)-(other[aligned[-1]]/other[aligned[0]]-1))*10000
            comparisons[benchmark]=result
        return dict(venue='binance',market='usdt_perpetual',symbol=symbol.upper(),available_before_ms=available_before_ms,benchmarks=comparisons)
    finally:conn.close()
