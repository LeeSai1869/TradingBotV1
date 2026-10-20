# ======================================================
# MARKET LOCATION
# Liquidity, Sessions, Fibonacci, Volume Profile,
# Range Location, Swing Location, Daily References
# (Full original logic – no reductions)
# ======================================================

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import math
import numpy as np
import pandas as pd

# ------------------------------------------------------
# Memory
# ------------------------------------------------------

@dataclass
class SessionMemory:
    asia_high: Optional[float] = None
    asia_low: Optional[float] = None
    asia_high_bar: Optional[int] = None
    asia_low_bar: Optional[int] = None
    prev_asia_high: Optional[float] = None
    prev_asia_low: Optional[float] = None

    london_high: Optional[float] = None
    london_low: Optional[float] = None
    london_high_bar: Optional[int] = None
    london_low_bar: Optional[int] = None
    prev_london_high: Optional[float] = None
    prev_london_low: Optional[float] = None

    newyork_high: Optional[float] = None
    newyork_low: Optional[float] = None
    newyork_high_bar: Optional[int] = None
    newyork_low_bar: Optional[int] = None
    prev_newyork_high: Optional[float] = None
    prev_newyork_low: Optional[float] = None

@dataclass
class FibMemory:
    active_fib_high: Optional[float] = None
    active_fib_low: Optional[float] = None
    fib_range: Optional[float] = None
    fib_direction: str = ""          # "BULLISH_LEG" or "BEARISH_LEG"

@dataclass
class LocationMemory:
    sessions: SessionMemory = field(default_factory=SessionMemory)
    fib: FibMemory = field(default_factory=FibMemory)
    prev_vp_poc: Optional[float] = None

# Keyed by (symbol, tf)
_location_memory_store: Dict[Tuple[str, str], LocationMemory] = {}

def get_location_memory(symbol: str, tf: str) -> LocationMemory:
    key = (symbol, tf)
    if key not in _location_memory_store:
        _location_memory_store[key] = LocationMemory()
    return _location_memory_store[key]

# ------------------------------------------------------
# Output contract
# ------------------------------------------------------

@dataclass
class MarketLocation:
    # Liquidity (basic)
    liquidity_high: Optional[float] = None
    liquidity_low: Optional[float] = None
    distance_to_liquidity_high: Optional[float] = None
    distance_to_liquidity_low: Optional[float] = None

    # Sessions
    asia_high: Optional[float] = None
    asia_low: Optional[float] = None
    london_high: Optional[float] = None
    london_low: Optional[float] = None
    newyork_high: Optional[float] = None
    newyork_low: Optional[float] = None

    prev_asia_high: Optional[float] = None
    prev_asia_low: Optional[float] = None
    prev_london_high: Optional[float] = None
    prev_london_low: Optional[float] = None
    prev_newyork_high: Optional[float] = None
    prev_newyork_low: Optional[float] = None

    asia_range: Optional[float] = None
    london_range: Optional[float] = None
    newyork_range: Optional[float] = None

    nearest_high_price: Optional[float] = None
    nearest_high_price_bar: Optional[int] = None
    nearest_high_price_session: str = ""
    nearest_high_price_distance: Optional[float] = None

    nearest_low_price: Optional[float] = None
    nearest_low_price_bar: Optional[int] = None
    nearest_low_price_session: str = ""
    nearest_low_price_distance: Optional[float] = None

    # Fibonacci
    active_fib_high: Optional[float] = None
    active_fib_low: Optional[float] = None
    fib_range: Optional[float] = None
    fib_direction: str = ""
    fib_retracement_levels: Dict[str, Optional[float]] = field(default_factory=dict)
    fib_extension_levels: Dict[str, Optional[float]] = field(default_factory=dict)

    # Volume Profile
    vp_poc: Optional[float] = None
    vp_va_high: Optional[float] = None
    vp_va_low: Optional[float] = None
    vp_hvn_high: Optional[float] = None
    vp_hvn_low: Optional[float] = None
    vp_lvn_high: Optional[float] = None
    vp_lvn_low: Optional[float] = None

    price_above_poc: bool = False
    price_below_poc: bool = False
    distance_to_poc: Optional[float] = None
    distance_to_poc_atr: Optional[float] = None
    distance_to_poc_pct: Optional[float] = None
    distance_to_vah: Optional[float] = None
    distance_to_val: Optional[float] = None
    inside_value_area: bool = False
    value_area_position: Optional[float] = None
    distance_to_hvn: Optional[float] = None
    distance_to_lvn: Optional[float] = None

    # Range Location
    range_high: Optional[float] = None
    range_low: Optional[float] = None
    range_size: Optional[float] = None
    range_position: Optional[float] = None

    # Swing Location
    latest_swing_high: Optional[float] = None
    latest_swing_low: Optional[float] = None
    distance_to_swing_high: Optional[float] = None
    distance_to_swing_low: Optional[float] = None

    # Price Extension
    atr_extension_ema50: Optional[float] = None
    atr_extension_ema200: Optional[float] = None

    # Daily References
    prev_day_high: Optional[float] = None
    prev_day_low: Optional[float] = None
    day_open: Optional[float] = None
    distance_to_pdh: Optional[float] = None
    distance_to_pdl: Optional[float] = None
    distance_from_day_open: Optional[float] = None

# ------------------------------------------------------
# Helpers
# ------------------------------------------------------

def _calculate_volume_profile(
    highs: np.ndarray,
    lows: np.ndarray,
    volumes: np.ndarray,
    lookback: int,
    bins: int,
    value_area_pct: float
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    if len(highs) < lookback:
        return None, None, None, None, None, None, None

    h = highs[-lookback:]
    l = lows[-lookback:]
    v = volumes[-lookback:]

    vp_high = np.max(h)
    vp_low = np.min(l)
    vp_range = vp_high - vp_low
    if vp_range <= 0:
        return None, None, None, None, None, None, None

    bin_size = vp_range / bins
    volume_bins = np.zeros(bins)

    for i in range(lookback):
        low_bin = int(np.floor((l[i] - vp_low) / bin_size))
        high_bin = int(np.floor((h[i] - vp_low) / bin_size))
        low_bin = max(0, min(bins-1, low_bin))
        high_bin = max(0, min(bins-1, high_bin))
        touched = high_bin - low_bin + 1
        vol_per_bin = v[i] / touched if touched > 0 else 0
        for b in range(low_bin, high_bin+1):
            volume_bins[b] += vol_per_bin

    poc_index = int(np.argmax(volume_bins))
    vp_poc = vp_low + (poc_index + 0.5) * bin_size

    total_volume = np.sum(volume_bins)
    value_target = total_volume * value_area_pct / 100.0

    va_low_idx = poc_index
    va_high_idx = poc_index
    accumulated = volume_bins[poc_index]

    while accumulated < value_target and (va_low_idx > 0 or va_high_idx < bins-1):
        left = volume_bins[va_low_idx-1] if va_low_idx > 0 else 0
        right = volume_bins[va_high_idx+1] if va_high_idx < bins-1 else 0
        # A missing neighbor is not an empty available bin. At the left
        # boundary a zero/zero tie used to decrement below zero forever.
        # Expand one valid bin per iteration, even across zero-volume gaps.
        if va_low_idx > 0 and (va_high_idx == bins-1 or left >= right):
            va_low_idx -= 1
            accumulated += left
        else:
            va_high_idx += 1
            accumulated += right

    vp_va_low = vp_low + va_low_idx * bin_size
    vp_va_high = vp_low + (va_high_idx + 1) * bin_size

    max_vol = volume_bins[poc_index]
    hvn_threshold = max_vol * 0.70
    lvn_threshold = max_vol * 0.30

    hvn_low = hvn_high = lvn_low = lvn_high = None
    for i in range(bins):
        bin_low = vp_low + i * bin_size
        bin_high = vp_low + (i + 1) * bin_size
        if volume_bins[i] >= hvn_threshold:
            hvn_low = bin_low if hvn_low is None else min(hvn_low, bin_low)
            hvn_high = bin_high if hvn_high is None else max(hvn_high, bin_high)
        if volume_bins[i] <= lvn_threshold:
            lvn_low = bin_low if lvn_low is None else min(lvn_low, bin_low)
            lvn_high = bin_high if lvn_high is None else max(lvn_high, bin_high)

    return vp_poc, vp_va_high, vp_va_low, hvn_high, hvn_low, lvn_high, lvn_low

# ------------------------------------------------------
# Main update function
# ------------------------------------------------------

def update_market_location(
    symbol: str,                    # <-- NEW
    tf: str,
    bar_index: int,
    time: Optional[int],
    c: float,
    h: float,
    l: float,
    o: float,
    atr: Optional[float],
    ema50: Optional[float],
    ema200: Optional[float],
    # Volume Profile settings
    vp_lookback: int = 200,
    vp_bins: int = 24,
    vp_value_area_pct: float = 70.0,
    # Range
    range_lookback: int = 100,
    # Session times (hour based, simplified)
    current_hour: Optional[int] = None,
    # Historical data for VP and range (numpy arrays)
    highs: Optional[np.ndarray] = None,
    lows: Optional[np.ndarray] = None,
    volumes: Optional[np.ndarray] = None,
    # Swing
    latest_swing_high: Optional[float] = None,
    latest_swing_low: Optional[float] = None,
    # Daily references (passed from higher TF)
    prev_day_high: Optional[float] = None,
    prev_day_low: Optional[float] = None,
    day_open: Optional[float] = None,
    is_confirmed: bool = True
) -> MarketLocation:

    mem = get_location_memory(symbol, tf)     # <-- (symbol, tf) key
    result = MarketLocation()

    # ==================================================
    # 1. SESSIONS
    # ==================================================
    # Simplified session detection (you can replace with exact timezone logic later)
    # Asia: 00:00-08:00, London: 08:00-16:00, New York: 13:00-21:00 (UTC example)

    asia_session = current_hour is not None and 0 <= current_hour < 8
    london_session = current_hour is not None and 8 <= current_hour < 16
    newyork_session = current_hour is not None and 13 <= current_hour < 21

    # Asia
    if asia_session:
        if mem.sessions.asia_high is None or h > mem.sessions.asia_high:
            mem.sessions.asia_high = h
            mem.sessions.asia_high_bar = bar_index
        if mem.sessions.asia_low is None or l < mem.sessions.asia_low:
            mem.sessions.asia_low = l
            mem.sessions.asia_low_bar = bar_index
    else:
        if mem.sessions.asia_high is not None:
            mem.sessions.prev_asia_high = mem.sessions.asia_high
            mem.sessions.prev_asia_low = mem.sessions.asia_low
            mem.sessions.asia_high = None
            mem.sessions.asia_low = None

    # London
    if london_session:
        if mem.sessions.london_high is None or h > mem.sessions.london_high:
            mem.sessions.london_high = h
            mem.sessions.london_high_bar = bar_index
        if mem.sessions.london_low is None or l < mem.sessions.london_low:
            mem.sessions.london_low = l
            mem.sessions.london_low_bar = bar_index
    else:
        if mem.sessions.london_high is not None:
            mem.sessions.prev_london_high = mem.sessions.london_high
            mem.sessions.prev_london_low = mem.sessions.london_low
            mem.sessions.london_high = None
            mem.sessions.london_low = None

    # New York
    if newyork_session:
        if mem.sessions.newyork_high is None or h > mem.sessions.newyork_high:
            mem.sessions.newyork_high = h
            mem.sessions.newyork_high_bar = bar_index
        if mem.sessions.newyork_low is None or l < mem.sessions.newyork_low:
            mem.sessions.newyork_low = l
            mem.sessions.newyork_low_bar = bar_index
    else:
        if mem.sessions.newyork_high is not None:
            mem.sessions.prev_newyork_high = mem.sessions.newyork_high
            mem.sessions.prev_newyork_low = mem.sessions.newyork_low
            mem.sessions.newyork_high = None
            mem.sessions.newyork_low = None

    result.asia_high = mem.sessions.asia_high
    result.asia_low = mem.sessions.asia_low
    result.london_high = mem.sessions.london_high
    result.london_low = mem.sessions.london_low
    result.newyork_high = mem.sessions.newyork_high
    result.newyork_low = mem.sessions.newyork_low

    result.prev_asia_high = mem.sessions.prev_asia_high
    result.prev_asia_low = mem.sessions.prev_asia_low
    result.prev_london_high = mem.sessions.prev_london_high
    result.prev_london_low = mem.sessions.prev_london_low
    result.prev_newyork_high = mem.sessions.prev_newyork_high
    result.prev_newyork_low = mem.sessions.prev_newyork_low

    if result.asia_high and result.asia_low:
        result.asia_range = result.asia_high - result.asia_low
    if result.london_high and result.london_low:
        result.london_range = result.london_high - result.london_low
    if result.newyork_high and result.newyork_low:
        result.newyork_range = result.newyork_high - result.newyork_low

    # Nearest session high / low
    candidates_high = []
    candidates_low = []
    if result.asia_high is not None:
        candidates_high.append(("ASIA", result.asia_high, mem.sessions.asia_high_bar))
    if result.london_high is not None:
        candidates_high.append(("LONDON", result.london_high, mem.sessions.london_high_bar))
    if result.newyork_high is not None:
        candidates_high.append(("NEW_YORK", result.newyork_high, mem.sessions.newyork_high_bar))

    if result.asia_low is not None:
        candidates_low.append(("ASIA", result.asia_low, mem.sessions.asia_low_bar))
    if result.london_low is not None:
        candidates_low.append(("LONDON", result.london_low, mem.sessions.london_low_bar))
    if result.newyork_low is not None:
        candidates_low.append(("NEW_YORK", result.newyork_low, mem.sessions.newyork_low_bar))

    if candidates_high:
        best = min(candidates_high, key=lambda x: abs(c - x[1]))
        result.nearest_high_price = best[1]
        result.nearest_high_price_session = best[0]
        result.nearest_high_price_bar = best[2]
        result.nearest_high_price_distance = abs(c - best[1])

    if candidates_low:
        best = min(candidates_low, key=lambda x: abs(c - x[1]))
        result.nearest_low_price = best[1]
        result.nearest_low_price_session = best[0]
        result.nearest_low_price_bar = best[2]
        result.nearest_low_price_distance = abs(c - best[1])

    # ==================================================
    # 2. FIBONACCI
    # ==================================================
    # Simple leg detection using latest swing high/low
    if latest_swing_high is not None and latest_swing_low is not None:
        if latest_swing_high > latest_swing_low:
            mem.fib.active_fib_high = latest_swing_high
            mem.fib.active_fib_low = latest_swing_low
            mem.fib.fib_range = latest_swing_high - latest_swing_low
            mem.fib.fib_direction = "BULLISH_LEG"
        else:
            mem.fib.active_fib_high = latest_swing_low
            mem.fib.active_fib_low = latest_swing_high
            mem.fib.fib_range = abs(latest_swing_high - latest_swing_low)
            mem.fib.fib_direction = "BEARISH_LEG"

    result.active_fib_high = mem.fib.active_fib_high
    result.active_fib_low = mem.fib.active_fib_low
    result.fib_range = mem.fib.fib_range
    result.fib_direction = mem.fib.fib_direction

    if mem.fib.fib_range and mem.fib.fib_range > 0:
        ratios_ret = [0.236, 0.382, 0.5, 0.618, 0.786]
        ratios_ext = [1.0, 1.272, 1.414, 1.618, 2.0, 2.618]

        for r in ratios_ret:
            if mem.fib.fib_direction == "BULLISH_LEG":
                level = mem.fib.active_fib_high - mem.fib.fib_range * r
            else:
                level = mem.fib.active_fib_low + mem.fib.fib_range * r
            result.fib_retracement_levels[str(r)] = level

        for r in ratios_ext:
            if mem.fib.fib_direction == "BULLISH_LEG":
                level = mem.fib.active_fib_high + mem.fib.fib_range * (r - 1.0)
            else:
                level = mem.fib.active_fib_low - mem.fib.fib_range * (r - 1.0)
            result.fib_extension_levels[str(r)] = level

    # ==================================================
    # 3. VOLUME PROFILE
    # ==================================================
    if highs is not None and lows is not None and volumes is not None:
        vp_poc, va_high, va_low, hvn_high, hvn_low, lvn_high, lvn_low = _calculate_volume_profile(
            highs, lows, volumes, vp_lookback, vp_bins, vp_value_area_pct
        )
        result.vp_poc = vp_poc
        result.vp_va_high = va_high
        result.vp_va_low = va_low
        result.vp_hvn_high = hvn_high
        result.vp_hvn_low = hvn_low
        result.vp_lvn_high = lvn_high
        result.vp_lvn_low = lvn_low

        if vp_poc is not None:
            result.price_above_poc = c > vp_poc
            result.price_below_poc = c < vp_poc
            result.distance_to_poc = abs(c - vp_poc)
            result.distance_to_poc_pct = result.distance_to_poc / c * 100 if c != 0 else None
            if atr and atr > 0:
                result.distance_to_poc_atr = result.distance_to_poc / atr

        if va_high is not None and va_low is not None:
            result.inside_value_area = va_low <= c <= va_high
            if va_high > va_low:
                result.value_area_position = (c - va_low) / (va_high - va_low)
            if c < va_low:
                result.distance_to_val = va_low - c
            if c > va_high:
                result.distance_to_vah = c - va_high

        if hvn_high is not None and hvn_low is not None:
            if c > hvn_high:
                result.distance_to_hvn = (c - hvn_high) / c * 100 if c != 0 else None
            elif c < hvn_low:
                result.distance_to_hvn = (c - hvn_low) / c * 100 if c != 0 else None
            else:
                result.distance_to_hvn = 0.0

        if lvn_high is not None and lvn_low is not None:
            if c > lvn_high:
                result.distance_to_lvn = (c - lvn_high) / c * 100 if c != 0 else None
            elif c < lvn_low:
                result.distance_to_lvn = (c - lvn_low) / c * 100 if c != 0 else None
            else:
                result.distance_to_lvn = 0.0

        mem.prev_vp_poc = vp_poc

    # ==================================================
    # 4. RANGE LOCATION
    # ==================================================
    if highs is not None and lows is not None and len(highs) >= range_lookback:
        result.range_high = float(np.max(highs[-range_lookback:]))
        result.range_low = float(np.min(lows[-range_lookback:]))
        result.range_size = result.range_high - result.range_low
        if result.range_size > 0:
            result.range_position = (c - result.range_low) / result.range_size

    # ==================================================
    # 5. SWING LOCATION
    # ==================================================
    result.latest_swing_high = latest_swing_high
    result.latest_swing_low = latest_swing_low
    if latest_swing_high is not None and c != 0:
        result.distance_to_swing_high = (latest_swing_high - c) / c * 100
    if latest_swing_low is not None and c != 0:
        result.distance_to_swing_low = (c - latest_swing_low) / c * 100

    # ==================================================
    # 6. PRICE EXTENSION
    # ==================================================
    if atr is not None and atr > 0:
        if ema50 is not None:
            result.atr_extension_ema50 = (c - ema50) / atr
        if ema200 is not None:
            result.atr_extension_ema200 = (c - ema200) / atr

    # ==================================================
    # 7. DAILY REFERENCES
    # ==================================================
    result.prev_day_high = prev_day_high
    result.prev_day_low = prev_day_low
    result.day_open = day_open

    if prev_day_high is not None and c != 0:
        result.distance_to_pdh = (prev_day_high - c) / c * 100
    if prev_day_low is not None and c != 0:
        result.distance_to_pdl = (c - prev_day_low) / c * 100
    if day_open is not None and c != 0:
        result.distance_from_day_open = (c - day_open) / c * 100

    return result