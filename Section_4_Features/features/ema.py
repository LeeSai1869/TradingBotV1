# ======================================================
# FEATURE — EMA FAMILY
# Pure function of close prices.
# ======================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd

from Section_2_Inputs.Inputs import (
    EMA_7_LEN, EMA_25_LEN, EMA_50_LEN,
    EMA_100_LEN, EMA_200_LEN, EMA_300_LEN,
)


@dataclass
class EMAFeatures:
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

    ema_bull_structure: bool = False
    ema_bear_structure: bool = False

    price_above_ema50: bool = False
    price_below_ema50: bool = False
    price_above_ema200: bool = False
    price_below_ema200: bool = False
    price_above_ema300: bool = False
    price_below_ema300: bool = False

    ema50_distance_pct: Optional[float] = None
    ema200_distance_pct: Optional[float] = None
    ema300_distance_pct: Optional[float] = None

    ema50_slope_pct: float = 0.0
    ema200_slope_pct: float = 0.0
    ema300_slope_pct: float = 0.0
    ema50_200_gap_pct: float = 0.0

    nearest_buy_ema: Optional[float] = None
    nearest_buy_ema_distance: Optional[float] = None
    nearest_buy_ema_distance_pct: Optional[float] = None
    nearest_sell_ema: Optional[float] = None
    nearest_sell_ema_distance: Optional[float] = None
    nearest_sell_ema_distance_pct: Optional[float] = None


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def compute(df: pd.DataFrame) -> EMAFeatures:
    if df is None or df.empty:
        return EMAFeatures()

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

    bull_struct = e7 > e25 > e50 > e100
    bear_struct = e7 < e25 < e50 < e100

    # Nearest EMA above / below price
    emas = [e7, e25, e50, e100, e200, e300]
    nb = ns = None
    nbd = nsd = None
    nbp = nsp = None
    for v in emas:
        d = abs(v - c)
        dp = d / c * 100 if c else None
        if v > c:
            if nbd is None or d < nbd:
                nb, nbd, nbp = v, d, dp
        elif v < c:
            if nsd is None or d < nsd:
                ns, nsd, nsp = v, d, dp

    return EMAFeatures(
        ema7=e7, ema25=e25, ema50=e50, ema100=e100, ema200=e200, ema300=e300,
        prev_ema7=pe7, prev_ema25=pe25, prev_ema50=pe50,
        prev_ema100=pe100, prev_ema200=pe200, prev_ema300=pe300,
        ema_gap_7_25=g_7_25, ema_gap_25_50=g_25_50, ema_gap_50_100=g_50_100,
        ema_gap_7_25_pct=g_7_25_pct, ema_gap_25_50_pct=g_25_50_pct,
        ema_gap_50_100_pct=g_50_100_pct,
        ema_compression=compression,
        ema_bull_structure=bull_struct, ema_bear_structure=bear_struct,
        price_above_ema50=c > e50, price_below_ema50=c < e50,
        price_above_ema200=c > e200, price_below_ema200=c < e200,
        price_above_ema300=c > e300, price_below_ema300=c < e300,
        ema50_distance_pct=abs(c - e50) / c * 100 if c else None,
        ema200_distance_pct=abs(c - e200) / c * 100 if c else None,
        ema300_distance_pct=abs(c - e300) / c * 100 if c else None,
        ema50_slope_pct=((e50 - pe50) / pe50 * 100) if pe50 else 0.0,
        ema200_slope_pct=((e200 - pe200) / pe200 * 100) if pe200 else 0.0,
        ema300_slope_pct=((e300 - pe300) / pe300 * 100) if pe300 else 0.0,
        ema50_200_gap_pct=abs(e50 - e200) / e200 * 100 if e200 else 0.0,
        nearest_buy_ema=nb, nearest_buy_ema_distance=nbd, nearest_buy_ema_distance_pct=nbp,
        nearest_sell_ema=ns, nearest_sell_ema_distance=nsd, nearest_sell_ema_distance_pct=nsp,
    )

# ---- Registry declaration ----
NAME = "ema"
INPUTS = ("df",)
OUTPUT_FIELDS = (
    "ema7","ema25","ema50","ema100","ema200","ema300",
    "prev_ema7","prev_ema25","prev_ema50","prev_ema100","prev_ema200","prev_ema300",
    "ema_gap_7_25","ema_gap_25_50","ema_gap_50_100",
    "ema_gap_7_25_pct","ema_gap_25_50_pct","ema_gap_50_100_pct",
    "ema_compression","ema_bull_structure","ema_bear_structure",
    "price_above_ema50","price_below_ema50","price_above_ema200","price_below_ema200",
    "price_above_ema300","price_below_ema300",
    "ema50_distance_pct","ema200_distance_pct","ema300_distance_pct",
    "ema50_slope_pct","ema200_slope_pct","ema300_slope_pct","ema50_200_gap_pct",
    "nearest_buy_ema","nearest_buy_ema_distance","nearest_buy_ema_distance_pct",
    "nearest_sell_ema","nearest_sell_ema_distance","nearest_sell_ema_distance_pct",
)
