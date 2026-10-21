from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd
from . import trend, ema_structure, price_location

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



def compute(df):
    context=vars(trend.compute(df))
    context.update(vars(ema_structure.compute(df,context)))
    context.update(vars(price_location.compute(df,context)))
    return EMAFeatures(**context)

_ema=trend._ema
NAME="ema"
INPUTS=("df",)
OUTPUT_FIELDS=('ema7', 'ema25', 'ema50', 'ema100', 'ema200', 'ema300', 'prev_ema7', 'prev_ema25', 'prev_ema50', 'prev_ema100', 'prev_ema200', 'prev_ema300', 'ema_gap_7_25', 'ema_gap_25_50', 'ema_gap_50_100', 'ema_gap_7_25_pct', 'ema_gap_25_50_pct', 'ema_gap_50_100_pct', 'ema_compression', 'ema_bull_structure', 'ema_bear_structure', 'price_above_ema50', 'price_below_ema50', 'price_above_ema200', 'price_below_ema200', 'price_above_ema300', 'price_below_ema300', 'ema50_distance_pct', 'ema200_distance_pct', 'ema300_distance_pct', 'ema50_slope_pct', 'ema200_slope_pct', 'ema300_slope_pct', 'ema50_200_gap_pct', 'nearest_buy_ema', 'nearest_buy_ema_distance', 'nearest_buy_ema_distance_pct', 'nearest_sell_ema', 'nearest_sell_ema_distance', 'nearest_sell_ema_distance_pct')
