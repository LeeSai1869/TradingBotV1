# ======================================================
# FEATURE — ATR
# ======================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd
from .pine_math import rma, true_range


ATR_LEN = 10
ATR_MA_LEN = 14


@dataclass
class ATRFeatures:
    atr: Optional[float] = None
    prev_atr: Optional[float] = None
    atr_percent: Optional[float] = None
    atr_ma: Optional[float] = None
    atr_ma_ratio: Optional[float] = None
    atr_change: Optional[float] = None


def _atr(high, low, close, length):
    return rma(true_range(high, low, close), length)


def compute(df: pd.DataFrame) -> ATRFeatures:
    if df is None or df.empty:
        return ATRFeatures()
    series = _atr(df["high"], df["low"], df["close"], ATR_LEN)
    atr = float(series.iloc[-1])
    prev = float(series.iloc[-2]) if len(series) > 1 else None
    ma = float(series.rolling(ATR_MA_LEN).mean().iloc[-1])
    ratio = atr / ma if ma and ma > 0 else None
    change = (atr - prev) if prev is not None else None
    c = float(df["close"].iloc[-1])
    pct = atr / c if c else None
    return ATRFeatures(
        atr=atr, prev_atr=prev, atr_percent=pct,
        atr_ma=ma, atr_ma_ratio=ratio, atr_change=change,
    )

# ---- Registry declaration ----
NAME = "atr"
INPUTS = ("df",)
OUTPUT_FIELDS = ("atr","prev_atr","atr_percent","atr_ma","atr_ma_ratio","atr_change")
