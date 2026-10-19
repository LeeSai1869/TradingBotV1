"""A1 — Schema audit.

Checks each row for structural validity. Never modifies the DB.
Returns failures to the caller; caller decides what to do.
"""

from __future__ import annotations

from typing import Iterable

from . import audit_config as cfg


INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000, "3d": 259_200_000,
    "1w": 604_800_000, "1M": 2_592_000_000,
}


def _check_row(row) -> str | None:
    """Return None if valid, else a reason string.

    row is a tuple:
        (symbol, interval, open_time, open, high, low, close, volume, close_time)
    """
    (symbol, interval, open_time, o, h, l, c, v, close_time) = row

    if not isinstance(symbol, str) or not symbol:
        return "bad_symbol"
    if interval not in INTERVAL_MS:
        return "bad_interval"
    if not isinstance(open_time, int) or open_time <= 0:
        return "bad_open_time"
    if not isinstance(close_time, int) or close_time <= 0:
        return "bad_close_time"
    if close_time <= open_time:
        return "close_le_open"

    # Fixed-duration intervals: close_time - open_time == interval_ms - 1.
    # Variable-length intervals (months) close at different offsets.
    if interval not in ("1M",):
        expected_span = INTERVAL_MS[interval] - 1
        if close_time - open_time != expected_span:
            return "close_open_mismatch"
    else:
        # Month bars: 28-31 days. Enforce a generous window.
        span = close_time - open_time
        if span < 27 * 86_400_000 or span > 32 * 86_400_000:
            return "close_open_mismatch"

    for name, val in (("open", o), ("high", h), ("low", l),
                      ("close", c), ("volume", v)):
        if val is None:
            return "null_" + name
        try:
            float(val)
        except (TypeError, ValueError):
            return "non_numeric_" + name

    if l > min(o, c):
        return "low_gt_min_oc"
    if h < max(o, c):
        return "high_lt_max_oc"
    if h < l:
        return "high_lt_low"
    if v < 0:
        return "negative_volume"

    return None


def run(rows: Iterable[tuple]) -> dict:
    """Check a batch of rows. Returns a summary dict.

    rows: iterable of 9-tuples matching klines.db schema.
    """
    if not cfg.A1_ENABLED:
        return {"enabled": False, "checked": 0, "failed": 0, "failures": []}

    checked = 0
    failures = []
    for row in rows:
        checked += 1
        reason = _check_row(row)
        if reason:
            failures.append({
                "symbol": row[0] if len(row) > 0 else None,
                "interval": row[1] if len(row) > 1 else None,
                "open_time": row[2] if len(row) > 2 else None,
                "reason": reason,
            })
            if len(failures) >= cfg.A1_MAX_FAILURES_REPORTED:
                break

    return {
        "enabled": True,
        "checked": checked,
        "failed": len(failures),
        "failures": failures,
    }
