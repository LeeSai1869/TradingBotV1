"""Volume profile calculation isolated from session and location memory."""
from typing import Optional, Tuple
import numpy as np

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

