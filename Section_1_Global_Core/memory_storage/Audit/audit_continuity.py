"""A2 — Continuity audit.

Detects gaps and overlaps in a (symbol, interval) series.
Optionally refetches missing bars from Binance.
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import audit_config as cfg


INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000,
    "4h": 14_400_000, "6h": 21_600_000, "8h": 28_800_000,
    "12h": 43_200_000, "1d": 86_400_000, "3d": 259_200_000,
    "1w": 604_800_000, "1M": 2_592_000_000,
}

_BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

_KNOWN_GAPS_PATH = cfg.LOG_DIR.parent / "known_gaps.json"
_KNOWN_GAPS_CACHE = None


def _load_known_gaps():
    global _KNOWN_GAPS_CACHE
    if _KNOWN_GAPS_CACHE is not None:
        return _KNOWN_GAPS_CACHE
    if not _KNOWN_GAPS_PATH.exists():
        _KNOWN_GAPS_CACHE = []
        return _KNOWN_GAPS_CACHE
    import json as _j
    _KNOWN_GAPS_CACHE = _j.loads(_KNOWN_GAPS_PATH.read_text())
    return _KNOWN_GAPS_CACHE


def _is_known(symbol, interval, start_ms, end_ms):
    for g in _load_known_gaps():
        if (g["symbol"] == symbol and g["interval"] == interval
                and g["from_ms"] == start_ms and g["to_ms"] == end_ms):
            return True
    return False


def _load_timestamps(symbol: str, interval: str) -> list[int]:
    conn = sqlite3.connect(str(cfg.KLINES_DB))
    try:
        cur = conn.execute(
            "SELECT open_time FROM klines "
            "WHERE symbol=? AND interval=? ORDER BY open_time",
            (symbol, interval),
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def _find_gaps(times: list[int], step: int) -> list[tuple[int, int]]:
    """Return list of (start_ms, end_ms) gaps (inclusive-exclusive)."""
    gaps = []
    for i in range(1, len(times)):
        delta = times[i] - times[i - 1]
        if delta > step:
            gaps.append((times[i - 1] + step, times[i]))
        # delta < step means overlap; handled separately
    return gaps


def _find_overlaps(times: list[int]) -> list[int]:
    seen = set()
    dups = []
    for t in times:
        if t in seen:
            dups.append(t)
        else:
            seen.add(t)
    return dups


def _next_month_open_ms(open_ms: int) -> int:
    """Given this 1M bar's open_time (1st of month, 00:00 UTC), return
    the open_time of the next month's bar (1st of next month, 00:00 UTC)."""
    import datetime as _dt
    dt = _dt.datetime.fromtimestamp(open_ms / 1000, _dt.timezone.utc)
    year, month = dt.year, dt.month + 1
    if month > 12:
        month, year = 1, year + 1
    nxt = _dt.datetime(year, month, 1, tzinfo=_dt.timezone.utc)
    return int(nxt.timestamp() * 1000)


def _find_monthly_gaps(times: list[int]) -> list[tuple[int, int]]:
    """Return (expected_next_open, actual_next_open) for skipped months."""
    gaps = []
    for i in range(1, len(times)):
        expected = _next_month_open_ms(times[i - 1])
        if times[i] != expected:
            gaps.append((expected, times[i]))
    return gaps


def _refetch_range(symbol: str, interval: str, start_ms: int, end_ms: int) -> int:
    """Fetch bars in [start_ms, end_ms) and insert into klines.db.

    Returns rows inserted. Never inserts forming bars.
    """
    step = INTERVAL_MS[interval]
    now_ms = int(time.time() * 1000)
    inserted = 0
    cursor = start_ms

    while cursor < end_ms:
        params = urllib.parse.urlencode({
            "symbol": symbol,
            "interval": interval,
            "startTime": cursor,
            "limit": 1000,
        })
        url = _BINANCE_KLINES_URL + "?" + params
        req = urllib.request.Request(
            url, headers={"User-Agent": "ScalpV1-Audit/1.0"}
        )
        try:
            with urllib.request.urlopen(
                req, timeout=cfg.A2_REFETCH_TIMEOUT_S
            ) as resp:
                page = json.loads(resp.read().decode("utf-8"))
        except Exception:
            break
        if not page:
            break

        rows = []
        for k in page:
            ct = int(k[6])
            if ct >= now_ms:
                continue
            ot = int(k[0])
            if ot >= end_ms:
                break
            rows.append((
                symbol, interval, ot,
                float(k[1]), float(k[2]), float(k[3]), float(k[4]),
                float(k[5]), ct,
            ))

        if rows:
            conn = sqlite3.connect(str(cfg.KLINES_DB))
            try:
                cur = conn.executemany(
                    "INSERT OR IGNORE INTO klines "
                    "(symbol, interval, open_time, open, high, low, close, "
                    "volume, close_time) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    rows,
                )
                conn.commit()
                inserted += cur.rowcount
            finally:
                conn.close()

        last_close = int(page[-1][6])
        cursor = last_close + 1

    return inserted


def run(symbol: str, interval: str, *, refetch: bool | None = None) -> dict:
    if not cfg.A2_ENABLED:
        return {"enabled": False, "symbol": symbol, "interval": interval}

    if refetch is None:
        refetch = cfg.A2_AUTO_REFETCH

    step = INTERVAL_MS.get(interval)
    if step is None:
        return {"enabled": True, "symbol": symbol, "interval": interval,
                "error": "unknown_interval"}

    # 1M has variable-length months. Use month-boundary check.
    if interval == "1M":
        times = _load_timestamps(symbol, interval)
        raw_gaps = _find_monthly_gaps(times)
        gaps, known_gaps = [], []
        for (s, e) in raw_gaps:
            (known_gaps if _is_known(symbol, interval, s, e) else gaps).append((s, e))
        return {
            "enabled": True,
            "symbol": symbol,
            "interval": interval,
            "rows": len(times),
            "gaps": gaps[: cfg.A2_MAX_GAPS_REPORTED],
            "gap_count": len(gaps),
            "known_gaps": known_gaps[: cfg.A2_MAX_GAPS_REPORTED],
            "known_gap_count": len(known_gaps),
            "overlaps": [],
            "overlap_count": 0,
            "refetch": None,
            "still_broken": len(gaps) > 0,
        }

    times = _load_timestamps(symbol, interval)
    if not times:
        return {"enabled": True, "symbol": symbol, "interval": interval,
                "rows": 0, "gaps": [], "overlaps": []}

    raw_gaps = _find_gaps(times, step)
    overlaps = _find_overlaps(times)

    gaps = []
    known_gaps = []
    for (s, e) in raw_gaps:
        if _is_known(symbol, interval, s, e):
            known_gaps.append((s, e))
        else:
            gaps.append((s, e))

    refetch_result = None
    if refetch and gaps:
        total_inserted = 0
        for start, end in gaps:
            total_inserted += _refetch_range(symbol, interval, start, end)
        refetch_result = {"attempted": len(gaps), "inserted": total_inserted}

        # Re-check after refetch
        times2 = _load_timestamps(symbol, interval)
        gaps2 = _find_gaps(times2, step)
        still_broken = len(gaps2) > 0
    else:
        still_broken = len(gaps) > 0

    return {
        "enabled": True,
        "symbol": symbol,
        "interval": interval,
        "rows": len(times),
        "gaps": gaps[: cfg.A2_MAX_GAPS_REPORTED],
        "gap_count": len(gaps),
        "known_gaps": known_gaps[: cfg.A2_MAX_GAPS_REPORTED],
        "known_gap_count": len(known_gaps),
        "overlaps": overlaps[: cfg.A2_MAX_GAPS_REPORTED],
        "overlap_count": len(overlaps),
        "refetch": refetch_result,
        "still_broken": still_broken,
    }
