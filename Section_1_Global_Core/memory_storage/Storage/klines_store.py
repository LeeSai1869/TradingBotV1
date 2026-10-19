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
    "read_after",
    "last_open_time",
    "count_rows",
    "insert_rows",
]
