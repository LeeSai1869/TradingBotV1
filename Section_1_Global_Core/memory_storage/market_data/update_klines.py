"""
================================================================================
MARKET DATA — Incremental Kline Updater
================================================================================

Keeps market_data/klines.db fresh. Called from the live runner each cycle.

Caught-up pairs respect interval boundaries. Historical pages keep progressing
between interval boundaries; recent snapshots are refreshed once per bucket.

INVARIANT:
    Every stored candle has close_time < now_ms, where now_ms is
    measured at the moment _insert validates the candle.
================================================================================
"""

from __future__ import annotations

from Section_1_Global_Core import data_policy
from Section_1_Global_Core.memory_storage.Storage import klines_store

import sqlite3
import time
import urllib.request
import urllib.parse
import json as _json
from pathlib import Path


DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "Storage"
    / "klines.db"
)

SYMBOLS = ["BTCUSDT", "SUIUSDT"]

INTERVALS = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
]

INTERVAL_MS = {
    "1m":   60_000,
    "3m":   180_000,
    "5m":   300_000,
    "15m":  900_000,
    "30m":  1_800_000,
    "1h":   3_600_000,
    "2h":   7_200_000,
    "4h":   14_400_000,
    "6h":   21_600_000,
    "8h":   28_800_000,
    "12h":  43_200_000,
    "1d":   86_400_000,
    "3d":   259_200_000,
    "1w":   604_800_000,
    "1M":   2_592_000_000,
}

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

# Audit is best-effort on every update_all(); if it fails, ingest is not blocked.
try:
    from Section_1_Global_Core.memory_storage.Audit import audit_runner as _audit_runner
except Exception:
    _audit_runner = None
PAGE_LIMIT = 1000


_LAST_UPDATE_MS = {}
LAST_AUDIT = None
_DOWNLOAD_CURSOR = 0
_LATEST_UPDATE_MS = {}


def _open_db():
    return sqlite3.connect(str(DB_PATH), timeout=10)


def _last_stored_open_time(conn, symbol, interval):
    cur = conn.execute(
        "SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?",
        (symbol, interval),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def _fetch(symbol, interval, start_ms):
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": PAGE_LIMIT,
    }
    if start_ms is not None:params["startTime"]=int(start_ms)
    url = BINANCE_KLINES_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "ScalpV1-UP/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return _json.loads(resp.read().decode("utf-8"))


def _insert(conn, symbol, interval, page, now_ms):
    """
    Insert a page of klines. Skips any candle whose close_time >= now_ms.

    This is the ONLY place the closed-candle invariant is enforced.
    """
    rows = []
    for k in page:
        close_time = int(k[6])
        if close_time >= now_ms:
            continue
        rows.append((
            symbol,
            interval,
            int(k[0]),
            float(k[1]),
            float(k[2]),
            float(k[3]),
            float(k[4]),
            float(k[5]),
            close_time,
        ))

    if not rows:
        return 0

    cur = conn.executemany(
        """
        INSERT OR IGNORE INTO klines
        (symbol, interval, open_time, open, high, low, close, volume, close_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return cur.rowcount


def _pair_epoch(symbol,interval):
    epochs=data_policy.read()['epochs']
    return epochs.get(f'symbol:{symbol}',0),epochs.get(f'interval:{interval}',0)


def update_one(symbol, interval, conn):
    """
    Update one (symbol, interval). Returns rows inserted.

    Fetch at most once per interval *bucket*. A new fetch is triggered
    as soon as wall-clock time crosses into the next interval bucket,
    which is the first moment the newly-closed bar is available.

    Never raises on network errors — logs and returns 0.
    The next cycle retries.
    """
    now_ms = int(time.time() * 1000)
    key = (symbol, interval)
    epoch=_pair_epoch(symbol,interval)
    step = INTERVAL_MS[interval]

    if not data_policy.enabled(symbol, interval):
        return 0
    klines_store.ensure_history_progress(conn)
    stored = _last_stored_open_time(conn, symbol, interval)
    if stored is None:_LATEST_UPDATE_MS.pop(key,None)
    cursor=klines_store.history_cursor(conn,symbol,interval)
    last_ms = _LAST_UPDATE_MS.get(key) if stored is not None else None
    if cursor is None and last_ms is not None and last_ms//step==now_ms//step:return 0
    from .download_binance_history import FALLBACK_START_MS
    start_ms=cursor if cursor is not None else stored+1 if stored is not None else FALLBACK_START_MS
    total=0
    # Keep the historical cursor separate from MAX(open_time) before adding a
    # current page. Otherwise a recent page would permanently skip older history.
    behind=stored is None or now_ms-stored>2*step
    if cursor is None and behind:
        with data_policy.locked():
            if not data_policy.enabled(symbol,interval) or epoch!=_pair_epoch(symbol,interval):return 0
            conn.execute('INSERT OR IGNORE INTO history_progress VALUES (?,?,?)',(symbol,interval,start_ms));conn.commit()
        cursor=start_ms
    if cursor is not None and _LATEST_UPDATE_MS.get(key,-1)//step!=now_ms//step:
        try:
            latest=_fetch(symbol,interval,None)
            with data_policy.locked():
                if not data_policy.enabled(symbol,interval) or epoch!=_pair_epoch(symbol,interval):return 0
                total+=_insert(conn,symbol,interval,latest,now_ms)
            _LATEST_UPDATE_MS[key]=now_ms
            if latest:print(f'[update_klines] {symbol} {interval}: recent closed candles refreshed; history cursor retained',flush=True)
        except Exception as error:
            print(f'[update_klines] {symbol} {interval}: latest refresh error: {error}',flush=True)

    try:
        page = _fetch(symbol, interval, start_ms)
    except Exception as e:
        print("[update_klines] " + symbol + " " + interval + ": fetch error: " + str(e), flush=True)
        return total

    if not page:
        _LAST_UPDATE_MS[key] = now_ms
        return total

    now_ms = int(time.time() * 1000)
    with data_policy.locked():
        if not data_policy.enabled(symbol, interval) or epoch!=_pair_epoch(symbol,interval):
            return total
        n = _insert(conn, symbol, interval, page, now_ms)
        closed=[row for row in page if int(row[6])<now_ms]
        if cursor is not None and not closed and page and int(page[0][6])>=now_ms:
            with conn:conn.execute('DELETE FROM history_progress WHERE symbol=? AND interval=?',(symbol,interval))
        if cursor is not None and closed:
            next_time=int(closed[-1][0])+1
            with conn:
                conn.execute('UPDATE history_progress SET next_open_time=? WHERE symbol=? AND interval=?',(next_time,symbol,interval))
                # Short pages finish historical catch-up only when they approach
                # the current exchange boundary (not on a transient old page).
                if (len(page)<PAGE_LIMIT or int(page[-1][6])>=now_ms) and now_ms-int(closed[-1][6])<2*step:
                    conn.execute('DELETE FROM history_progress WHERE symbol=? AND interval=?',(symbol,interval))
    # A full page can mean backlog; continue next cycle rather than waiting
    # an entire 1w/1M interval. Throttle only when caught up.
    if len(page) < PAGE_LIMIT or int(page[-1][6]) >= now_ms:
        _LAST_UPDATE_MS[key] = now_ms
    else:
        _LAST_UPDATE_MS.pop(key, None)
    if n > 0:
        print("[update_klines] " + symbol + " " + interval + ": +" + str(n) + " bars", flush=True)
    return total+n


def update_all(*, max_pairs=512, time_budget=2.0):
    """
    Update a bounded round-robin slice of pairs. Returns total bars inserted.

    Time is checked between requests; one request retains its network timeout.

    Safe to call every runner cycle. Interval-boundary tracking means
    caught-up pairs are queried at most once per bar period; history keeps paging.
    """
    global LAST_AUDIT, _DOWNLOAD_CURSOR
    LAST_AUDIT = None
    if not DB_PATH.exists():
        return 0

    conn = _open_db()
    total = 0
    try:
        pairs=[(symbol,interval) for symbol in data_policy.active_symbols()
               for interval in data_policy.active_intervals()]
        deadline=time.monotonic()+time_budget
        visited=0
        for _ in range(min(max_pairs,len(pairs))):
            symbol,interval=pairs[_DOWNLOAD_CURSOR%len(pairs)]
            _DOWNLOAD_CURSOR+=1;visited+=1
            total += update_one(symbol, interval, conn)
            # A request may finish after the soft deadline; never start the next
            # one until features have had their turn in the existing runner.
            if time.monotonic()>=deadline:break
        print(f'[update_klines] download slice: {visited}/{len(pairs)} pairs; cursor={_DOWNLOAD_CURSOR}; yielding to features',flush=True)
    finally:
        conn.close()

    # Bounded audit after ingest. Full verification/repairs are a separate run.
    if _audit_runner is not None and total > 0:
        try:
            print("[audit] recent-row audit starting",flush=True)
            manifest = _audit_runner.run_fast(sample_rows_per_pair=10)
            LAST_AUDIT = manifest.get('summary') or _audit_runner.summarize(manifest)
            audit_conn=_open_db()
            try:
                pending=audit_conn.execute('SELECT symbol,interval FROM history_progress').fetchall() if audit_conn.execute("SELECT 1 FROM sqlite_master WHERE name='history_progress'").fetchone() else []
                active=set(pairs)
                LAST_AUDIT['history_backfill_pairs']=sum(tuple(pair) in active for pair in pending)
                if LAST_AUDIT['history_backfill_pairs']:LAST_AUDIT['pass']=False
            finally:audit_conn.close()
            print('[audit] '+_json.dumps(LAST_AUDIT,sort_keys=True),flush=True)
        except Exception as e:
            LAST_AUDIT = {"pass":None,"error":str(e)}
            print("[update_klines] audit warning:", e, flush=True)

    return total


__all__ = ["update_all", "update_one", "SYMBOLS", "INTERVALS"]