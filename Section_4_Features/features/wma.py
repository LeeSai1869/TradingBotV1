# ======================================================
# FEATURE — WMA FAMILY
# ======================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


WMA_50_LEN = 50


@dataclass
class WMAFeatures:
    wma50: Optional[float] = None
    wma50_distance: Optional[float] = None
    wma50_distance_pct: Optional[float] = None


def _wma(series: pd.Series, length: int) -> pd.Series:
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


def compute(df: pd.DataFrame) -> WMAFeatures:
    if df is None or df.empty or len(df) < WMA_50_LEN:
        return WMAFeatures()

    c = float(df["close"].iloc[-1])
    w = float(_wma(df["close"], WMA_50_LEN).iloc[-1])
    d = abs(w - c)
    dp = d / c * 100 if c else None
    return WMAFeatures(wma50=w, wma50_distance=d, wma50_distance_pct=dp)

# ---- Registry declaration ----
NAME = "wma"
INPUTS = ("df",)
OUTPUT_FIELDS = ("wma50","wma50_distance","wma50_distance_pct")
