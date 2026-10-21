from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd
from Section_2_Inputs.Inputs import EMA_7_LEN, EMA_25_LEN, EMA_50_LEN, EMA_100_LEN, EMA_200_LEN, EMA_300_LEN

@dataclass
class TrendFeatures:
    ema7: Optional[float] = None
    ema25: Optional[float] = None
    ema50: Optional[float] = None
    ema100: Optional[float] = None
    ema200: Optional[float] = None
    ema300: Optional[float] = None
    prev_ema7: Optional[float] = None
    prev_ema25: Optional[float] = None
    prev_ema50: Optional[float] = None
    prev_ema100: Optional[float] = None
    prev_ema200: Optional[float] = None
    prev_ema300: Optional[float] = None
    ema_gap_7_25: Optional[float] = None
    ema_gap_25_50: Optional[float] = None
    ema_gap_50_100: Optional[float] = None
    ema_gap_7_25_pct: Optional[float] = None
    ema_gap_25_50_pct: Optional[float] = None
    ema_gap_50_100_pct: Optional[float] = None
    ema_compression: Optional[float] = None

def _ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def compute(df):
    if df is None or df.empty: return TrendFeatures()
    close = df["close"]
    c = float(close.iloc[-1])
    has_prev = len(df) > 1

    e7 = float(_ema(close, EMA_7_LEN).iloc[-1])
    e25 = float(_ema(close, EMA_25_LEN).iloc[-1])
    e50 = float(_ema(close, EMA_50_LEN).iloc[-1])
    e100 = float(_ema(close, EMA_100_LEN).iloc[-1])
    e200 = float(_ema(close, EMA_200_LEN).iloc[-1])
    e300 = float(_ema(close, EMA_300_LEN).iloc[-1])

    pe7 = float(_ema(close, EMA_7_LEN).iloc[-2]) if has_prev else None
    pe25 = float(_ema(close, EMA_25_LEN).iloc[-2]) if has_prev else None
    pe50 = float(_ema(close, EMA_50_LEN).iloc[-2]) if has_prev else None
    pe100 = float(_ema(close, EMA_100_LEN).iloc[-2]) if has_prev else None
    pe200 = float(_ema(close, EMA_200_LEN).iloc[-2]) if has_prev else None
    pe300 = float(_ema(close, EMA_300_LEN).iloc[-2]) if has_prev else None

    g_7_25 = abs(e7 - e25)
    g_25_50 = abs(e25 - e50)
    g_50_100 = abs(e50 - e100)

    g_7_25_pct = g_7_25 / c if c else None
    g_25_50_pct = g_25_50 / c if c else None
    g_50_100_pct = g_50_100 / c if c else None

    compression = None
    if g_7_25_pct is not None and g_25_50_pct is not None and g_50_100_pct is not None:
        compression = (g_7_25_pct + g_25_50_pct + g_50_100_pct) / 3.0

    return TrendFeatures(
        ema7=e7,
        ema25=e25,
        ema50=e50,
        ema100=e100,
        ema200=e200,
        ema300=e300,
        prev_ema7=pe7,
        prev_ema25=pe25,
        prev_ema50=pe50,
        prev_ema100=pe100,
        prev_ema200=pe200,
        prev_ema300=pe300,
        ema_gap_7_25=g_7_25,
        ema_gap_25_50=g_25_50,
        ema_gap_50_100=g_50_100,
        ema_gap_7_25_pct=g_7_25_pct,
        ema_gap_25_50_pct=g_25_50_pct,
        ema_gap_50_100_pct=g_50_100_pct,
        ema_compression=compression,
    )

NAME="trend"
INPUTS=("df",)
OUTPUT_FIELDS=('ema7', 'ema25', 'ema50', 'ema100', 'ema200', 'ema300', 'prev_ema7', 'prev_ema25', 'prev_ema50', 'prev_ema100', 'prev_ema200', 'prev_ema300', 'ema_gap_7_25', 'ema_gap_25_50', 'ema_gap_50_100', 'ema_gap_7_25_pct', 'ema_gap_25_50_pct', 'ema_gap_50_100_pct', 'ema_compression')
