"""Per-symbol tick size / decimal precision.

Source of truth: Binance exchangeInfo. We cache it in memory and
refresh on process restart (it changes extremely rarely).
"""
from __future__ import annotations
import json
import urllib.request

_CACHE: dict | None = None
_URL = "https://api.binance.com/api/v3/exchangeInfo"


def _load():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    req = urllib.request.Request(_URL, headers={"User-Agent": "Chart/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = {}
    for s in data.get("symbols", []):
        if s.get("quoteAsset") != "USDT":
            continue
        if s.get("status") != "TRADING":
            continue
        # Find the PRICE_FILTER tickSize
        tick = None
        for f in s.get("filters", []):
            if f.get("filterType") == "PRICE_FILTER":
                tick = f.get("tickSize")
                break
        if not tick:
            continue
        # Precision = number of digits after the decimal point in tickSize
        # e.g. "0.00010000" -> 4 ; "0.01000000" -> 2
        try:
            t = tick.rstrip("0")
            if "." in t:
                prec = len(t.split(".")[1])
            else:
                prec = 0
        except Exception:
            prec = 2
        out[s["symbol"]] = {"precision": prec, "tickSize": tick}
    _CACHE = out
    return out


def get_meta(symbol: str):
    meta = _load()
    return meta.get(symbol, {"precision": 2, "tickSize": "0.01"})
