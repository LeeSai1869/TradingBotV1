"""
================================================================================
ADCN STORE — Engine decisions (DB 3)
================================================================================

Holds:
    Section 4 interpretations (swing_* fields)
    Section 6.1 output
    Section 7.1 output
    Section 8.1 output

One row per (symbol, interval, open_time).

Interpretations change when engine logic changes. Section 4's
permanent per-bar features live in features_store.py instead.
================================================================================
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "ADCN.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    symbol              TEXT NOT NULL,
    interval            TEXT NOT NULL,
    open_time           INTEGER NOT NULL,

    -- Section 4 interpretations
    flip_direction          TEXT,
    swing_candidate_pivot   INTEGER,
    swing_direction         TEXT,
    swing_pivot_high_flip   INTEGER,
    swing_pivot_low_flip    INTEGER,
    swing_transition        INTEGER,

    -- Section 6.1
    scalp_score             REAL,
    scalp_diplus_score      REAL,
    scalp_diminus_score     REAL,
    pivot_high_eligible     INTEGER,
    pivot_low_eligible      INTEGER,
    pivot_direction         INTEGER,
    directional_movement_score REAL,
    pivot_score             REAL,
    bullish_movement_score  REAL,
    bearish_movement_score  REAL,

    -- Section 7.1
    confluence_net_score    REAL,

    -- Section 8.1
    trend_state             TEXT,
    last_signal             TEXT,
    looking_for             TEXT,
    trigger                 TEXT,
    signal_type             TEXT,
    final_score             REAL,
    decision_state          TEXT,

    PRIMARY KEY (symbol, interval, open_time)
);

CREATE INDEX IF NOT EXISTS idx_decisions_signals
    ON decisions (symbol, interval, signal_type);
"""

COLUMNS = [
    "symbol", "interval", "open_time",

    "flip_direction", "swing_candidate_pivot", "swing_direction",
    "swing_pivot_high_flip", "swing_pivot_low_flip", "swing_transition",

    "scalp_score", "scalp_diplus_score", "scalp_diminus_score",
    "pivot_high_eligible", "pivot_low_eligible", "pivot_direction",
    "directional_movement_score", "pivot_score",
    "bullish_movement_score", "bearish_movement_score",

    "confluence_net_score",

    "trend_state", "last_signal", "looking_for",
    "trigger", "signal_type", "final_score", "decision_state",
]

_PLACEHOLDERS = ",".join(["?"] * len(COLUMNS))


def open_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def insert_rows(conn: sqlite3.Connection, rows: list[dict]) -> int:
    if not rows:
        return 0
    values = [[r.get(c) for c in COLUMNS] for r in rows]
    cur = conn.executemany(
        f"""
        INSERT OR REPLACE INTO decisions
        ({",".join(COLUMNS)})
        VALUES ({_PLACEHOLDERS})
        """,
        values,
    )
    conn.commit()
    return cur.rowcount


def has_row(conn, symbol, interval, open_time) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM decisions WHERE symbol=? AND interval=? AND open_time=?",
        (symbol, interval, open_time),
    )
    return cur.fetchone() is not None


def read_row(conn, symbol, interval, open_time):
    cur = conn.execute(
        f"""
        SELECT {",".join(COLUMNS)} FROM decisions
        WHERE symbol=? AND interval=? AND open_time=?
        """,
        (symbol, interval, open_time),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(COLUMNS, row))


def read_range(conn, symbol, interval, start_ms, end_ms):
    """
    Read permanent ADCN rows in [start_ms, end_ms), oldest first.

    Returns dictionaries keyed by COLUMNS.
    """
    cur = conn.execute(
        f"""
        SELECT {",".join(COLUMNS)} FROM decisions
        WHERE symbol=? AND interval=?
          AND open_time>=? AND open_time<?
        ORDER BY open_time
        """,
        (symbol, interval, start_ms, end_ms),
    )
    return [dict(zip(COLUMNS, row)) for row in cur.fetchall()]


def read_previous_state(conn, symbol, interval, open_time):
    """
    Most recent decisions row strictly before open_time.
    Carries swing state forward from the previous bar.
    """
    cur = conn.execute(
        f"""
        SELECT {",".join(COLUMNS)} FROM decisions
        WHERE symbol=? AND interval=? AND open_time < ?
        ORDER BY open_time DESC LIMIT 1
        """,
        (symbol, interval, open_time),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(COLUMNS, row))


def last_signal_for(conn, symbol: str, interval: str):
    """
    Most recent fired BUY or SELL for (symbol, interval).
    Returns (signal_type, open_time) or (None, None).
    """
    cur = conn.execute(
        """
        SELECT signal_type, open_time FROM decisions
        WHERE symbol=? AND interval=?
          AND signal_type IN ('BUY', 'SELL')
        ORDER BY open_time DESC LIMIT 1
        """,
        (symbol, interval),
    )
    row = cur.fetchone()
    if row is None:
        return (None, None)
    return (row[0], row[1])


def read_signals(conn, symbol, interval, limit=None):
    """Every BUY/SELL row for (symbol, interval), oldest first.
    One query. No range, no loop."""
    if limit is not None:
        cur = conn.execute(
            "SELECT symbol, interval, open_time, signal_type, final_score "
            "FROM decisions WHERE symbol=? AND interval=? "
            "AND signal_type IN ('BUY','SELL') "
            "ORDER BY open_time DESC LIMIT ?",
            (symbol, interval, limit),
        )
        rows = cur.fetchall()
        rows.reverse()
        return rows
    cur = conn.execute(
        "SELECT symbol, interval, open_time, signal_type, final_score "
        "FROM decisions WHERE symbol=? AND interval=? "
        "AND signal_type IN ('BUY','SELL') "
        "ORDER BY open_time",
        (symbol, interval),
    )
    return cur.fetchall()


def last_open_time(conn, symbol, interval):
    """Latest open_time in decisions for (symbol, interval). Any row."""
    cur = conn.execute(
        "SELECT MAX(open_time) FROM decisions WHERE symbol=? AND interval=?",
        (symbol, interval),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def count_rows(conn, symbol=None, interval=None) -> int:
    if symbol and interval:
        cur = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE symbol=? AND interval=?",
            (symbol, interval),
        )
    else:
        cur = conn.execute("SELECT COUNT(*) FROM decisions")
    return cur.fetchone()[0]


__all__ = [
    "DB_PATH", "COLUMNS", "open_db",
    "insert_rows", "has_row", "read_row", "read_range",
    "read_previous_state", "last_open_time",
    "last_signal_for", "count_rows",
]