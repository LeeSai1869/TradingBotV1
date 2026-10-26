"""
================================================================================
MARKET DATA — Binance History Downloader
================================================================================

Fetches historical klines from Binance and stores them in market_data/klines.db.

INVARIANT:
    Every stored candle has close_time < now_ms, where now_ms is
    measured at the moment insert_page validates the candle.

    No open (forming) candle ever enters the database.

Run once to build local history:
    cd "/Users/jhanzeebakbar/Scalp Indicator V1"
    python3 -m Section_1_Global_Core.memory_storage.market_data.download_binance_history

Interruptible. Re-run to resume from the last stored bar.
================================================================================
"""

from __future__ import annotations

from Section_1_Global_Core import data_policy

import sqlite3
import time
import urllib.request
import urllib.parse
import json as _json
from pathlib import Path
from urllib.error import HTTPError, URLError


# ==============================================================================
# CONFIG
# ==============================================================================

DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "Storage"
    / "klines.db"
)

SYMBOLS = ["BTCUSDT", "SUIUSDT"]

INTERVALS = [
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M",
]

# Optional override for a symbol's earliest kline.
# Set to None to let Binance tell us (recommended).
SYMBOL_START_MS = {
    "BTCUSDT": None,
    "SUIUSDT": None,
}

# Start of the range if Binance doesn't tell us — before any listing.
FALLBACK_START_MS = 1262304000000   # 2010-01-01

# Rate limiting
REQUESTS_PER_SECOND = 3
REQUEST_INTERVAL_S = 1.0 / REQUESTS_PER_SECOND

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
PAGE_LIMIT = 1000


# ==============================================================================
# FETCH ERRORS
# ==============================================================================

class TransientError(Exception):
    """Network timeout or 5xx — retry after a delay."""
    pass

class RateLimitError(Exception):
    """429 — back off and retry."""
    pass

class PermanentError(Exception):
    """Permanent 4xx (other than 429) or malformed response.
    Abort this (symbol, interval) pair."""
    pass

class AbortAllError(Exception):
    """418 (IP banned) or equivalent — abort the entire downloader."""
    pass


# ==============================================================================
# DB
# ==============================================================================

def open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS klines (
                symbol      TEXT NOT NULL,
                interval    TEXT NOT NULL,
                open_time   INTEGER NOT NULL,
                open        REAL NOT NULL,
                high        REAL NOT NULL,
                low         REAL NOT NULL,
                close       REAL NOT NULL,
                volume      REAL NOT NULL,
                close_time  INTEGER NOT NULL,
                PRIMARY KEY (symbol, interval, open_time)
            )
        """)
        conn.commit()
        return conn
    except BaseException:
        conn.close()
        raise


def last_stored_open_time(conn, symbol: str, interval: str):
    cur = conn.execute(
        "SELECT MAX(open_time) FROM klines WHERE symbol=? AND interval=?",
        (symbol, interval),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


def insert_page(conn, symbol, interval, page, now_ms):
    with data_policy.locked():
        if not data_policy.enabled(symbol, interval):
            return 0
        return _insert_page(conn, symbol, interval, page, now_ms)


def _insert_page(conn, symbol, interval, page, now_ms):
    """
    Insert a page of klines. Skips any candle whose close_time >= now_ms.

    This is the ONLY place the closed-candle invariant is enforced.
    The caller passes the raw Binance page; this function decides
    what is safe to store.

    Returns rows actually written (deduped by PK).
    """
    rows = []
    for k in page:
        close_time = int(k[6])
        if close_time >= now_ms:
            continue
        rows.append((
            symbol,
            interval,
            int(k[0]),
            float(k[1]),
            float(k[2]),
            float(k[3]),
            float(k[4]),
            float(k[5]),
            close_time,
        ))

    if not rows:
        return 0

    cur = conn.executemany(
        """
        INSERT OR IGNORE INTO klines
        (symbol, interval, open_time, open, high, low, close, volume, close_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return cur.rowcount


# ==============================================================================
# BINANCE
# ==============================================================================

def fetch_klines(symbol, interval, start_time_ms, limit=PAGE_LIMIT):
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": int(start_time_ms),
        "limit": limit,
    }
    url = BINANCE_KLINES_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "ScalpV1-DL/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return _json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 429:
            raise RateLimitError("Binance 429 (rate limited)")
        if e.code == 418:
            raise AbortAllError("Binance 418 (IP banned)")
        if 500 <= e.code < 600:
            raise TransientError("Binance HTTP " + str(e.code) + " (server error)")
        raise PermanentError("Binance HTTP " + str(e.code) + ": " + str(e.reason))
    except URLError as e:
        raise TransientError("Network error: " + str(e.reason))
    except Exception as e:
        raise PermanentError("Unexpected error: " + str(e))


# ==============================================================================
# DOWNLOAD ONE (symbol, interval)
# ==============================================================================

def download_one(conn, symbol, interval):
    """
    Download one (symbol, interval).

    Returns (rows_inserted, error_message_or_None).

    Raises AbortAllError to stop the entire downloader.
    """
    start_ms = last_stored_open_time(conn, symbol, interval)
    if start_ms is None:
        start_ms = SYMBOL_START_MS.get(symbol) or FALLBACK_START_MS
        status = "fresh from " + str(start_ms)
    else:
        status = "resume from " + str(start_ms)

    print("")
    print("[" + symbol + " " + interval + "] " + status, flush=True)

    total_inserted = 0
    page_count = 0
    last_report = time.time()

    while True:
        if not data_policy.enabled(symbol, interval):
            break
        try:
            page = fetch_klines(symbol, interval, start_ms, limit=PAGE_LIMIT)
        except RateLimitError as e:
            print("[" + symbol + " " + interval + "] " + str(e) + " -- sleeping 60s", flush=True)
            time.sleep(60)
            continue
        except TransientError as e:
            print("[" + symbol + " " + interval + "] " + str(e) + " -- retry in 5s", flush=True)
            time.sleep(5)
            continue
        except PermanentError as e:
            print("[" + symbol + " " + interval + "] PERMANENT: " + str(e) + " -- aborting pair", flush=True)
            return total_inserted, str(e)
        except AbortAllError as e:
            print("[" + symbol + " " + interval + "] ABORT: " + str(e), flush=True)
            raise

        if not page:
            break

        now_ms = int(time.time() * 1000)
        n = insert_page(conn, symbol, interval, page, now_ms)
        total_inserted += n
        page_count += 1

        last_close = int(page[-1][6])
        if last_close >= now_ms:
            break
        start_ms = last_close + 1

        if time.time() - last_report >= 5.0:
            print("[" + symbol + " " + interval + "] page " + str(page_count) +
                  "  inserted " + str(total_inserted) + "  through " + str(start_ms), flush=True)
            last_report = time.time()

        time.sleep(REQUEST_INTERVAL_S)

    print("[" + symbol + " " + interval + "] DONE: +" + str(total_inserted) +
          " rows, " + str(page_count) + " pages", flush=True)
    return total_inserted, None


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    print("=" * 78)
    print("BINANCE HISTORY DOWNLOADER")
    print("=" * 78)
    print("DB        : " + str(DB_PATH))
    print("Symbols   : " + str(data_policy.active_symbols()))
    print("Intervals : " + str(data_policy.active_intervals()))
    print("")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = open_db()

    summary = {}
    failures = []
    t0 = time.time()

    abort_triggered = False

    for symbol in data_policy.active_symbols():
        if abort_triggered:
            break
        for interval in data_policy.active_intervals():
            try:
                n, err = download_one(conn, symbol, interval)
                summary[(symbol, interval)] = n
                if err is not None:
                    failures.append((symbol, interval, err))
            except AbortAllError as e:
                print("")
                print("[ABORT] " + str(e))
                summary[(symbol, interval)] = 0
                failures.append((symbol, interval, str(e)))
                abort_triggered = True
                break

    elapsed = time.time() - t0

    print("")
    print("=" * 78)
    print("DOWNLOAD SUMMARY")
    print("=" * 78)

    grand_total_inserted = 0
    grand_total_rows = 0

    for (symbol, interval), n in summary.items():
        cur = conn.execute(
            "SELECT COUNT(*) FROM klines WHERE symbol=? AND interval=?",
            (symbol, interval),
        )
        total_rows = cur.fetchone()[0]
        grand_total_inserted += n
        grand_total_rows += total_rows
        print("  " + symbol.ljust(8) + "  " + interval.ljust(4) +
              "  +" + str(n).rjust(9) + "  total=" + str(total_rows).rjust(10))

    print("")
    print("  Grand total inserted this run : " + str(grand_total_inserted))
    print("  Grand total rows in DB        : " + str(grand_total_rows))
    print("  Elapsed                       : " + str(round(elapsed, 1)) + " s")

    if failures:
        print("")
        print("  FAILURES:")
        for symbol, interval, err in failures:
            print("    " + symbol.ljust(8) + "  " + interval.ljust(4) + "  " + err)
    else:
        print("  No failures.")

    if abort_triggered:
        print("")
        print("  DOWNLOADER ABORTED — resume later with the same command.")
        conn.close()
        raise SystemExit(1)

    conn.close()


if __name__ == "__main__":
    main()