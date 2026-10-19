# ======================================================
# FEATURE — CANDLE METRICS
# ======================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd


@dataclass
class CandleFeatures:
    candle_range: Optional[float] = None
    body: Optional[float] = None
    prev_body: Optional[float] = None
    body_percent: Optional[float] = None
    prev_body_percent: Optional[float] = None
    upper_wick: Optional[float] = None
    lower_wick: Optional[float] = None
    wick_ratio: Optional[float] = None
    close_location: Optional[float] = None
    prev_close_location: Optional[float] = None
    candle_direction: Optional[int] = None
    prev_candle_direction: Optional[int] = None
    displacement_atr: Optional[float] = None
    prev_displacement_atr: Optional[float] = None
    candle_range_atr: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None


def compute(df: pd.DataFrame, atr: Optional[float] = None) -> CandleFeatures:
    if df is None or df.empty:
        return CandleFeatures()
    o = float(df["open"].iloc[-1]); h = float(df["high"].iloc[-1])
    l = float(df["low"].iloc[-1]);  c = float(df["close"].iloc[-1])
    has_prev = len(df) > 1

    rng = h - l
    body = abs(c - o)
    bp = body / rng if rng > 0 else 0.0
    upw = h - max(c, o)
    low = min(c, o) - l
    cl = (c - l) / rng if rng > 0 else 0.0
    direction = 1 if c > o else (-1 if c < o else 0)

    wr = None
    if rng > 0:
        wr = max(upw, low) / rng

    disp = body / atr if atr and atr > 0 else None
    rng_atr = rng / atr if atr and atr > 0 else None

    if has_prev:
        o1 = float(df["open"].iloc[-2]); c1 = float(df["close"].iloc[-2])
        h1 = float(df["high"].iloc[-2]); l1 = float(df["low"].iloc[-2])
        pb = abs(c1 - o1)
        prng = h1 - l1
        pbp = pb / prng if prng > 0 else 0.0
        pcl = (c1 - l1) / prng if prng > 0 else 0.0
        pdirection = 1 if c1 > o1 else (-1 if c1 < o1 else 0)
        change = c - c1
        chg_pct = change / c1 * 100 if c1 else None
    else:
        pb = pbp = pcl = pdirection = change = chg_pct = None

    return CandleFeatures(
        candle_range=rng, body=body, prev_body=pb,
        body_percent=bp, prev_body_percent=pbp,
        upper_wick=upw, lower_wick=low, wick_ratio=wr,
        close_location=cl, prev_close_location=pcl,
        candle_direction=direction, prev_candle_direction=pdirection,
        displacement_atr=disp, candle_range_atr=rng_atr,
        change=change, change_percent=chg_pct,
    )

# ---- Registry declaration ----
NAME = "candle"
INPUTS = ("df", "atr")
OUTPUT_FIELDS = (
    "candle_range","body","prev_body","body_percent","prev_body_percent",
    "upper_wick","lower_wick","wick_ratio","close_location","prev_close_location",
    "candle_direction","prev_candle_direction",
    "displacement_atr","prev_displacement_atr","candle_range_atr",
    "change","change_percent",
)
