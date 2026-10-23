"""
================================================================================
CENTRAL DB ACCESS — the one place every section reads and writes through.
================================================================================

Wraps the three stores (klines_store, features_store, adcn_store).
Each store owns its schema; this module owns the *access pattern*.

Every caller uses:
    from Section_1_Global_Core.memory_storage.Storage import db

    db.write_klines([...])
    db.read_last_klines("BTCUSDT", "15m", 500)
    db.write_features([...])
    db.read_features_after("BTCUSDT", "15m", since_ms)
    ...

No section opens sqlite3 directly. No section imports the stores
directly. Everything goes through db.py.
================================================================================
"""

from __future__ import annotations
from pathlib import Path
import sqlite3

from . import klines_store
from . import features_store
from . import adcn_store


# ==============================================================================
# PATHS
# ==============================================================================

KLINES_DB   = klines_store.DB_PATH
FEATURES_DB = features_store.DB_PATH
ADCN_DB     = adcn_store.DB_PATH


# ==============================================================================
# KLINES
# ==============================================================================

def write_klines(rows: list[dict]) -> int:
    """Insert a batch of kline rows. Returns number of rows written."""
    conn = klines_store.open_db()
    try:
        return klines_store.insert_rows(conn, rows)
    finally:
        conn.close()


def read_klines(symbol, interval, start_ms=None, end_ms=None):
    """Read klines in [start_ms, end_ms)."""
    conn = klines_store.open_db()
    try:
        return klines_store.read_range(conn, symbol, interval, start_ms, end_ms)
    finally:
        conn.close()


def read_last_klines(symbol, interval, n):
    """Read the last N closed bars, oldest first."""
    conn = klines_store.open_db()
    try:
        return klines_store.read_last_n(conn, symbol, interval, n)
    finally:
        conn.close()


def read_klines_after(symbol, interval, after_open_ms):
    """Read every closed bar with open_time > after_open_ms."""
    conn = klines_store.open_db()
    try:
        return klines_store.read_after(conn, symbol, interval, after_open_ms)
    finally:
        conn.close()


def read_klines_tail(symbol, interval, end_ms, n=500):
    conn = klines_store.open_db()
    try:
        return klines_store.read_page(conn, symbol, interval, n, before=end_ms)
    finally:
        conn.close()


def read_state_after(symbol, interval, after_ms, limit=500):
    conn = klines_store.open_db()
    try:
        rows = klines_store.read_after_page(conn, symbol, interval, after_ms, limit)
    finally:
        conn.close()
    if not rows:
        return []
    return read_state_range(symbol, interval, int(rows[0][2]), int(rows[-1][2]) + 1)


def last_kline_time(symbol, interval):
    conn = klines_store.open_db()
    try:
        return klines_store.last_open_time(conn, symbol, interval)
    finally:
        conn.close()


def count_klines(symbol=None, interval=None):
    conn = klines_store.open_db()
    try:
        return klines_store.count_rows(conn, symbol, interval)
    finally:
        conn.close()


# ==============================================================================
# FEATURES
# ==============================================================================

def write_features(rows: list[dict]) -> int:
    """Insert a batch of feature rows. Returns number of rows written."""
    conn = features_store.open_db()
    try:
        return features_store.insert_rows(conn, rows)
    finally:
        conn.close()


def read_features(symbol, interval, open_time):
    conn = features_store.open_db()
    try:
        return features_store.read_row(conn, symbol, interval, open_time)
    finally:
        conn.close()


def last_feature_time(symbol, interval):
    conn = features_store.open_db()
    try:
        return features_store.last_open_time(conn, symbol, interval)
    finally:
        conn.close()


def count_features(symbol=None, interval=None):
    conn = features_store.open_db()
    try:
        return features_store.count_rows(conn, symbol, interval)
    finally:
        conn.close()


# ==============================================================================
# CANONICAL PER-BAR STATE
# ==============================================================================

_KLINE_COLUMNS = (
    "symbol", "interval", "open_time",
    "open", "high", "low", "close", "volume", "close_time",
)


def read_state_range(symbol, interval, start_ms, end_ms):
    """
    Read canonical permanent state in [start_ms, end_ms).

    Klines are the authoritative timeline. Each returned item represents
    exactly one stored kline. Permanent features and permanent ADCN state
    are attached by the shared identity:

        (symbol, interval, open_time)

    Missing derived rows remain None; they never remove a canonical bar.
    The three physical stores remain an implementation detail of this
    public Central Core contract.
    """
    k_conn = klines_store.open_db()
    f_conn = features_store.open_db()
    a_conn = adcn_store.open_db()

    try:
        kline_rows = klines_store.read_range(
            k_conn, symbol, interval, start_ms, end_ms
        )
        feature_rows = features_store.read_range(
            f_conn, symbol, interval, start_ms, end_ms
        )
        adcn_rows = adcn_store.read_range(
            a_conn, symbol, interval, start_ms, end_ms
        )
    finally:
        k_conn.close()
        f_conn.close()
        a_conn.close()

    features_by_time = {
        int(row["open_time"]): row
        for row in feature_rows
    }
    adcn_by_time = {
        int(row["open_time"]): row
        for row in adcn_rows
    }

    state = []

    for raw in kline_rows:
        client = dict(zip(_KLINE_COLUMNS, raw))
        open_time = int(client["open_time"])

        state.append({
            "symbol": client["symbol"],
            "interval": client["interval"],
            "open_time": open_time,
            "client": client,
            "features": features_by_time.get(open_time),
            "adcn": adcn_by_time.get(open_time),
        })

    return state


def _read_connection(path):
    """Read committed data without schema creation or a writer connection."""
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=1)


def _read_derived(store, symbol, interval, start_ms, end_ms):
    if not store.DB_PATH.exists():
        return []
    conn = _read_connection(store.DB_PATH)
    try:
        return store.read_range(conn, symbol, interval, start_ms, end_ms)
    finally:
        conn.close()


def read_state_page(symbol, interval, limit=1000, *, before=None):
    """One combined record per stored candle, with an exclusive older cursor.

    Keep the selected kline keys authoritative even while the ingestion
    process commits new rows. Missing derived rows remain None.
    """
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if not klines_store.DB_PATH.exists():
        return {"bars": [], "next_before": None}
    conn = _read_connection(klines_store.DB_PATH)
    try:
        rows = klines_store.read_page(conn, symbol, interval, limit + 2, before=before)
        cursor=klines_store.history_cursor(conn,symbol,interval)
    finally:
        conn.close()
    has_more = len(rows) > limit
    if not rows:
        return {"bars": [], "next_before": None}
    start_ms, end_ms = int(rows[0][2]), int(rows[-1][2]) + 1
    features = _read_derived(features_store, symbol, interval, start_ms, end_ms)
    decisions = _read_derived(adcn_store, symbol, interval, start_ms, end_ms)
    features_by_time = {int(row["open_time"]): row for row in features}
    decisions_by_time = {int(row["open_time"]): row for row in decisions}
    bars = []
    for row in rows:
        client = dict(zip(_KLINE_COLUMNS, row))
        open_time = int(client["open_time"])
        bars.append({
            "symbol": symbol, "interval": interval, "open_time": open_time,
            "time": open_time // 1000,
            "client": client,
            "features": features_by_time.get(open_time),
            "adcn": decisions_by_time.get(open_time),
        })
    # Two predecessor rows seed the same Section 8 gate at page boundaries.
    # This is a bounded read-only projection; it does not backfill ADCN memory.
    from Section_8_Decision_Engine.presentation import annotate
    bars=annotate(bars)
    # Most recent windows can still lack replayed features. Never search their
    # entire older history when there is no candidate to display in this page.
    if any(bar.get('momentum',{}).get('signal_type') for bar in bars[-limit:] if bar.get('momentum')):
        first_evaluated=bars[2]['open_time'] if len(bars)>2 else bars[0]['open_time']
        last_signal=read_previous_decision_candidate(symbol,interval,first_evaluated)
        bars=annotate(bars,last_signal)
    bars=bars[-limit:]
    return {"bars": bars, "next_before": bars[0]['open_time'] if has_more else None, "history_pending":cursor is not None}


# ==============================================================================
# ADCN
# ==============================================================================

def write_adcn(rows: list[dict]) -> int:
    conn = adcn_store.open_db()
    try:
        return adcn_store.insert_rows(conn, rows)
    finally:
        conn.close()


def read_adcn(symbol, interval, open_time):
    conn = adcn_store.open_db()
    try:
        return adcn_store.read_row(conn, symbol, interval, open_time)
    finally:
        conn.close()


def read_signals(symbol, interval, limit=None):
    conn = adcn_store.open_db()
    try:
        return adcn_store.read_signals(conn, symbol, interval, limit)
    finally:
        conn.close()


def read_latest_adcn(symbol, interval):
    """
    Read the latest permanent ADCN row for (symbol, interval).

    Returns a dictionary keyed by adcn_store.COLUMNS, or None when
    no permanent ADCN state exists for the requested market/timeframe.
    """
    conn = adcn_store.open_db()
    try:
        last = adcn_store.last_open_time(conn, symbol, interval)
        if last is None:
            return None
        row = adcn_store.read_row(conn, symbol, interval, last)
    finally:
        conn.close()

    if row is None:
        return None

    return row


def last_adcn_time(symbol, interval):
    conn = adcn_store.open_db()
    try:
        return adcn_store.last_open_time(conn, symbol, interval)
    finally:
        conn.close()


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # paths
    "KLINES_DB", "FEATURES_DB", "ADCN_DB",

    # klines
    "write_klines", "read_klines", "read_last_klines", "read_klines_after",
    "last_kline_time", "count_klines", "read_klines_tail",

    # features
    "write_features", "read_features", "last_feature_time", "count_features",

    # adcn
    "write_adcn", "read_adcn", "read_latest_adcn", "last_adcn_time",

    # canonical state
    "read_state_range",
    "read_state_page", "read_state_after",
]


def read_decision_inputs(symbol,interval,after,limit=200):
    """Small closed-bar/DI projection, capped by committed feature replay state."""
    if not features_store.DB_PATH.exists() or not klines_store.DB_PATH.exists():return []
    from Section_1_Global_Core import data_policy
    with data_policy.snapshot_guard():
        features=_read_connection(features_store.DB_PATH)
        raw=_read_connection(klines_store.DB_PATH)
        try:
            features.execute('BEGIN')
            through=features_store.replay_through(features,symbol,interval)
            if through is None:return []
            rows=[row for row in klines_store.read_after_page(raw,symbol,interval,after,limit) if row[2]<=through]
            if not rows:return []
            values=features_store.read_di_inputs(features,symbol,interval,rows[0][2],rows[-1][2]+1)
            return [dict(open_time=row[2],close_time=row[8],close=row[6],features=values.get(row[2])) for row in rows]
        finally:features.close();raw.close()


def read_decision_seed(symbol,interval):
    """Latest three raw candles at the committed feature prefix; never a live tail."""
    if not features_store.DB_PATH.exists() or not klines_store.DB_PATH.exists():return []
    from Section_1_Global_Core import data_policy
    with data_policy.snapshot_guard():
        features=_read_connection(features_store.DB_PATH);raw=_read_connection(klines_store.DB_PATH)
        try:
            features.execute('BEGIN')
            through=features_store.replay_through(features,symbol,interval)
            if through is None:return []
            rows=klines_store.read_page(raw,symbol,interval,3,before=through+1)
            if not rows:return []
            values=features_store.read_di_inputs(features,symbol,interval,rows[0][2],rows[-1][2]+1)
            return [dict(open_time=row[2],close_time=row[8],close=row[6],features=values.get(row[2])) for row in rows]
        finally:features.close();raw.close()


def iter_decision_history(symbols=None,intervals=None):
    """Read-only, streaming canonical closed history for strategy evaluation.

    Each yielded cursor is consumed before requesting the next pair. A feature
    snapshot caps the stream at its committed replay prefix.
    """
    import time
    if not klines_store.DB_PATH.exists() or not features_store.DB_PATH.exists():return
    raw=_read_connection(klines_store.DB_PATH)
    try:
        raw.execute('ATTACH DATABASE ? AS f',(f'file:{features_store.DB_PATH}?mode=ro',))
        raw.execute('BEGIN')
        if not raw.execute("SELECT 1 FROM f.sqlite_master WHERE name='feature_engine_state'").fetchone():return
        pairs=raw.execute('SELECT symbol,interval,last_open_time FROM f.feature_engine_state ORDER BY symbol,interval').fetchall()
        for symbol,interval,cap in pairs:
            if raw.execute("SELECT 1 FROM f.sqlite_master WHERE name='feature_replay_jobs'").fetchone():
                task=raw.execute('SELECT last_time,columns FROM f.feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                if task:
                    import json
                    if set(json.loads(task[1]))&set(features_store.decision_fields()+['c','close']):cap=min(cap,task[0])
            if (symbols and symbol not in symbols) or (intervals and interval not in intervals):continue
            columns=('open_time','close_time','open','close','di_plus','di_minus','di_spread','adx')
            cursor=raw.execute('''SELECT k.open_time,k.close_time,k.open,k.close,f.di_plus,f.di_minus,f.di_spread,f.adx
                FROM klines k JOIN f.features f ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time
                WHERE k.symbol=? AND k.interval=? AND k.open_time<=? AND k.close_time<? AND f.formula_version=3 ORDER BY k.open_time''',
                (symbol,interval,cap,int(time.time()*1000)))
            yield symbol,interval,cap,(dict(zip(columns,r)) for r in cursor)
    finally:raw.close()


def read_previous_decision_candidate(symbol,interval,before):
    """Nearest raw gate direction before a candle, using small backward pages.

    Last accepted direction equals last raw candidate direction under strict
    alternation. This seeds chart pages without restarting alternation at each
    viewport boundary, and avoids replaying every older decision into memory.
    Only the small DI/ADX projection is read; connections always close explicitly.
    """
    from contextlib import ExitStack,closing
    from Section_8_Decision_Engine.rules import di_turning_point as rule
    import time
    if not klines_store.DB_PATH.exists() or not features_store.DB_PATH.exists():return None
    now=int(time.time()*1000)
    with ExitStack() as stack:
        raw=stack.enter_context(closing(_read_connection(klines_store.DB_PATH)))
        features=stack.enter_context(closing(_read_connection(features_store.DB_PATH)))
        features.execute('BEGIN')
        while True:
            rows=klines_store.read_page(raw,symbol,interval,514,before=before)
            if len(rows)<3:return None
            values=features_store.read_di_inputs(features,symbol,interval,rows[0][2],rows[-1][2]+1)
            records=[];previous=[];last_close=None
            for row in rows:
                if last_close is not None and last_close+1!=row[2]:previous=[]
                last_close=row[8]
                if row[8]>=now or row[2] not in values:
                    previous=[];records.append(None);continue
                current={**values[row[2]],'close':row[6]}
                records.append(rule.evaluate(previous,current)['signal_type'])
                previous.append(current);previous=previous[-2:]
            for signal in reversed(records[2:]):
                if signal:return signal
            if len(rows)<514:return None
            before=rows[2][2]
