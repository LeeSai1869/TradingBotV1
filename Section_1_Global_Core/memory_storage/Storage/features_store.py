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
from Section_4_Features.execution.contract import LEGACY_FIELDS
for _field in LEGACY_FIELDS:
    if _field not in COLUMNS:COLUMNS.append(_field)
COLUMNS.append('formula_version')
from Section_4_Features.execution.contract import FIELDS as _translated_fields
for _field in _translated_fields:
    if _field not in COLUMNS:COLUMNS.append(_field)
_PLACEHOLDERS = ",".join(["?"] * len(COLUMNS))


def open_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript(_SCHEMA)
        existing = {row[1] for row in conn.execute('PRAGMA table_info(features)')}
        for column in COLUMNS:
            if column not in existing:
                kind = 'INTEGER DEFAULT 1' if column=='formula_version' else 'TEXT' if _translated_fields.get(column)=='string' or column.endswith('_type') else 'REAL'
                try:
                    conn.execute(f'ALTER TABLE features ADD COLUMN {column} {kind}')
                except sqlite3.OperationalError:
                    # UI and runner may open the previous schema concurrently.
                    if column not in {row[1] for row in conn.execute('PRAGMA table_info(features)')}:
                        conn.close()
                        raise
        conn.execute('CREATE TABLE IF NOT EXISTS feature_replay_jobs (symbol TEXT, interval TEXT, signature TEXT, target INTEGER, last_time INTEGER, changed TEXT, state TEXT, columns TEXT, PRIMARY KEY(symbol,interval))')
        conn.execute("CREATE TABLE IF NOT EXISTS feature_calculation_versions (symbol TEXT, interval TEXT, signature TEXT, generation INTEGER NOT NULL DEFAULT 0, invalidated_columns TEXT NOT NULL DEFAULT '[]', PRIMARY KEY(symbol,interval))")
        if 'invalidated_columns' not in {row[1] for row in conn.execute('PRAGMA table_info(feature_calculation_versions)')}:
            conn.execute("ALTER TABLE feature_calculation_versions ADD COLUMN invalidated_columns TEXT NOT NULL DEFAULT '[]'")
        conn.execute('CREATE TABLE IF NOT EXISTS feature_engine_state (symbol TEXT, interval TEXT, last_open_time INTEGER, state TEXT NOT NULL, PRIMARY KEY(symbol,interval))')
        conn.commit()
        return conn
    except BaseException:
        conn.close()
        raise


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
    columns = _read_columns(conn)
    if not columns:return None
    cur = conn.execute(
        f"""
        SELECT {",".join(columns)} FROM features
        WHERE symbol=? AND interval=? AND open_time=?
        """,
        (symbol, interval, open_time),
    )
    row = cur.fetchone()
    if row is None:
        return None
    result=_decode(columns,row)
    mask_replays(conn,symbol,interval,[result])
    return result


def _read_columns(conn):
    existing={row[1] for row in conn.execute('PRAGMA table_info(features)')}
    return [column for column in COLUMNS if column in existing]


def _decode(columns,row):
    result=dict.fromkeys(COLUMNS)
    result.update(zip(columns,row))
    for key,value in result.items():
        if value is not None and _translated_fields.get(key)=='bool':result[key]=bool(value)
    return result


def read_range(conn, symbol, interval, start_ms, end_ms, *, mask_pending=True):
    """
    Read permanent feature rows in [start_ms, end_ms), oldest first.

    Returns dictionaries keyed by COLUMNS.
    """
    columns=_read_columns(conn)
    if not columns:return []
    cur = conn.execute(
        f"""
        SELECT {",".join(columns)} FROM features
        WHERE symbol=? AND interval=?
          AND open_time>=? AND open_time<?
        ORDER BY open_time
        """,
        (symbol, interval, start_ms, end_ms),
    )
    result=[_decode(columns,row) for row in cur.fetchall()]
    if mask_pending:mask_replays(conn,symbol,interval,result)
    return result


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


def read_di_inputs(conn,symbol,interval,start,end):
    columns={row[1] for row in conn.execute('PRAGMA table_info(features)')}
    fields=decision_fields()
    if not set(fields+['formula_version']).issubset(columns):return {}
    cap=replay_through(conn,symbol,interval)
    if cap is not None:end=min(end,cap+1)
    rows=conn.execute('SELECT open_time,'+','.join(fields)+' FROM features WHERE symbol=? AND interval=? AND open_time>=? AND open_time<? AND formula_version=3 ORDER BY open_time',(symbol,interval,start,end)).fetchall()
    return {row[0]:dict(zip(fields,row[1:])) for row in rows}


def replay_through(conn,symbol,interval):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_engine_state'").fetchone():return None
    row=conn.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
    through=row[0] if row else None
    task=pending_replay(conn,symbol,interval)
    if task and set(task[2])&set(decision_fields()+['c','close']):
        through=min(through,task[0]) if through is not None else task[0]
    return through


def pending_replay(conn,symbol,interval):
    import json
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_replay_jobs'").fetchone():return None
    row=conn.execute('SELECT last_time,target,columns FROM feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
    return (row[0],row[1],json.loads(row[2])) if row else None


def decision_generation(symbol,interval):
    if not DB_PATH.exists():return 0
    conn=sqlite3.connect(DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_calculation_versions'").fetchone():return 0
        row=conn.execute('SELECT generation FROM feature_calculation_versions WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
        return row[0] if row else 0
    finally:conn.close()


def decision_fields():
    from Section_8_Decision_Engine.rules import di_turning_point as rule
    return [field for field in rule.FIELDS if field!='close']



def read_replay_inputs(conn,symbol,interval,start,end,columns):
    """Small prerequisite projection for targeted replay; no presentation masking."""
    columns=sorted((set(columns)&set(COLUMNS))|{'open_time','formula_version'})
    rows=conn.execute('SELECT '+','.join(columns)+' FROM features WHERE symbol=? AND interval=? AND open_time>=? AND open_time<? ORDER BY open_time',(symbol,interval,start,end)).fetchall()
    result=[]
    for row in rows:
        value=dict(zip(columns,row))
        for key,item in value.items():
            if item is not None and _translated_fields.get(key)=='bool':value[key]=bool(item)
        result.append(value)
    return result



def mask_replays(conn,symbol,interval,rows):
    import json
    task=pending_replay(conn,symbol,interval)
    legacy=None
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='feature_calculation_versions'").fetchone():
        legacy=conn.execute('SELECT v.invalidated_columns,s.last_open_time FROM feature_calculation_versions v LEFT JOIN feature_engine_state s ON v.symbol=s.symbol AND v.interval=s.interval WHERE v.symbol=? AND v.interval=?',(symbol,interval)).fetchone()
    invalidated=json.loads(legacy[0]) if legacy else []
    for row in rows:
        if task and task[0]<row['open_time']<=task[1]:
            for field in task[2]:row[field]=None
        if legacy and legacy[1] is not None and row['open_time']>legacy[1]:
            for field in invalidated:row[field]=None
