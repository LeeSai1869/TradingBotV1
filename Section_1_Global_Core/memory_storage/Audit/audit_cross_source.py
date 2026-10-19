"""A3 — Cross-source audit.

Randomly samples rows from klines.db and re-fetches from Binance
to verify byte-for-byte agreement. Expensive; runs daily.
"""

from __future__ import annotations

import json
import random
import sqlite3
import urllib.parse
import urllib.request

from . import audit_config as cfg
from .audit_schema import INTERVAL_MS


_BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"


def _sample_rows(symbol: str, interval: str, n: int):
    conn = sqlite3.connect(str(cfg.KLINES_DB))
    try:
        cur = conn.execute(
            "SELECT open_time, open, high, low, close, volume, close_time "
            "FROM klines WHERE symbol=? AND interval=? "
            "ORDER BY open_time DESC LIMIT 500",
            (symbol, interval),
        )
        pool = cur.fetchall()
    finally:
        conn.close()

    if not pool:
        return []
    k = min(n, len(pool))
    return random.sample(pool, k)


def _refetch_one(symbol: str, interval: str, open_time: int):
    params = urllib.parse.urlencode({
        "symbol": symbol, "interval": interval,
        "startTime": open_time, "limit": 1,
    })
    url = _BINANCE_KLINES_URL + "?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "ScalpV1-Audit/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        page = json.loads(resp.read().decode("utf-8"))
    if not page:
        return None
    k = page[0]
    return {
        "open_time": int(k[0]),
        "open": float(k[1]),
        "high": float(k[2]),
        "low": float(k[3]),
        "close": float(k[4]),
        "volume": float(k[5]),
        "close_time": int(k[6]),
    }


def _close(a, b) -> bool:
    """Floats agree within 1e-9 relative."""
    if a == b:
        return True
    denom = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / denom < 1e-9


def run(symbol: str, interval: str, sample: int | None = None) -> dict:
    if not cfg.A3_ENABLED:
        return {"enabled": False}

    n = sample or cfg.A3_SAMPLE_PER_PAIR
    rows = _sample_rows(symbol, interval, n)

    mismatches = []
    errors = []

    for (ot, o, h, l, c, v, ct) in rows:
        try:
            remote = _refetch_one(symbol, interval, ot)
        except Exception as e:
            errors.append({"open_time": ot, "error": str(e)})
            continue
        if remote is None:
            errors.append({"open_time": ot, "error": "empty_response"})
            continue

        for field, local in (("open", o), ("high", h), ("low", l),
                             ("close", c), ("volume", v)):
            if not _close(local, remote[field]):
                mismatches.append({
                    "open_time": ot,
                    "field": field,
                    "local": local,
                    "remote": remote[field],
                })
        if ct != remote["close_time"]:
            mismatches.append({
                "open_time": ot, "field": "close_time",
                "local": ct, "remote": remote["close_time"],
            })

    return {
        "enabled": True,
        "symbol": symbol,
        "interval": interval,
        "sampled": len(rows),
        "mismatches": mismatches[:50],
        "mismatch_count": len(mismatches),
        "errors": errors[:20],
        "error_count": len(errors),
    }
