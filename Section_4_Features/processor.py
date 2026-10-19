"""
================================================================================
SECTION 4 — LIVE PROCESSOR
================================================================================

Two entry points used by Section 1's orchestrator:

    catch_up(symbol, interval)
        Called once on startup. Walks every kline bar newer than the
        last feature row and computes features for it.

    process_bar(ev)
        Called on every new closed bar. Computes features for that bar.

Both read klines through db.read_last_klines() and write through
db.write_features(). No direct store or sqlite access.

Warmup window: 500 bars. Enough for EMA-300, session VWAP, liquidity
lookbacks, and everything in market_context / market_location.
================================================================================
"""

from __future__ import annotations

import pandas as pd

from Section_1_Global_Core.memory_storage.Storage import db
from Section_1_Global_Core.memory_storage.Storage import features_store
from Section_4_Features.feature_builder import build_feature_packet


WARMUP_BARS = 500
WRITE_BATCH = 500

_INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000, "3d": 259_200_000,
    "1w": 604_800_000, "1M": 2_592_000_000,
}


# ==============================================================================
# HELPERS
# ==============================================================================

def _df_from_rows(rows):
    """Convert a list of kline tuples/rows into a DataFrame for Section 4."""
    if not rows:
        return None
    # klines_store returns tuples:
    # (symbol, interval, open_time, open, high, low, close, volume, close_time)
    df = pd.DataFrame(rows, columns=[
        "symbol", "interval", "open_time",
        "open", "high", "low", "close", "volume", "close_time",
    ])
    df = df.rename(columns={"open_time": "time"})
    df = df.sort_values("time").reset_index(drop=True)
    return df


def _row_from_packet(symbol, interval, open_time, packet):
    """Map FeaturePacket.features dict onto a features.db row dict."""
    if packet is None or not packet.valid:
        return None
    f = packet.features or {}
    # Only carry keys that features_store.COLUMNS knows about.
    from Section_1_Global_Core.memory_storage.Storage.features_store import COLUMNS
    row = {"symbol": symbol, "interval": interval, "open_time": open_time}
    for col in COLUMNS:
        if col in ("symbol", "interval", "open_time"):
            continue
        if col in f:
            row[col] = f[col]
    return row


# ==============================================================================
# CORE
# ==============================================================================

def _compute_and_write_one(symbol, interval, bar_open_ms):
    """Compute features for one bar and write the row."""
    # Read the warmup window ending at bar_open_ms (inclusive).
    rows = db.read_klines(
        symbol, interval,
        start_ms=0, end_ms=bar_open_ms + 1,
    )
    if not rows:
        return 0
    # Keep only the last WARMUP_BARS.
    rows = rows[-WARMUP_BARS:]
    df = _df_from_rows(rows)
    if df is None or df.empty:
        return 0

    packet = build_feature_packet(
        tf=interval,
        symbol=symbol,
        df=df,
        bar_index=len(df) - 1,
        is_confirmed=True,
    )
    row = _row_from_packet(symbol, interval, bar_open_ms, packet)
    if row is None:
        return 0
    return db.write_features([row])


def catch_up(symbol, interval):
    """
    Fill any missing feature rows for (symbol, interval).

    Handles three cases:
      * No features at all         -> walk from the first kline.
      * Feature tail behind klines -> walk from the last feature forward.
      * Tail current but interior gaps exist -> walk backwards in bounded
        windows and fill the holes, stopping once a full window is clean.

    Uses features_store.has_row() to test each bar. Batched writes.
    """
    import time as _t
    t0 = _t.time()

    last_kline = db.last_kline_time(symbol, interval)
    if last_kline is None:
        return 0

    last_feature = db.last_feature_time(symbol, interval)
    interval_ms = _INTERVAL_MS[interval]

    # ---- Case 1: no features at all ----
    if last_feature is None:
        gap_rows = _klines_to_dicts(db.read_klines(symbol, interval, 0, last_kline + 1))
        return _fill_gap(symbol, interval, gap_rows, t0)

    # ---- Case 2: tail is behind klines ----
    if last_feature < last_kline:
        # warmup + range from last_feature to last_kline
        gap_start = last_feature + interval_ms   # next bar after last feature
        warmup_start = max(0, gap_start - WARMUP_BARS * interval_ms)
        warmup_rows = _klines_to_dicts(db.read_klines(symbol, interval,
                                           warmup_start, gap_start))
        gap_rows = _klines_to_dicts(db.read_klines(symbol, interval,
                                        gap_start, last_kline + 1))
        return _fill_gap(symbol, interval, gap_rows, t0,
                         warmup_rows=warmup_rows)

    # ---- Case 3: tail current — look for interior gaps ----
    # Walk backwards in windows of WINDOW_BARS. If a window is clean,
    # stop. Otherwise, fill the missing rows, continue back.
    WINDOW_BARS = 2000
    step = interval_ms

    cursor_end = last_kline + step
    total_written = 0

    for _ in range(50):   # safety limit: at most 50 windows
        cursor_start = cursor_end - WINDOW_BARS * step
        if cursor_start < 0:
            cursor_start = 0

        window = _klines_to_dicts(db.read_klines(symbol, interval,
                                      cursor_start, cursor_end))
        if not window:
            break

        # Which bars in this window have no feature row?
        conn = features_store.open_db()
        try:
            missing_times = []
            for r in window:
                t_bar = r["open_time"]
                if not features_store.has_row(conn, symbol, interval, t_bar):
                    missing_times.append(t_bar)
        finally:
            conn.close()

        if not missing_times:
            # Window is clean — assume history behind it is clean too.
            break

        # Fill this window's missing bars.
        # Warmup = WARMUP_BARS klines immediately before the earliest missing bar.
        earliest_missing = missing_times[0]
        warmup_start = max(0, earliest_missing - WARMUP_BARS * step)
        warmup_rows = _klines_to_dicts(db.read_klines(symbol, interval,
                                           warmup_start, earliest_missing))

        written = _fill_gap(symbol, interval, window, t0,
                            warmup_rows=warmup_rows,
                            only_times=set(missing_times),
                            silent=True)
        total_written += written

        if cursor_start == 0:
            break
        cursor_end = cursor_start

    dt = _t.time() - t0
    if total_written:
        print(f"[processor] catch_up {symbol} {interval}: "
              f"+{total_written} interior rows in {dt:.1f}s", flush=True)
    return total_written


def _klines_to_dicts(rows):
    """Convert tuple rows from db.read_klines into dicts."""
    out = []
    for r in rows:
        out.append({
            "symbol": r[0], "interval": r[1], "open_time": r[2],
            "open": r[3], "high": r[4], "low": r[5],
            "close": r[6], "volume": r[7], "close_time": r[8],
        })
    return out


def _fill_gap(symbol, interval, gap_rows, t0,
              warmup_rows=None, only_times=None, silent=False):
    """
    Compute and write feature rows for `gap_rows`.
    gap_rows: list of kline dicts
    warmup_rows: klines preceding the gap for computing features
    only_times: optional set of open_times to restrict writes to
    """
    import time as _t
    if not gap_rows:
        return 0

    warmup_rows = warmup_rows or []
    all_rows = warmup_rows + gap_rows
    df = _df_from_rows(all_rows)
    if df is None or df.empty:
        return 0

    time_to_idx = {int(t): i for i, t in enumerate(df["time"].tolist())}

    from Section_1_Global_Core.memory_storage.Storage.features_store import COLUMNS
    rows_to_write = []
    written = 0

    for r in gap_rows:
        bar_open_ms = r["open_time"]
        if only_times is not None and bar_open_ms not in only_times:
            continue
        idx = time_to_idx.get(int(bar_open_ms))
        if idx is None:
            continue
        start = max(0, idx - WARMUP_BARS + 1)
        slice_df = df.iloc[start:idx + 1]
        try:
            packet = build_feature_packet(
                tf=interval, symbol=symbol,
                df=slice_df,
                bar_index=len(slice_df) - 1,
                is_confirmed=True,
            )
            row = _row_from_packet(symbol, interval, bar_open_ms, packet)
            if row is not None:
                rows_to_write.append(row)
        except Exception as e:
            print(f"[processor] {symbol} {interval} bar {bar_open_ms} failed: {e}",
                  flush=True)

        if len(rows_to_write) >= WRITE_BATCH:
            written += db.write_features(rows_to_write)
            rows_to_write = []

    if rows_to_write:
        written += db.write_features(rows_to_write)

    if not silent:
        dt = _t.time() - t0
        print(f"[processor] catch_up {symbol} {interval}: "
              f"+{written} rows in {dt:.1f}s", flush=True)
    return written


def process_bar(ev):
    """Called by Section 1's orchestrator on every new closed bar."""
    try:
        return _compute_and_write_one(ev.symbol, ev.timeframe, ev.open_time)
    except Exception as e:
        print(f"[processor] process_bar failed {ev.symbol} {ev.timeframe}: {e}",
              flush=True)
        return 0
