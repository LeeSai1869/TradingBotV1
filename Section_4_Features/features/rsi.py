# ======================================================
# FEATURE — RSI
# ======================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd


RSI_LEN = 7


@dataclass
class RSIFeatures:
    rsi: Optional[float] = None
    prev_rsi: Optional[float] = None
    rsi_change: Optional[float] = None


def _rsi(series: pd.Series, length: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute(df: pd.DataFrame) -> RSIFeatures:
    if df is None or df.empty:
        return RSIFeatures()
    series = _rsi(df["close"], RSI_LEN)
    r = series.iloc[-1]
    p = series.iloc[-2] if len(series) > 1 else None
    r = float(r) if r is not None and not pd.isna(r) else None
    p = float(p) if p is not None and not pd.isna(p) else None
    ch = (r - p) if r is not None and p is not None else None
    return RSIFeatures(rsi=r, prev_rsi=p, rsi_change=ch)

# ---- Registry declaration ----
NAME = "rsi"
INPUTS = ("df",)
OUTPUT_FIELDS = ("rsi","prev_rsi","rsi_change")
