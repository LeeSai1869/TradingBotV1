# ======================================================
# FEATURE — DMI / ADX
# ======================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd
from .pine_math import rma, true_range


ADX_LEN = 10


@dataclass
class DMIFeatures:
    adx: Optional[float] = None
    prev_adx: Optional[float] = None
    di_plus: Optional[float] = None
    prev_di_plus: Optional[float] = None
    di_minus: Optional[float] = None
    prev_di_minus: Optional[float] = None
    di_direction: Optional[float] = None
    di_spread: Optional[float] = None
    di_dominance: Optional[float] = None
    bull_momentum_weakening: bool = False
    bear_momentum_weakening: bool = False


def _atr(high, low, close, length):
    return rma(true_range(high, low, close, first_bar=False), length)


def _dmi(high, low, close, length):
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index).where(up.notna())
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index).where(down.notna())
    atr = _atr(high, low, close, length)
    plus_di = (100 * rma(plus_dm, length) / atr).ffill()
    minus_di = (100 * rma(minus_dm, length) / atr).ffill()
    total = plus_di + minus_di
    dx = (plus_di - minus_di).abs() / total.where(total != 0, 1) * 100
    adx = rma(dx, length)
    return plus_di, minus_di, adx


def _f(v):
    if v is None: return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def compute(df: pd.DataFrame) -> DMIFeatures:
    if df is None or df.empty:
        return DMIFeatures()
    dp, dm, adx = _dmi(df["high"], df["low"], df["close"], ADX_LEN)
    dpv, dmv, av = _f(dp.iloc[-1]), _f(dm.iloc[-1]), _f(adx.iloc[-1])
    pdpv = _f(dp.iloc[-2]) if len(dp) > 1 else None
    pdmv = _f(dm.iloc[-2]) if len(dm) > 1 else None
    pav = _f(adx.iloc[-2]) if len(adx) > 1 else None

    direction = spread = dominance = None
    if dpv is not None and dmv is not None:
        direction = dpv - dmv
        spread = abs(direction)
        denom = dpv + dmv
        dominance = abs(dpv - dmv) / denom if denom > 0 else 0.0

    bull_weak = (dpv is not None and pdpv is not None and av is not None and pav is not None
                 and dpv < pdpv and av < pav)
    bear_weak = (dmv is not None and pdmv is not None and av is not None and pav is not None
                 and dmv < pdmv and av < pav)

    return DMIFeatures(
        adx=av, prev_adx=pav,
        di_plus=dpv, prev_di_plus=pdpv,
        di_minus=dmv, prev_di_minus=pdmv,
        di_direction=direction, di_spread=spread, di_dominance=dominance,
        bull_momentum_weakening=bull_weak,
        bear_momentum_weakening=bear_weak,
    )

# ---- Registry declaration ----
NAME = "di_adx"
INPUTS = ("df",)
OUTPUT_FIELDS = (
    "adx","prev_adx","di_plus","prev_di_plus","di_minus","prev_di_minus",
    "di_direction","di_spread","di_dominance",
    "bull_momentum_weakening","bear_momentum_weakening",
)
