# ============================================================
# binance_historical_source.py
# Binance historical candle data source
# ============================================================

import time
import requests


BINANCE_REST_URL = "https://api.binance.com/api/v3/klines"

MAX_CANDLES_PER_REQUEST = 1000


def fetch_binance_klines(
    *,
    symbol: str,
    interval: str,
    start_time: int,
    end_time: int | None = None,
):
    """
    Fetch historical Binance spot candles.

    Times are Unix milliseconds.

    Returns:
        list of raw Binance kline rows.
    """

    all_rows = []

    current_start = start_time

    while True:

        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "limit": MAX_CANDLES_PER_REQUEST,
        }

        if end_time is not None:
            params["endTime"] = end_time

        response = requests.get(
            BINANCE_REST_URL,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        rows = response.json()

        if not rows:
            break

        all_rows.extend(rows)

        last_open_time = rows[-1][0]

        # Prevent accidental infinite loops.
        if last_open_time <= current_start:
            break

        current_start = last_open_time + 1

        if end_time is not None and current_start >= end_time:
            break

        if len(rows) < MAX_CANDLES_PER_REQUEST:
            break

        # Be polite to the API.
        time.sleep(0.05)

    return all_rows

def normalize_binance_kline(
    row,
    bar_index: int,
):
    """
    Convert a Binance kline into the project's
    normalized candle structure.
    """

    return {
        "bar_index": bar_index,

        "bar_time": int(row[0]),

        "open_price": float(row[1]),
        "high_price": float(row[2]),
        "low_price": float(row[3]),
        "close_price": float(row[4]),

        "volume": float(row[5]),

        "close_time": int(row[6]),

        "quote_volume": float(row[7]),
        "trade_count": int(row[8]),

        "taker_buy_base_volume": float(row[9]),
        "taker_buy_quote_volume": float(row[10]),
    }