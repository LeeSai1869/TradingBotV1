from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd

@dataclass
class EMAStructureFeatures:
    ema_bull_structure: bool = False
    ema_bear_structure: bool = False
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

def compute(df, context):
    if df is None or df.empty: return EMAStructureFeatures()
    c=float(df["close"].iloc[-1])
    e7=context["ema7"]; pe7=context["prev_ema7"]
    e25=context["ema25"]; pe25=context["prev_ema25"]
    e50=context["ema50"]; pe50=context["prev_ema50"]
    e100=context["ema100"]; pe100=context["prev_ema100"]
    e200=context["ema200"]; pe200=context["prev_ema200"]
    e300=context["ema300"]; pe300=context["prev_ema300"]
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

    return EMAStructureFeatures(
        ema_bull_structure=bull_struct,
        ema_bear_structure=bear_struct,
        ema50_distance_pct=abs(c - e50) / c * 100 if c else None,
        ema200_distance_pct=abs(c - e200) / c * 100 if c else None,
        ema300_distance_pct=abs(c - e300) / c * 100 if c else None,
        ema50_slope_pct=(e50 - pe50) / pe50 * 100 if pe50 else 0.0,
        ema200_slope_pct=(e200 - pe200) / pe200 * 100 if pe200 else 0.0,
        ema300_slope_pct=(e300 - pe300) / pe300 * 100 if pe300 else 0.0,
        ema50_200_gap_pct=abs(e50 - e200) / e200 * 100 if e200 else 0.0,
        nearest_buy_ema=nb,
        nearest_buy_ema_distance=nbd,
        nearest_buy_ema_distance_pct=nbp,
        nearest_sell_ema=ns,
        nearest_sell_ema_distance=nsd,
        nearest_sell_ema_distance_pct=nsp,
    )

NAME="ema_structure"
INPUTS=("df","context")
OUTPUT_FIELDS=('ema_bull_structure', 'ema_bear_structure', 'ema50_distance_pct', 'ema200_distance_pct', 'ema300_distance_pct', 'ema50_slope_pct', 'ema200_slope_pct', 'ema300_slope_pct', 'ema50_200_gap_pct', 'nearest_buy_ema', 'nearest_buy_ema_distance', 'nearest_buy_ema_distance_pct', 'nearest_sell_ema', 'nearest_sell_ema_distance', 'nearest_sell_ema_distance_pct')
