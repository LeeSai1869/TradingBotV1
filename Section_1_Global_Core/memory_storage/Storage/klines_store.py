"""
================================================================================
KLINES STORE — Raw per-bar OHLCV (DB 1)
================================================================================

The passthrough for klines.db. Same shape as features_store.py and
adcn_store.py: open + read + write, one module owns the schema, every
caller goes through this instead of sqlite3.connect().

Schema: matches klines.db as written by download_binance_history.py and
update_klines.py. This module does NOT create tables — it assumes the
schema exists. Use download_binance_history.open_db() to initialize.
================================================================================
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional


DB_PATH = Path(__file__).resolve().parent / "klines.db"


def open_db() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH), timeout=10)


# ------------------------------------------------------------------
# Reads
# ------------------------------------------------------------------

def read_row(conn, symbol, interval, open_time):
    cur = conn.execute(
        "SELECT symbol, interval, open_time, open, high, low, close, "
        "volume, close_time FROM klines "
        "WHERE symbol=? AND interval=? AND open_time=?",
        (symbol, interval, open_time),
    )
    return cur.fetchone()


def read_range(conn, symbol, interval, start_ms, end_ms):
    cur = conn.execute(
        "SELECT symbol, interval, open_time, open, high, low, close, "
        "volume, close_time FROM klines "
        "WHERE symbol=? AND interval=? AND open_time>=? AND open_time<? "
        "ORDER BY open_time",
        (symbol, interval, start_ms, end_ms),
    )
    return cur.fetchall()


def read_last_n(conn, symbol, interval, n: int):
    """Return the last n closed bars, oldest first."""
    cur = conn.execute(
        "SELECT symbol, interval, open_time, open, high, low, close, "
        "volume, close_time FROM klines "
        "WHERE symbol=? AND interval=? "
        "ORDER BY open_time DESC LIMIT ?",
        (symbol, interval, n),
    )
    rows = cur.fetchall()
    return list(reversed(rows))


def read_page(conn, symbol, interval, limit, *, before=None):
    """Latest stored rows, or rows strictly before an existing candle key.

    Count rows rather than estimating a duration: gaps and calendar months
    must not shorten a page when enough stored history exists.
    """
    if not 1 <= limit <= 1002:
        raise ValueError("limit must be between 1 and 1002")
    where = "symbol=? AND interval=?"
    params = [symbol, interval]
    if before is not None:
        where += " AND open_time<?"
        params.append(before)
    params.append(limit)
    rows = conn.execute(
        "SELECT symbol, interval, open_time, open, high, low, close, "
        f"volume, close_time FROM klines WHERE {where} "
        "ORDER BY open_time DESC LIMIT ?", params,
    ).fetchall()
    return list(reversed(rows))


def read_after_page(conn, symbol, interval, after_open_time, limit=500):
    if not 1 <= limit <= 1000:
        raise ValueError('limit must be 1..1000')
    return conn.execute(
        "SELECT symbol,interval,open_time,open,high,low,close,volume,close_time "
        "FROM klines WHERE symbol=? AND interval=? AND open_time>? ORDER BY open_time LIMIT ?",
        (symbol,interval,after_open_time,limit)).fetchall()


def read_after(conn, symbol, interval, after_open_time):
    """Every closed bar strictly after `after_open_time`, oldest first."""
    cur = conn.execute(
        "SELECT symbol, interval, open_time, open, high, low, close, "
        "volume, close_time FROM klines "
        "WHERE symbol=? AND interval=? AND open_time>? "
        "ORDER BY open_time",
        (symbol, interval, after_open_time),
    )
    return cur.fetchall()


def last_open_time(conn, symbol, interval) -> Optional[int]:
    cur = conn.execute(
        "SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?",
        (symbol, interval),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def count_rows(conn, symbol=None, interval=None) -> int:
    if symbol and interval:
        cur = conn.execute(
            "SELECT COUNT(*) FROM klines WHERE symbol=? AND interval=?",
            (symbol, interval),
        )
    elif symbol:
        cur = conn.execute(
            "SELECT COUNT(*) FROM klines WHERE symbol=?", (symbol,)
        )
    else:
        cur = conn.execute("SELECT COUNT(*) FROM klines")
    return cur.fetchone()[0]


# ------------------------------------------------------------------
# Writes
# ------------------------------------------------------------------

def insert_rows(conn, rows: Iterable[dict]) -> int:
    """Insert rows as dicts. Skips duplicates. Returns rows written."""
    batch = []
    for r in rows:
        batch.append((
            r["symbol"], r["interval"], int(r["open_time"]),
            float(r["open"]), float(r["high"]), float(r["low"]),
            float(r["close"]), float(r["volume"]), int(r["close_time"]),
        ))
    if not batch:
        return 0
    cur = conn.executemany(
        "INSERT OR IGNORE INTO klines "
        "(symbol, interval, open_time, open, high, low, close, volume, close_time) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        batch,
    )
    conn.commit()
    return cur.rowcount


__all__ = [
    "DB_PATH",
    "open_db",
    "read_row",
    "read_range",
    "read_last_n",
    "read_page",
    "read_after", "read_after_page",
    "last_open_time",
    "count_rows",
    "insert_rows",
]


def ensure_history_progress(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS history_progress (symbol TEXT, interval TEXT, next_open_time INTEGER NOT NULL, PRIMARY KEY(symbol,interval))')
    conn.commit()


def history_cursor(conn,symbol,interval):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='history_progress'").fetchone():return None
    row=conn.execute('SELECT next_open_time FROM history_progress WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
    return row[0] if row else None


def first_close_waits(conn,now_ms=None):
    """Source-confirmed first forming candles; metadata only, never fake OHLCV."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='first_close_waits'").fetchone():return {}
    rows=conn.execute('SELECT symbol,interval,close_time FROM first_close_waits').fetchall()
    return {(s,t):close for s,t,close in rows if now_ms is None or close>=now_ms}


def record_first_close_wait(conn,symbol,interval,open_time,close_time,observed_at):
    conn.execute('CREATE TABLE IF NOT EXISTS first_close_waits (symbol TEXT,interval TEXT,open_time INTEGER,close_time INTEGER,observed_at INTEGER,PRIMARY KEY(symbol,interval))')
    conn.execute('INSERT OR REPLACE INTO first_close_waits VALUES (?,?,?,?,?)',(symbol,interval,open_time,close_time,observed_at))
    conn.commit()


def clear_first_close_wait(conn,symbol,interval):
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='first_close_waits'").fetchone() and conn.execute('SELECT 1 FROM first_close_waits WHERE symbol=? AND interval=?',(symbol,interval)).fetchone():
        conn.execute('DELETE FROM first_close_waits WHERE symbol=? AND interval=?',(symbol,interval));conn.commit()
