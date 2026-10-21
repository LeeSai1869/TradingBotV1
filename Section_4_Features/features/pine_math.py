"""Pine-compatible Wilder smoothing, seeded with an SMA of valid samples."""
import math
import pandas as pd


def rma(source: pd.Series, length: int) -> pd.Series:
    if length < 1:
        raise ValueError('RMA length must be positive')
    seed = []
    previous = None
    output = []
    for value in source:
        if not pd.isna(value):
            if previous is None:
                seed.append(float(value))
                if len(seed) == length:
                    previous = math.fsum(seed) / length
            else:
                previous = (float(value) + (length - 1) * previous) / length
        output.append(float('nan') if previous is None else previous)
    return pd.Series(output, index=source.index, dtype=float)


def true_range(high, low, close, *, first_bar=True):
    previous = close.shift(1)
    result = pd.concat([high-low, (high-previous).abs(), (low-previous).abs()], axis=1).max(axis=1)
    if not first_bar:
        result = result.where(previous.notna())
    return result
