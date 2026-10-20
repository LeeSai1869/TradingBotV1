"""Fetch the CURRENT (un-closed) bar from Binance REST.

Uses /api/v3/klines with limit=1 and does NOT filter closed bars.
The returned bar's close time is in the future — it is the forming bar.
"""
from __future__ import annotations
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
        "open_time": int(k[0]),
        "close_time": int(k[6]),
        "time": int(k[0]) // 1000,          # open time in seconds
        "open": float(k[1]),
        "high": float(k[2]),
        "low": float(k[3]),
        "close": float(k[4]),
        "volume": float(k[5]),
    }


# Exchange I/O runs outside HTTP dispatch. A slow/failed live feed must never
# hold up SQLite history reads. Latest-page requests share one snapshot per key.
class FormingCandleCache:
    def __init__(self, fetcher=None, *, poll_seconds=1.0, stale_seconds=5.0,
                 clock=time.monotonic, wall_clock=time.time):
        self.fetcher = fetcher
        self.poll_seconds = poll_seconds
        self.stale_seconds = stale_seconds
        self.clock = clock
        self.wall_clock = wall_clock
        self._lock = threading.Lock()
        self._entries = {}
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="forming-candle")

    def snapshot(self, symbol, interval):
        key = (symbol, interval)
        now = self.clock()
        with self._lock:
            # Idle selections stop requesting exchange data. Bound retained
            # snapshots so repeatedly changing markets cannot grow this cache.
            for old_key, old in list(self._entries.items()):
                if not old['pending'] and now - old['requested'] > 60:
                    del self._entries[old_key]
            entry = self._entries.get(key)
            if entry is None:
                if len(self._entries) >= 64:
                    return {"bar": None, "status": "unavailable", "error": "Live feed busy"}
                entry = {"bar": None, "requested": float('-inf'), "received": float('-inf'),
                         "as_of": None, "pending": False, "error": None}
                self._entries[key] = entry
            if not entry['pending'] and now - entry['requested'] >= self.poll_seconds:
                entry['pending'] = True
                entry['requested'] = now
                self._pool.submit(self._refresh, key, entry)
            bar = entry['bar']
            if (now - entry['received'] > self.stale_seconds or
                    (bar and bar['client']['close_time'] < int(self.wall_clock()*1000))):
                bar = None
            return {"bar": bar, "status": "live" if bar else
                    ("loading" if entry['pending'] and not entry['error'] else "unavailable"),
                    "as_of": entry['as_of'], "error": entry['error']}

    def _refresh(self, key, entry):
        try:
            symbol, interval = key
            raw = (self.fetcher or fetch_forming_candle)(symbol, interval)
            bar = None
            if raw is not None:
                open_time = int(raw.get('open_time', raw['time']*1000))
                close_time = int(raw['close_time'])
                values = {name: float(raw[name]) for name in ('open','high','low','close','volume')}
                if not all(math.isfinite(value) for value in values.values()):
                    raise ValueError('Non-finite forming candle')
                if close_time >= int(self.wall_clock()*1000):
                    bar = {"symbol": symbol, "interval": interval, "open_time": open_time,
                           "time": open_time//1000, "provisional": True,
                           "client": {"symbol": symbol, "interval": interval,
                                      "open_time": open_time, "close_time": close_time, **values},
                           "features": None, "adcn": None}
            if bar is not None:
                try:
                    from .live_features import calculate
                    bar['features'] = calculate(symbol, interval, bar['client'])
                    bar['features_status'] = 'provisional' if bar['features'] else 'waiting for stored history'
                except Exception as feature_error:
                    # Missing dependencies/history must not interrupt the price feed.
                    bar['features_status'] = 'unavailable'
                    bar['features_error'] = str(feature_error)
            with self._lock:
                entry.update(bar=bar, received=self.clock(), as_of=int(self.wall_clock()*1000), error=None)
        except Exception as error:
            with self._lock:
                entry['error'] = str(error)
        finally:
            with self._lock:
                entry['pending'] = False

    def close(self):
        self._pool.shutdown(wait=True)


_LIVE = FormingCandleCache()


def get_snapshot(symbol, interval):
    return _LIVE.snapshot(symbol, interval)
