"""Fetch the CURRENT (un-closed) bar from Binance REST.

Uses /api/v3/klines with limit=1 and does NOT filter closed bars.
The returned bar's close time is in the future — it is the forming bar.
"""
from __future__ import annotations
import json
import urllib.parse
import urllib.request

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"


def fetch_forming_candle(symbol: str, interval: str):
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": interval,
        "limit": 1,
    })
    url = BINANCE_KLINES + "?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "Chart/1.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        page = json.loads(resp.read().decode("utf-8"))
    if not page:
        return None
    k = page[0]
    return {
        "time": int(k[0]) // 1000,          # open time in seconds
        "open": float(k[1]),
        "high": float(k[2]),
        "low": float(k[3]),
        "close": float(k[4]),
        "volume": float(k[5]),
    }
