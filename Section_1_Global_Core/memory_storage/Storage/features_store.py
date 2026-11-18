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
import re
from pathlib import Path


from ...paths import data_path
DB_PATH = data_path('storage/features.db',Path(__file__).resolve().parent / "features.db")


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

# Public names remain readable; these 24 names have no independent stored value
# in the canonical schema. The two unresolved confirmation names are excluded.
from Section_4_Features.execution.contract import ALIASES
STORAGE_ALIASES={
    'ema_gap_7_25':'ema_gap7_25','ema_gap_25_50':'ema_gap25_50','ema_gap_50_100':'ema_gap50_100',
    'ema_gap_7_25_pct':'ema_gap7_25_pct','ema_gap_25_50_pct':'ema_gap25_50_pct','ema_gap_50_100_pct':'ema_gap50_100_pct',
    'distance_to_poc_atr':'distance_to_pocatr','prev_close':'c1',
    'newyork_high':'new_york_high','newyork_low':'new_york_low',
    'vp_vah':'vp_va_high','vp_val':'vp_va_low',
    'nearest_support_price':'nearest_support','nearest_resistance_price':'nearest_resistance',
    'swing_candidate_pivot':'candidate_pivot',
    'swing_candidate_high_price':'candidate_pivot_high_price','swing_candidate_low_price':'candidate_pivot_low_price',
    'swing_direction':'current_swing_direction',
    'swing_latest_confirmed_high':'latest_confirmed_pivot_high','swing_latest_confirmed_low':'latest_confirmed_pivot_low',
    'swing_nearest_high':'nearest_swing_high','swing_nearest_low':'nearest_swing_low',
    'swing_distance_to_high_pct':'distance_to_swing_high_pct','swing_distance_to_low_pct':'distance_to_swing_low_pct',
}
if any(ALIASES.get(a)!=s or s not in _translated_fields for a,s in STORAGE_ALIASES.items()):
    raise RuntimeError('A reviewed storage alias changed; repeat the semantic audit')
FORMULA_COLUMNS={
    'ema_gap7_25':'abs(ema7-ema25)',
    'ema_gap25_50':'abs(ema25-ema50)',
    'ema_gap50_100':'abs(ema50-ema100)',
    'ema_gap7_25_pct':'ema_gap7_25/NULLIF(c,0)',
    'ema_gap25_50_pct':'ema_gap25_50/NULLIF(c,0)',
    'ema_gap50_100_pct':'ema_gap50_100/NULLIF(c,0)',
    'ema_compression':'((ema_gap7_25_pct+ema_gap25_50_pct)+ema_gap50_100_pct)/3.0',
}
STORAGE_COLUMNS=[c for c in COLUMNS if c not in STORAGE_ALIASES and c not in FORMULA_COLUMNS]


def storage_columns(conn):
    generated={r[1] for r in conn.execute('PRAGMA table_xinfo(features)') if r[6] in (2,3)}
    return [c for c in COLUMNS if c not in generated and c not in FORMULA_COLUMNS]


def read_expression(field,prefix='f',*,preserve_legacy=True):
    """Formula projections for dynamic research/SQL readers, with legacy fallback."""
    if field not in COLUMNS:raise ValueError('Unknown feature column')
    from . import ema_distance_reads
    if field in ema_distance_reads.FIELDS:
        return ema_distance_reads.expression(field,prefix,preserve_legacy=preserve_legacy)
    from . import atr_slope_reads
    if field in atr_slope_reads.FIELDS:
        return atr_slope_reads.expression(field,prefix,preserve_legacy=preserve_legacy)
    source=STORAGE_ALIASES.get(field,field)
    def expand(name):
        if name in FORMULA_COLUMNS:
            return '('+re.sub(r'\b[A-Za-z_][A-Za-z_0-9]*\b',lambda m:expand(m[0]) if m[0] in COLUMNS else m[0],FORMULA_COLUMNS[name])+')'
        return prefix+'."'+name+'"'
    if source not in FORMULA_COLUMNS:return prefix+'."'+field+'"'
    expression=expand(source)
    if not preserve_legacy:return expression+' AS "'+field+'"'
    return f'(CASE WHEN {prefix}.formula_version=3 THEN {expression} ELSE COALESCE({prefix}."{field}",{expression}) END) AS "{field}"'


def resolve_derived(values):
    if values.get('formula_version')==3:
        from Section_4_Features.execution.derived_features import trend_values
        values.update(trend_values(values))
        for alias,source in STORAGE_ALIASES.items():
            if source in FORMULA_COLUMNS:values[alias]=values[source]
        from Section_4_Features.execution.ema_distances import values as ema_distance_values
        values.update(ema_distance_values(values))
    return values


def storage_values(row,columns):
    values=dict(row)
    for alias,source in STORAGE_ALIASES.items():
        a=values.get(alias);s=values.get(source)
        if a is not None and s is not None and a!=s:
            raise ValueError('Conflicting feature alias: '+alias+' / '+source)
        if s is None and a is not None:values[source]=a
    return [values.get(c) for c in columns]


def open_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH.resolve().as_uri(),uri=True)
    try:
        schema=_SCHEMA
        for alias in (*STORAGE_ALIASES,*FORMULA_COLUMNS):
            schema=re.sub(r'^\s*'+re.escape(alias)+r'\s+[^\n]*,\n','',schema,flags=re.MULTILINE)
        conn.executescript(schema)
        existing = {row[1] for row in conn.execute('PRAGMA table_xinfo(features)')}
        for column in COLUMNS:
            if column in STORAGE_ALIASES or column in FORMULA_COLUMNS:continue
            if column not in existing:
                kind = 'INTEGER DEFAULT 1' if column=='formula_version' else 'TEXT' if _translated_fields.get(column)=='string' or column.endswith('_type') else 'REAL'
                try:
                    conn.execute(f'ALTER TABLE features ADD COLUMN {column} {kind}')
                except sqlite3.OperationalError:
                    # UI and runner may open the previous schema concurrently.
                    if column not in {row[1] for row in conn.execute('PRAGMA table_xinfo(features)')}:
                        conn.close()
                        raise
        for alias,source in {**FORMULA_COLUMNS,**STORAGE_ALIASES}.items():
            if alias not in existing:
                kind='TEXT' if _translated_fields.get(source)=='string' else 'REAL'
                try:conn.execute(f'ALTER TABLE features ADD COLUMN {alias} {kind} GENERATED ALWAYS AS ({source}) VIRTUAL')
                except sqlite3.OperationalError:
                    if alias not in {r[1] for r in conn.execute('PRAGMA table_xinfo(features)')}:raise
        conn.execute('CREATE TABLE IF NOT EXISTS feature_replay_jobs (symbol TEXT, interval TEXT, signature TEXT, target INTEGER, last_time INTEGER, changed TEXT, state TEXT, columns TEXT, PRIMARY KEY(symbol,interval))')
        conn.execute("CREATE TABLE IF NOT EXISTS feature_calculation_versions (symbol TEXT, interval TEXT, signature TEXT, generation INTEGER NOT NULL DEFAULT 0, invalidated_columns TEXT NOT NULL DEFAULT '[]', PRIMARY KEY(symbol,interval))")
        if 'invalidated_columns' not in {row[1] for row in conn.execute('PRAGMA table_info(feature_calculation_versions)')}:
            conn.execute("ALTER TABLE feature_calculation_versions ADD COLUMN invalidated_columns TEXT NOT NULL DEFAULT '[]'")
        conn.execute('CREATE TABLE IF NOT EXISTS feature_engine_state (symbol TEXT, interval TEXT, last_open_time INTEGER, state TEXT NOT NULL, PRIMARY KEY(symbol,interval))')
        conn.commit()
        from . import atr_slope_reads
        atr_slope_reads.install(conn,attach_raw=False)
        return conn
    except BaseException:
        conn.close()
        raise


def insert_rows(conn: sqlite3.Connection, rows: list[dict]) -> int:
    if not rows:
        return 0
    columns=storage_columns(conn)
    values = [storage_values(r,columns) for r in rows]
    with conn:
        cur = conn.executemany(
            f"""
            INSERT OR REPLACE INTO features
            ({",".join(columns)})
            VALUES ({",".join('?' for _ in columns)})
            """,
            values,
        )
        from . import atr_slope_reads
        atr_slope_reads.retire_written(conn,[(r['symbol'],r['interval'],r['open_time']) for r in rows])
        from . import ema_distance_retirement
        ema_distance_retirement.retire_written(conn,[(r['symbol'],r['interval'],r['open_time']) for r in rows])
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
        SELECT {_read_projection(conn,columns)} FROM features
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
    existing={row[1] for row in conn.execute('PRAGMA table_xinfo(features)')}
    return [column for column in COLUMNS if column in existing]


def _read_projection(conn,columns):
    from . import atr_slope_reads
    if set(columns)&atr_slope_reads.FIELDS.keys():
        atr_slope_reads.install(conn)
    return ','.join(atr_slope_reads.expression(c,'features')
                    if c in atr_slope_reads.FIELDS else '"'+c+'"' for c in columns)


def _decode(columns,row):
    result=dict.fromkeys(COLUMNS)
    result.update(zip(columns,row))
    for key,value in result.items():
        if value is not None and _translated_fields.get(key)=='bool':result[key]=bool(value)
    return resolve_derived(result)


def read_range(conn, symbol, interval, start_ms, end_ms, *, mask_pending=True):
    """
    Read permanent feature rows in [start_ms, end_ms), oldest first.

    Returns dictionaries keyed by COLUMNS.
    """
    columns=_read_columns(conn)
    if not columns:return []
    cur = conn.execute(
        f"""
        SELECT {_read_projection(conn,columns)} FROM features
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
    columns={row[1] for row in conn.execute('PRAGMA table_xinfo(features)')}
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
    from . import atr_slope_reads
    if set(columns)&atr_slope_reads.FIELDS.keys():atr_slope_reads.install(conn)
    rows=conn.execute('SELECT '+','.join(read_expression(c) for c in columns)+' FROM features f WHERE symbol=? AND interval=? AND open_time>=? AND open_time<? ORDER BY open_time',(symbol,interval,start,end)).fetchall()
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
