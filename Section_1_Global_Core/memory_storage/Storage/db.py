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
    "last_kline_time", "count_klines",

    # features
    "write_features", "read_features", "last_feature_time", "count_features",

    # adcn
    "write_adcn", "read_adcn", "read_latest_adcn", "last_adcn_time",

    # canonical state
    "read_state_range",
]
