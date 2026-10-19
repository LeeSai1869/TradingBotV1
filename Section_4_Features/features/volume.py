# ======================================================
# FEATURE — VOLUME
# ======================================================

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd

from Section_2_Inputs.Inputs import VOLUME_LOOKBACK


@dataclass
class VolumeFeatures:
    volume: float = 0.0
    prev_volume: Optional[float] = None
    volume_ma: Optional[float] = None
    volume_ratio: float = 0.0
    prev_volume_ratio: Optional[float] = None


def compute(df: pd.DataFrame) -> VolumeFeatures:
    if df is None or df.empty:
        return VolumeFeatures()
    if "volume" not in df.columns:
        return VolumeFeatures()
    vol = df["volume"]
    v = float(vol.iloc[-1])
    pv = float(vol.iloc[-2]) if len(vol) > 1 else None
    ma = float(vol.rolling(VOLUME_LOOKBACK).mean().iloc[-1])
    ratio = v / ma if ma and ma > 0 else 0.0
    if len(vol) > 1:
        pma = float(vol.rolling(VOLUME_LOOKBACK).mean().iloc[-2])
        pratio = (pv / pma) if (pv is not None and pma > 0) else None
    else:
        pratio = None
    return VolumeFeatures(
        volume=v, prev_volume=pv, volume_ma=ma,
        volume_ratio=ratio, prev_volume_ratio=pratio,
    )

# ---- Registry declaration ----
NAME = "volume"
INPUTS = ("df",)
OUTPUT_FIELDS = ("volume","prev_volume","volume_ma","volume_ratio","prev_volume_ratio")
