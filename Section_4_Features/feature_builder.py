# ============================================================
# feature_builder.py
# Assembles Section 4 feature modules into one FeaturePacket
# ============================================================

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from Section_4_Features.feature_packet import (
    FeaturePacket,
    create_feature_packet,
)
from Section_4_Features.features import registry as _feature_registry
from Section_4_Features.features.support_resistance import update_market_levels
from Section_4_Features.features.market_liquidity import update_market_liquidity
from Section_4_Features.features.bos_structure import (
    update_market_structure,
    update_swing_pivots,
    update_flip_candidate,
)
from Section_4_Features.features.market_imbalance import update_market_imbalance
from Section_4_Features.features.market_location import update_market_location


def _dataclass_to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "__dict__"):
        return {
            k: v
            for k, v in vars(obj).items()
            if not k.startswith("_")
        }
    return {}


def build_feature_packet(
    *,
    tf: str,
    symbol: str,               # <-- NEW
    df: pd.DataFrame,
    bar_index: Optional[int] = None,
    is_confirmed: bool = True,
    pivot_high: Optional[float] = None,
    pivot_low: Optional[float] = None,
) -> FeaturePacket:
    """
    Build a FeaturePacket for the *last* row of df.

    df columns required: open, high, low, close
    optional: volume, time (ms)

    Bars must be fed in chronological order so per-tf memory
    (S/R, FVG, OB, structure, swing pivots, flip candidate) stays correct.
    """
    if df is None or df.empty:
        return create_feature_packet(tf=tf, features={}, valid=False)

    if bar_index is None:
        bar_index = len(df) - 1

    # --------------------------------------------------
    # 1. Market context (atr, emas, current ohlc, ...)
    # --------------------------------------------------
    # Section 4 — pure feature modules, driven by the registry.
    # Each module declares INPUTS so we know how to call it.
    # 'atr' is computed first because some features need it as an arg.
    ctx_dict = {}
    _atr_value = None
    for decl in _feature_registry.load():
        kwargs = {}
        for arg in decl["inputs"]:
            if arg == "df":
                kwargs["df"] = df
            elif arg == "atr":
                if _atr_value is None:
                    from Section_4_Features.features.atr import compute as _atr_compute
                    _atr_value = _atr_compute(df).atr
                kwargs["atr"] = _atr_value
        result = decl["module"].compute(**kwargs)
        ctx_dict.update(vars(result))

    c = float(df["close"].iloc[-1])
    o = float(df["open"].iloc[-1])
    h = float(df["high"].iloc[-1])
    l = float(df["low"].iloc[-1])

    c1 = float(df["close"].iloc[-2]) if len(df) > 1 else None
    o1 = float(df["open"].iloc[-2]) if len(df) > 1 else None
    h1 = float(df["high"].iloc[-2]) if len(df) > 1 else None
    l1 = float(df["low"].iloc[-2]) if len(df) > 1 else None

    atr = ctx_dict.get("atr")
    ema50 = ctx_dict.get("ema50")
    ema200 = ctx_dict.get("ema200")

    time_val = None
    if "time" in df.columns:
        time_val = int(df["time"].iloc[-1])
    elif "bar_time" in df.columns:
        time_val = int(df["bar_time"].iloc[-1])

    current_hour = None
    if time_val is not None:
        # ms → UTC hour
        current_hour = int((time_val // 1000) % 86400 // 3600)

    # --------------------------------------------------
    # 2. Swing pivots (slow lifecycle — 25% confirmation)
    # --------------------------------------------------
    swing_pivot_out = update_swing_pivots(
        symbol=symbol,
        tf=tf,
        bar_index=bar_index,
        time=time_val,
        o=o,
        h=h,
        l=l,
        c=c,
        prev_h=h1,
        prev_l=l1,
        is_confirmed=is_confirmed,
    )

    swing_dict = {
        "swing_candidate_pivot":       swing_pivot_out.candidate_pivot,
        "swing_candidate_high_price":  swing_pivot_out.candidate_pivot_high_price,
        "swing_candidate_low_price":   swing_pivot_out.candidate_pivot_low_price,
        "swing_pivot_high_confirmed":  swing_pivot_out.pivot_high_confirmed_this_bar,
        "swing_pivot_low_confirmed":   swing_pivot_out.pivot_low_confirmed_this_bar,
        "swing_direction":             swing_pivot_out.current_swing_direction,
        "swing_transition":            swing_pivot_out.swing_transition,
        "swing_latest_confirmed_high": swing_pivot_out.latest_confirmed_pivot_high,
        "swing_latest_confirmed_low":  swing_pivot_out.latest_confirmed_pivot_low,
        "swing_nearest_high":          swing_pivot_out.nearest_swing_high,
        "swing_nearest_low":           swing_pivot_out.nearest_swing_low,
        "swing_distance_to_high_pct":  swing_pivot_out.distance_to_swing_high_pct,
        "swing_distance_to_low_pct":   swing_pivot_out.distance_to_swing_low_pct,
        "swing_pivot_high_confirmation_price": swing_pivot_out.pivot_high_confirmation_price,
        "swing_pivot_low_confirmation_price":  swing_pivot_out.pivot_low_confirmation_price,
    }

    # --------------------------------------------------
    # 3. Flip candidate (fast lifecycle — first opposite close)
    # --------------------------------------------------
    flip_out = update_flip_candidate(
        symbol=symbol,
        tf=tf,
        bar_index=bar_index,
        h=h,
        l=l,
        c=c,
        prev_h=h1,
        prev_l=l1,
        is_confirmed=is_confirmed,
    )

    # FeaturePacket key names are kept as `swing_pivot_high_flip` /
    # `swing_pivot_low_flip` for backward compatibility with Section 6.1.
    # The values come from the flip candidate engine (fast lifecycle),
    # not the swing engine.
    flip_dict = {
        "swing_pivot_high_flip": flip_out.flip_high_this_bar,
        "swing_pivot_low_flip":  flip_out.flip_low_this_bar,

        # Additional context for diagnostics and future use
        "flip_direction":              flip_out.flip_direction,
        "flip_high_candidate_price":   flip_out.flip_high_candidate_price,
        "flip_high_candidate_bar":     flip_out.flip_high_candidate_bar,
        "flip_low_candidate_price":    flip_out.flip_low_candidate_price,
        "flip_low_candidate_bar":      flip_out.flip_low_candidate_bar,
    }

    # --------------------------------------------------
    # 4. Structure (BOS / CHOCH)
    # --------------------------------------------------
    structure = update_market_structure(
        symbol=symbol,
        tf=tf,
        bar_index=bar_index,
        time=time_val,
        c=c,
        h=h,
        l=l,
        atr=atr,
        pivot_high=pivot_high,
        pivot_low=pivot_low,
        is_confirmed=is_confirmed,
    )
    structure_dict = _dataclass_to_dict(structure)

    # --------------------------------------------------
    # 5. Support / Resistance
    # --------------------------------------------------
    levels = update_market_levels(
        symbol=symbol,
        tf=tf,
        bar_index=bar_index,
        time=time_val,
        c=c,
        h=h,
        l=l,
        h1=h1,
        l1=l1,
        atr=atr,
        pivot_high=pivot_high,
        pivot_low=pivot_low,
        is_confirmed=is_confirmed,
    )
    levels_dict = _dataclass_to_dict(levels)

    # --------------------------------------------------
    # 6. Imbalance (FVG / OB)
    # --------------------------------------------------
    imbalance = update_market_imbalance(
        symbol=symbol,
        tf=tf,
        bar_index=bar_index,
        c=c,
        h=h,
        l=l,
        o=o,
        c1=c1,
        h1=h1,
        l1=l1,
        o1=o1,
        atr=atr,
        is_confirmed=is_confirmed,
    )
    imbalance_dict = _dataclass_to_dict(imbalance)

    # --------------------------------------------------
    # 7. Location (sessions, VP, range, ...)
    # --------------------------------------------------
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    volumes = (
        df["volume"].to_numpy(dtype=float)
        if "volume" in df.columns
        else None
    )

    location = update_market_location(
        symbol=symbol,
        tf=tf,
        bar_index=bar_index,
        time=time_val,
        c=c,
        h=h,
        l=l,
        o=o,
        atr=atr,
        ema50=ema50,
        ema200=ema200,
        current_hour=current_hour,
        highs=highs,
        lows=lows,
        volumes=volumes,
        is_confirmed=is_confirmed,
    )
    location_dict = _dataclass_to_dict(location)

    # --------------------------------------------------
    # 8. Market Liquidity
    # --------------------------------------------------
    volume = (
        float(df["volume"].iloc[-1])
        if "volume" in df.columns
        else None
    )

    liquidity_volume_ma = ctx_dict.get("volume_ma")
    liquidity_volume_ratio = ctx_dict.get("volume_ratio")
    liquidity_candle_range = ctx_dict.get("candle_range")
    liquidity_upper_wick = ctx_dict.get("upper_wick")
    liquidity_lower_wick = ctx_dict.get("lower_wick")
    liquidity_wick_ratio = ctx_dict.get("wick_ratio")

    support_high = levels_dict.get("nearest_support_high")
    resistance_low = levels_dict.get("nearest_resistance_low")

    liquidity = update_market_liquidity(
        tf=tf,
        bar_index=bar_index,
        time=time_val,
        c=c,
        h=h,
        l=l,
        o=o,
        h1=h1,
        l1=l1,
        atr=atr,
        highs=highs,
        lows=lows,
        volumes=volumes,
        volume=volume,
        volume_ma=liquidity_volume_ma,
        volume_ratio=liquidity_volume_ratio,
        candle_range=liquidity_candle_range,
        upper_wick=liquidity_upper_wick,
        lower_wick=liquidity_lower_wick,
        wick_ratio=liquidity_wick_ratio,
        support_high=support_high,
        resistance_low=resistance_low,
        is_confirmed=is_confirmed,
    )
    liquidity_dict = _dataclass_to_dict(liquidity)

    # --------------------------------------------------
    # 9. Merge into one features dict
    # --------------------------------------------------
    features: Dict[str, Any] = {}
    features.update(ctx_dict)
    features.update(swing_dict)
    features.update(flip_dict)
    features.update(structure_dict)
    features.update(levels_dict)
    features.update(imbalance_dict)
    features.update(location_dict)
    features.update(liquidity_dict)

    # Always keep core OHLC on the packet features
    features["c"] = c
    features["o"] = o
    features["h"] = h
    features["l"] = l
    features["c1"] = c1
    features["o1"] = o1
    features["h1"] = h1
    features["l1"] = l1
    features["bar_index"] = bar_index
    features["bar_time"] = time_val

    return create_feature_packet(tf=tf, features=features, valid=True)