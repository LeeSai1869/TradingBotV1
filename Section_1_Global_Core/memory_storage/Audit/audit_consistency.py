"""A4 — Cross-interval consistency audit.

For paired intervals (short, long), verify that the long bar's
OHLCV is consistent with the aggregate of the short bars.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from . import audit_config as cfg
from .audit_schema import INTERVAL_MS


def _load(symbol: str, interval: str, start_ms: int | None = None) -> list:
    conn = sqlite3.connect(str(cfg.KLINES_DB))
    try:
        sql = ("SELECT open_time, open, high, low, close, volume "
               "FROM klines WHERE symbol=? AND interval=?")
        params: list = [symbol, interval]
        if start_ms is not None:
            sql += " AND open_time >= ?"
            params.append(start_ms)
        sql += " ORDER BY open_time"
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _bucket_long_time(short_open: int, long_step: int) -> int:
    return (short_open // long_step) * long_step


def run(symbol: str, *, pair_filter=None) -> dict:
    if not cfg.A4_ENABLED:
        return {"enabled": False}

    pairs = pair_filter or cfg.A4_PAIRS
    results = []

    for short_tf, long_tf, ratio in pairs:
        short_step = INTERVAL_MS[short_tf]
        long_step = INTERVAL_MS[long_tf]

        # Load last 500 long bars to bound the workload
        long_rows = _load(symbol, long_tf)
        if not long_rows:
            continue
        long_rows = long_rows[-500:]

        # Load matching short bars
        start_ms = long_rows[0][0]
        short_rows = _load(symbol, short_tf, start_ms=start_ms)
        if not short_rows:
            continue

        short_by_bucket: dict[int, list] = defaultdict(list)
        for sr in short_rows:
            bucket = _bucket_long_time(sr[0], long_step)
            short_by_bucket[bucket].append(sr)

        mismatches = []
        for lr in long_rows:
            lot, lo, lh, ll, lc, lv = lr
            group = short_by_bucket.get(lot, [])
            if len(group) != ratio:
                # incomplete group; skip (could be boundary)
                continue
            sum_vol = sum(g[5] for g in group)
            max_high = max(g[2] for g in group)
            min_low = min(g[3] for g in group)
            first_open = group[0][1]
            last_close = group[-1][4]

            if lv > 0:
                vol_diff = abs(sum_vol - lv) / lv
                if vol_diff > cfg.A4_VOLUME_TOLERANCE:
                    mismatches.append({
                        "bucket": lot, "field": "volume",
                        "long": lv, "short_sum": sum_vol,
                        "diff_pct": round(vol_diff * 100, 4),
                    })
            if lh < max_high:
                mismatches.append({
                    "bucket": lot, "field": "high",
                    "long": lh, "short_max": max_high,
                })
            if ll > min_low:
                mismatches.append({
                    "bucket": lot, "field": "low",
                    "long": ll, "short_min": min_low,
                })

        results.append({
            "short": short_tf,
            "long": long_tf,
            "checked": len(long_rows),
            "mismatch_count": len(mismatches),
            "mismatches": mismatches[:30],
        })

    return {"enabled": True, "symbol": symbol, "pairs": results}
