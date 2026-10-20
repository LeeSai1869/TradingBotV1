"""
================================================================================
MARKET DATA — Incremental Kline Updater
================================================================================

Keeps market_data/klines.db fresh. Called from the live runner each cycle.

Only fetches new bars. Respects interval boundaries: a 1h interval is
queried at most once per hour, a 1w interval at most once per week, etc.

INVARIANT:
    Every stored candle has close_time < now_ms, where now_ms is
    measured at the moment _insert validates the candle.
================================================================================
"""

from __future__ import annotations

from Section_1_Global_Core import data_policy

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
        "startTime": int(start_ms),
        "limit": PAGE_LIMIT,
    }
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
    step = INTERVAL_MS[interval]

    if not data_policy.enabled(symbol, interval):
        return 0
    stored = _last_stored_open_time(conn, symbol, interval)
    last_ms = _LAST_UPDATE_MS.get(key) if stored is not None else None
    if last_ms is not None:
        # Same interval bucket as the last fetch — the bar we would
        # fetch hasn't closed yet. Nothing new to do.
        if (last_ms // step) == (now_ms // step):
            return 0

    # Missing/deleted pairs bootstrap from exchange history, one page per cycle.
    from .download_binance_history import FALLBACK_START_MS
    start_ms = stored + 1 if stored is not None else FALLBACK_START_MS

    try:
        page = _fetch(symbol, interval, start_ms)
    except Exception as e:
        print("[update_klines] " + symbol + " " + interval + ": fetch error: " + str(e), flush=True)
        return 0

    if not page:
        _LAST_UPDATE_MS[key] = now_ms
        return 0

    now_ms = int(time.time() * 1000)
    with data_policy.locked():
        if not data_policy.enabled(symbol, interval):
            return 0
        n = _insert(conn, symbol, interval, page, now_ms)
    # A full page can mean backlog; continue next cycle rather than waiting
    # an entire 1w/1M interval. Throttle only when caught up.
    if len(page) < PAGE_LIMIT or int(page[-1][6]) >= now_ms:
        _LAST_UPDATE_MS[key] = now_ms
    else:
        _LAST_UPDATE_MS.pop(key, None)
    if n > 0:
        print("[update_klines] " + symbol + " " + interval + ": +" + str(n) + " bars", flush=True)
    return n


def update_all():
    """
    Update every (symbol, interval). Returns total bars inserted.

    Safe to call every runner cycle. Interval-boundary tracking means
    each interval is queried at most once per bar period.
    """
    if not DB_PATH.exists():
        return 0

    conn = _open_db()
    total = 0
    try:
        for symbol in data_policy.active_symbols():
            for interval in data_policy.active_intervals():
                total += update_one(symbol, interval, conn)
    finally:
        conn.close()

    # Best-effort audit after every ingest pass. Does not block.
    if _audit_runner is not None and total > 0:
        try:
            _audit_runner.run_fast(sample_rows_per_pair=10)
        except Exception as e:
            print("[update_klines] audit warning:", e, flush=True)

    return total


__all__ = ["update_all", "update_one", "SYMBOLS", "INTERVALS"]