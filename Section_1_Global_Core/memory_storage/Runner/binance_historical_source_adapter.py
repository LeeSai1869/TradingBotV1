# ============================================================
# Binance historical source adapter
# ============================================================

from Section_1_Global_Core.memory_storage.Runner.binance_historical_source import (
    fetch_binance_klines,
    normalize_binance_kline,
)


def binance_candle_source(
    *,
    symbol: str,
    timeframe: str,
    start_time: int,
    end_time: int | None = None,
):

    rows = fetch_binance_klines(
        symbol=symbol,
        interval=timeframe,
        start_time=start_time,
        end_time=end_time,
    )

    candles = []

    for index, row in enumerate(rows):

        candle = normalize_binance_kline(
            row,
            bar_index=index,
        )

        candles.append(candle)

    return candles