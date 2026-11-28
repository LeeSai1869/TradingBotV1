"""Compare committed candle closes without calculating indicators."""
from contextlib import closing
import math
import time

from Section_1_Global_Core.memory_storage.Storage import db, klines_store

HOUR = 3_600_000
PERIODS = {"1h": HOUR, "4h": 4 * HOUR, "24h": 24 * HOUR, "7d": 168 * HOUR}
FRAMES = {"1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
          "30m": 1_800_000, "1h": HOUR, "2h": 2 * HOUR, "4h": 4 * HOUR,
          "6h": 6 * HOUR, "8h": 8 * HOUR, "12h": 12 * HOUR, "1d": 24 * HOUR}


def _close_at(conn, symbol, interval, cutoff):
    # Fixed-duration candles use close_time = open_time + duration - 1.
    # The open_time bound lets SQLite seek on the existing primary key.
    return conn.execute(
        "SELECT close_time, close FROM klines "
        "WHERE symbol=? AND interval=? AND open_time<=? AND close_time<=? "
        "ORDER BY open_time DESC LIMIT 1",
        (symbol, interval, cutoff - FRAMES[interval] + 1, cutoff),
    ).fetchone()


def _changes(conn, symbols, duration, now):
    for symbol in symbols:
        row = {"symbol": symbol, "change_pct": None, "as_of": None, "stale": False}
        if conn is None:
            yield row
            continue
        available = [(interval, sample) for interval in FRAMES
                     if (sample := _close_at(conn, symbol, interval, now))]
        if not available:
            yield row
            continue
        frame, (end, price) = max(available, key=lambda item: item[1][0])
        row.update(as_of=end, stale=now - end > max(300_000, 2 * FRAMES[frame]))
        cutoff = end - duration
        references = []
        for interval, _ in available:
            if FRAMES[interval] > duration:
                continue
            reference = _close_at(conn, symbol, interval, cutoff)
            if reference and cutoff - reference[0] < FRAMES[interval] and reference[1] > 0:
                references.append(reference)
        if references:
            start, base = max(references, key=lambda sample: sample[0])
            change = (price / base - 1) * 100
            if math.isfinite(change):
                row.update(change_pct=change, reference_at=start)
        yield row


def snapshot(symbols, period, *, now=None):
    now = int(time.time() * 1000) if now is None else now
    if klines_store.DB_PATH.exists():
        with closing(db._read_connection(klines_store.DB_PATH)) as conn:
            conn.execute("BEGIN")
            rows = list(_changes(conn, symbols, PERIODS[period], now))
    else:
        rows = list(_changes(None, symbols, PERIODS[period], now))
    return {"period": period, "rows": rows}
