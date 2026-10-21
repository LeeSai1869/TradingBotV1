"""
================================================================================
FEATURES STORE — Permanent per-bar features (DB 2)
================================================================================

Holds Section 4 output fields that are pure functions of raw klines.
Never changes unless the klines change or the formula changes.

Keyed by (symbol, interval, open_time), matching klines.db.
================================================================================
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "features.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS features (
    symbol              TEXT NOT NULL,
    interval            TEXT NOT NULL,
    open_time           INTEGER NOT NULL,

    ema7                REAL,
    ema25               REAL,
    ema50               REAL,
    ema100              REAL,
    ema200              REAL,
    ema300              REAL,
    prev_ema7           REAL,
    prev_ema25          REAL,
    prev_ema50          REAL,
    prev_ema100         REAL,
    prev_ema200         REAL,
    prev_ema300         REAL,

    wma50               REAL,

    rsi                 REAL,
    prev_rsi            REAL,
    rsi_change          REAL,

    adx                 REAL,
    prev_adx            REAL,
    adx_strength        REAL,
    di_plus             REAL,
    di_minus            REAL,
    prev_di_plus        REAL,
    prev_di_minus       REAL,
    di_dominance        REAL,
    di_spread           REAL,
    di_direction        REAL,

    atr                 REAL,
    prev_atr            REAL,
    atr_percent         REAL,
    atr_ma              REAL,
    atr_ma_ratio        REAL,
    atr_change          REAL,

    current_price       REAL,
    prev_close          REAL,

    candle_range        REAL,
    body                REAL,
    body_percent        REAL,
    prev_candle_range   REAL,
    prev_body           REAL,
    prev_body_percent   REAL,
    upper_wick          REAL,
    lower_wick          REAL,
    close_location      REAL,
    candle_direction    INTEGER,
    change              REAL,
    change_percent      REAL,
    displacement_atr    REAL,
    candle_range_atr    REAL,

    volume              REAL,
    prev_volume         REAL,
    volume_ma           REAL,
    volume_ratio        REAL,
    prev_volume_ratio   REAL,

    vp_poc              REAL,
    vp_vah              REAL,
    vp_val              REAL,
    vp_hvn_high         REAL,
    vp_hvn_low          REAL,
    vp_lvn_high         REAL,
    vp_lvn_low          REAL,

    vwap                REAL,
    vwap_upper1         REAL,
    vwap_upper2         REAL,
    vwap_lower1         REAL,
    vwap_lower2         REAL,

    day_open            REAL,
    london_high         REAL,
    london_low          REAL,
    newyork_high        REAL,
    newyork_low         REAL,
    asia_high           REAL,
    asia_low            REAL,

    PRIMARY KEY (symbol, interval, open_time)
);
"""


COLUMNS = [
    "symbol", "interval", "open_time",

    "ema7", "ema25", "ema50", "ema100", "ema200", "ema300",
    "prev_ema7", "prev_ema25", "prev_ema50", "prev_ema100", "prev_ema200", "prev_ema300",

    "wma50",

    "rsi", "prev_rsi", "rsi_change",

    "adx", "prev_adx", "adx_strength",
    "di_plus", "di_minus",
    "prev_di_plus", "prev_di_minus",
    "di_dominance", "di_spread", "di_direction",

    "atr", "prev_atr", "atr_percent", "atr_ma", "atr_ma_ratio", "atr_change",

    "current_price", "prev_close",

    "candle_range", "body", "body_percent",
    "prev_candle_range", "prev_body", "prev_body_percent",
    "upper_wick", "lower_wick",
    "close_location", "candle_direction",
    "change", "change_percent",
    "displacement_atr", "candle_range_atr",

    "volume", "prev_volume", "volume_ma", "volume_ratio", "prev_volume_ratio",

    "vp_poc", "vp_vah", "vp_val",
    "vp_hvn_high", "vp_hvn_low", "vp_lvn_high", "vp_lvn_low",

    "vwap", "vwap_upper1", "vwap_upper2", "vwap_lower1", "vwap_lower2",

    "day_open",
    "london_high", "london_low",
    "newyork_high", "newyork_low",
    "asia_high", "asia_low",
]

# Keep every pure feature output instead of silently discarding derived fields.
# Legacy columns retain their order for existing callers.
from Section_4_Features.features.registry import load as _pure_features
for _declaration in _pure_features():
    for _field in _declaration['output_fields']:
        if _field not in COLUMNS:
            COLUMNS.append(_field)
COLUMNS.append('formula_version')
_PLACEHOLDERS = ",".join(["?"] * len(COLUMNS))


def open_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(_SCHEMA)
    existing = {row[1] for row in conn.execute('PRAGMA table_info(features)')}
    for column in COLUMNS:
        if column not in existing:
            kind = 'INTEGER DEFAULT 1' if column=='formula_version' else 'TEXT' if column.endswith('_type') else 'REAL'
            try:
                conn.execute(f'ALTER TABLE features ADD COLUMN {column} {kind}')
            except sqlite3.OperationalError:
                # UI and runner may open the previous schema concurrently.
                if column not in {row[1] for row in conn.execute('PRAGMA table_info(features)')}:
                    conn.close()
                    raise
    conn.commit()
    return conn


def insert_rows(conn: sqlite3.Connection, rows: list[dict]) -> int:
    if not rows:
        return 0
    values = [[r.get(c) for c in COLUMNS] for r in rows]
    cur = conn.executemany(
        f"""
        INSERT OR REPLACE INTO features
        ({",".join(COLUMNS)})
        VALUES ({_PLACEHOLDERS})
        """,
        values,
    )
    conn.commit()
    return cur.rowcount


def has_row(conn, symbol, interval, open_time) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM features WHERE symbol=? AND interval=? AND open_time=?",
        (symbol, interval, open_time),
    )
    return cur.fetchone() is not None


def read_row(conn, symbol, interval, open_time):
    cur = conn.execute(
        f"""
        SELECT {",".join(COLUMNS)} FROM features
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
    Read permanent feature rows in [start_ms, end_ms), oldest first.

    Returns dictionaries keyed by COLUMNS.
    """
    cur = conn.execute(
        f"""
        SELECT {",".join(COLUMNS)} FROM features
        WHERE symbol=? AND interval=?
          AND open_time>=? AND open_time<?
        ORDER BY open_time
        """,
        (symbol, interval, start_ms, end_ms),
    )
    return [dict(zip(COLUMNS, row)) for row in cur.fetchall()]


def count_rows(conn, symbol=None, interval=None) -> int:
    if symbol and interval:
        cur = conn.execute(
            "SELECT COUNT(*) FROM features WHERE symbol=? AND interval=?",
            (symbol, interval),
        )
    else:
        cur = conn.execute("SELECT COUNT(*) FROM features")
    return cur.fetchone()[0]


def last_open_time(conn, symbol: str, interval: str):
    cur = conn.execute(
        "SELECT MAX(open_time) FROM features WHERE symbol=? AND interval=?",
        (symbol, interval),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


__all__ = [
    "DB_PATH", "COLUMNS", "open_db",
    "insert_rows", "has_row", "read_row", "read_range",
    "count_rows", "last_open_time",
]
