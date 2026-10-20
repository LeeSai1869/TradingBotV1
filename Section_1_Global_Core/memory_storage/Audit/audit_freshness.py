"""A5 — Freshness audit.

For each (symbol, interval) pair, verifies that the latest stored
bar is within `multiplier × interval_ms` of now.
"""

from __future__ import annotations

import sqlite3
import time

from . import audit_config as cfg
from .audit_schema import INTERVAL_MS


def _last_close_time(symbol: str, interval: str) -> int | None:
    conn = sqlite3.connect(str(cfg.KLINES_DB))
    try:
        cur = conn.execute(
            "SELECT close_time FROM klines WHERE symbol=? AND interval=? ORDER BY open_time DESC LIMIT 1",
            (symbol, interval),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None
    finally:
        conn.close()


def run(pairs: list[tuple[str, str]]) -> dict:
    """pairs: list of (symbol, interval)."""
    if not cfg.A5_ENABLED:
        return {"enabled": False}

    now_ms = int(time.time() * 1000)
    stale = []
    fresh = 0
    missing = 0

    for symbol, interval in pairs:
        step = INTERVAL_MS.get(interval)
        if step is None:
            continue
        last = _last_close_time(symbol, interval)
        if last is None:
            missing += 1
            continue
        age_ms = now_ms - last
        threshold = step * cfg.A5_FRESHNESS_MULTIPLIER
        if age_ms > threshold:
            stale.append({
                "symbol": symbol,
                "interval": interval,
                "last_close_ms": last,
                "age_ms": age_ms,
                "threshold_ms": int(threshold),
                "age_intervals": round(age_ms / step, 2),
            })
        else:
            fresh += 1

    return {
        "enabled": True,
        "checked": len(pairs),
        "fresh": fresh,
        "stale": stale,
        "stale_count": len(stale),
        "missing": missing,
    }
