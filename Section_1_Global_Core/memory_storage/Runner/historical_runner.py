# ============================================================
# historical_runner.py
# Generic historical candle execution runner
# ============================================================

from typing import Callable, Iterable, Optional


class HistoricalRunner:

    def __init__(
        self,
        *,
        candle_source: Callable,
        processor: Callable,
    ):
        """
        candle_source:
            Function that supplies normalized candles.

        processor:
            Function that processes one candle through
            the existing engine / packet pipeline.
        """

        self.candle_source = candle_source
        self.processor = processor

    def run(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_time: int,
        end_time: Optional[int] = None,
    ):

        candles = self.candle_source(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
        )

        processed_count = 0

        for candle in candles:

            self.processor(
                symbol=symbol,
                timeframe=timeframe,
                candle=candle,
            )

            processed_count += 1

        return processed_count