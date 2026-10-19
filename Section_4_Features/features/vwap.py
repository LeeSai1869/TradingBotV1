# ======================================================
# FEATURE — VWAP + BANDS
# Session-anchored VWAP (calendar day UTC).
# ======================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd

from Section_2_Inputs.Inputs import (
    VWAP_BAND_MULTIPLIER_1,
    VWAP_BAND_MULTIPLIER_2,
)


@dataclass
class VWAPFeatures:
    vwap: Optional[float] = None
    vwap_distance: Optional[float] = None
    vwap_distance_pct: Optional[float] = None
    price_above_vwap: bool = False
    price_below_vwap: bool = False
    vwap_upper1: Optional[float] = None
    vwap_lower1: Optional[float] = None
    vwap_upper2: Optional[float] = None
    vwap_lower2: Optional[float] = None
    nearest_buy_vwap: Optional[float] = None
    nearest_buy_vwap_distance: Optional[float] = None
    nearest_buy_vwap_distance_pct: Optional[float] = None
    nearest_buy_vwap_type: str = ""
    nearest_sell_vwap: Optional[float] = None
    nearest_sell_vwap_distance: Optional[float] = None
    nearest_sell_vwap_distance_pct: Optional[float] = None
    nearest_sell_vwap_type: str = ""


def _session_vwap_bands(df: pd.DataFrame, m1: float, m2: float):
    """
    Compute session VWAP from the beginning of the current UTC day
    through the last bar of df.

    Returns (vwap, sd, session_first_price) or (None, None, None) if
    no volume data or the day cannot be determined.
    """
    if "time" not in df.columns and "bar_time" not in df.columns:
        return None, None, None
    if "volume" not in df.columns:
        return None, None, None

    tcol = "time" if "time" in df.columns else "bar_time"
    t = pd.to_datetime(df[tcol], unit="ms", utc=True)
    day = t.dt.floor("D")
    current_day = day.iloc[-1]
    mask = (day == current_day)
    sub = df.loc[mask]
    if sub.empty or sub["volume"].sum() <= 0:
        return None, None, None

    tp = (sub["high"] + sub["low"] + sub["close"]) / 3.0
    v = sub["volume"]
    vwap = float((tp * v).sum() / v.sum())
    var = float(((tp - vwap) ** 2 * v).sum() / v.sum())
    sd = var ** 0.5
    return vwap, sd, float(sub["close"].iloc[0])


def compute(df: pd.DataFrame) -> VWAPFeatures:
    if df is None or df.empty:
        return VWAPFeatures()

    vwap, sd, _ = _session_vwap_bands(df, VWAP_BAND_MULTIPLIER_1, VWAP_BAND_MULTIPLIER_2)
    if vwap is None or sd is None:
        return VWAPFeatures()

    c = float(df["close"].iloc[-1])
    up1 = vwap + VWAP_BAND_MULTIPLIER_1 * sd
    lo1 = vwap - VWAP_BAND_MULTIPLIER_1 * sd
    up2 = vwap + VWAP_BAND_MULTIPLIER_2 * sd
    lo2 = vwap - VWAP_BAND_MULTIPLIER_2 * sd

    dist = abs(vwap - c)
    dist_pct = dist / c * 100 if c else None

    bands = [
        ("vwap", vwap),
        ("upper1", up1),
        ("upper2", up2),
        ("lower1", lo1),
        ("lower2", lo2),
    ]
    nb = ns = None; nbd = nsd = None; nbp = nsp = None
    nbt = nst = ""
    for name, val in bands:
        d = abs(val - c)
        dp = d / c * 100 if c else None
        if val > c:
            if nbd is None or d < nbd:
                nb, nbd, nbp, nbt = val, d, dp, name
        elif val < c:
            if nsd is None or d < nsd:
                ns, nsd, nsp, nst = val, d, dp, name

    return VWAPFeatures(
        vwap=vwap, vwap_distance=dist, vwap_distance_pct=dist_pct,
        price_above_vwap=c > vwap, price_below_vwap=c < vwap,
        vwap_upper1=up1, vwap_lower1=lo1,
        vwap_upper2=up2, vwap_lower2=lo2,
        nearest_buy_vwap=nb, nearest_buy_vwap_distance=nbd,
        nearest_buy_vwap_distance_pct=nbp, nearest_buy_vwap_type=nbt,
        nearest_sell_vwap=ns, nearest_sell_vwap_distance=nsd,
        nearest_sell_vwap_distance_pct=nsp, nearest_sell_vwap_type=nst,
    )

# ---- Registry declaration ----
NAME = "vwap"
INPUTS = ("df",)
OUTPUT_FIELDS = (
    "vwap","vwap_distance","vwap_distance_pct","price_above_vwap","price_below_vwap",
    "vwap_upper1","vwap_lower1","vwap_upper2","vwap_lower2",
    "nearest_buy_vwap","nearest_buy_vwap_distance","nearest_buy_vwap_distance_pct","nearest_buy_vwap_type",
    "nearest_sell_vwap","nearest_sell_vwap_distance","nearest_sell_vwap_distance_pct","nearest_sell_vwap_type",
)
