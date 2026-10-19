# ======================================================
# MARKET CONTEXT
# Price, EMA, VWAP, Momentum, Volatility, Volume, Candle
# ======================================================

from dataclasses import dataclass
from typing import Optional, List
import math
import numpy as np
import pandas as pd

from Section_2_Inputs.Inputs import (
    EMA_7_LEN, EMA_25_LEN, EMA_50_LEN, EMA_100_LEN, EMA_200_LEN, EMA_300_LEN,
    VWAP_BAND_MULTIPLIER_1, VWAP_BAND_MULTIPLIER_2,
    VOLUME_LOOKBACK
)

@dataclass
class MarketContext:
    # Price
    c: float = 0.0
    c1: Optional[float] = None
    h: float = 0.0
    h1: Optional[float] = None
    l: float = 0.0
    l1: Optional[float] = None
    o: float = 0.0
    o1: Optional[float] = None
    current_price: float = 0.0

    # EMAs
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

    wma50: Optional[float] = None
    wma50_distance: Optional[float] = None
    wma50_distance_pct: Optional[float] = None

    # VWAP
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

    # Momentum
    rsi: Optional[float] = None
    prev_rsi: Optional[float] = None
    rsi_change: Optional[float] = None

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
    bull_momentum_divergence: bool = False
    bear_momentum_divergence: bool = False

    # Volatility
    atr: Optional[float] = None
    atr_ma: Optional[float] = None
    atr_ma_ratio: Optional[float] = None
    atr_change: Optional[float] = None
    atr_percent: Optional[float] = None

    # Volume
    volume: float = 0.0
    prev_volume: Optional[float] = None
    volume_ma: Optional[float] = None
    volume_ratio: float = 0.0
    prev_volume_ratio: Optional[float] = None

    # Candle
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
    candle_direction: Optional[float] = None
    prev_candle_direction: Optional[float] = None
    displacement_atr: Optional[float] = None
    prev_displacement_atr: Optional[float] = None
    candle_range_atr: Optional[float] = None

    change: Optional[float] = None
    change_percent: Optional[float] = None

def calculate_ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def calculate_wma(series: pd.Series, length: int) -> pd.Series:
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def calculate_rsi(series: pd.Series, length: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, min_periods=length, adjust=False).mean()

def calculate_dmi(high: pd.Series, low: pd.Series, close: pd.Series, length: int):
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr = calculate_atr(high, low, close, length)  # already smoothed
    # We need raw TR for proper DMI, simplified version:
    atr = calculate_atr(high, low, close, length)

    plus_di = 100 * pd.Series(plus_dm, index=high.index).ewm(alpha=1/length, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=high.index).ewm(alpha=1/length, adjust=False).mean() / atr
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di) * 100
    adx = dx.ewm(alpha=1/length, adjust=False).mean()
    return plus_di, minus_di, adx

def build_market_context(
    df: pd.DataFrame,
    rsi_len: int = 7,
    adx_len: int = 10,
    atr_len: int = 10,
    atr_ma_len: int = 14
) -> MarketContext:
    """
    Build MarketContext from a pandas DataFrame.
    Expected columns: open, high, low, close, volume
    The DataFrame should already be on the correct timeframe.
    """
    if df.empty:
        return MarketContext()

    c = df["close"].iloc[-1]
    o = df["open"].iloc[-1]
    h = df["high"].iloc[-1]
    l = df["low"].iloc[-1]

    c1 = df["close"].iloc[-2] if len(df) > 1 else None
    o1 = df["open"].iloc[-2] if len(df) > 1 else None
    h1 = df["high"].iloc[-2] if len(df) > 1 else None
    l1 = df["low"].iloc[-2] if len(df) > 1 else None

    # EMAs
    ema7 = calculate_ema(df["close"], EMA_7_LEN).iloc[-1]
    ema25 = calculate_ema(df["close"], EMA_25_LEN).iloc[-1]
    ema50 = calculate_ema(df["close"], EMA_50_LEN).iloc[-1]
    ema100 = calculate_ema(df["close"], EMA_100_LEN).iloc[-1]
    ema200 = calculate_ema(df["close"], EMA_200_LEN).iloc[-1]
    ema300 = calculate_ema(df["close"], EMA_300_LEN).iloc[-1]

    prev_ema7 = calculate_ema(df["close"], EMA_7_LEN).iloc[-2] if len(df) > 1 else None
    prev_ema25 = calculate_ema(df["close"], EMA_25_LEN).iloc[-2] if len(df) > 1 else None
    prev_ema50 = calculate_ema(df["close"], EMA_50_LEN).iloc[-2] if len(df) > 1 else None
    prev_ema100 = calculate_ema(df["close"], EMA_100_LEN).iloc[-2] if len(df) > 1 else None
    prev_ema200 = calculate_ema(df["close"], EMA_200_LEN).iloc[-2] if len(df) > 1 else None
    prev_ema300 = calculate_ema(df["close"], EMA_300_LEN).iloc[-2] if len(df) > 1 else None

    ema_gap_7_25 = abs(ema7 - ema25) if ema7 is not None and ema25 is not None else None
    ema_gap_25_50 = abs(ema25 - ema50) if ema25 is not None and ema50 is not None else None
    ema_gap_50_100 = abs(ema50 - ema100) if ema50 is not None and ema100 is not None else None

    ema_gap_7_25_pct = ema_gap_7_25 / c if ema_gap_7_25 is not None and c != 0 else None
    ema_gap_25_50_pct = ema_gap_25_50 / c if ema_gap_25_50 is not None and c != 0 else None
    ema_gap_50_100_pct = ema_gap_50_100 / c if ema_gap_50_100 is not None and c != 0 else None

    ema_compression = None
    if all(x is not None for x in [ema_gap_7_25_pct, ema_gap_25_50_pct, ema_gap_50_100_pct]):
        ema_compression = (ema_gap_7_25_pct + ema_gap_25_50_pct + ema_gap_50_100_pct) / 3

    ema_bull_structure = ema7 > ema25 > ema50 > ema100 if all(x is not None for x in [ema7, ema25, ema50, ema100]) else False
    ema_bear_structure = ema7 < ema25 < ema50 < ema100 if all(x is not None for x in [ema7, ema25, ema50, ema100]) else False

    # Nearest EMAs
    ema_values = [ema7, ema25, ema50, ema100, ema200, ema300]
    nearest_buy_ema = nearest_buy_dist = nearest_buy_pct = None
    nearest_sell_ema = nearest_sell_dist = nearest_sell_pct = None

    for ema_val in ema_values:
        if ema_val is None:
            continue
        dist = abs(ema_val - c)
        dist_pct = dist / c * 100 if c != 0 else None
        if ema_val > c:
            if nearest_buy_dist is None or dist < nearest_buy_dist:
                nearest_buy_ema = ema_val
                nearest_buy_dist = dist
                nearest_buy_pct = dist_pct
        elif ema_val < c:
            if nearest_sell_dist is None or dist < nearest_sell_dist:
                nearest_sell_ema = ema_val
                nearest_sell_dist = dist
                nearest_sell_pct = dist_pct

    # WMA 50
    wma50 = calculate_wma(df["close"], 50).iloc[-1]
    wma50_distance = abs(wma50 - c) if wma50 is not None else None
    wma50_distance_pct = wma50_distance / c * 100 if wma50_distance is not None and c != 0 else None

    # ATR
    atr_series = calculate_atr(df["high"], df["low"], df["close"], atr_len)
    atr = atr_series.iloc[-1]
    atr_ma = atr_series.rolling(atr_ma_len).mean().iloc[-1]
    atr_ma_ratio = atr / atr_ma if atr_ma and atr_ma > 0 else None
    atr_change = atr - atr_series.iloc[-2] if len(atr_series) > 1 else None
    atr_percent = atr / c if c != 0 else None

    # RSI
    rsi_series = calculate_rsi(df["close"], rsi_len)
    rsi = rsi_series.iloc[-1]
    prev_rsi = rsi_series.iloc[-2] if len(rsi_series) > 1 else None
    rsi_change = rsi - prev_rsi if prev_rsi is not None else None

    # DMI / ADX
    di_plus, di_minus, adx = calculate_dmi(df["high"], df["low"], df["close"], adx_len)
    di_plus_val = di_plus.iloc[-1]
    di_minus_val = di_minus.iloc[-1]
    adx_val = adx.iloc[-1]
    prev_di_plus = di_plus.iloc[-2] if len(di_plus) > 1 else None
    prev_di_minus = di_minus.iloc[-2] if len(di_minus) > 1 else None
    prev_adx = adx.iloc[-2] if len(adx) > 1 else None

    di_direction = di_plus_val - di_minus_val if di_plus_val is not None and di_minus_val is not None else None
    di_spread = abs(di_direction) if di_direction is not None else None
    di_dominance = abs(di_plus_val - di_minus_val) / (di_plus_val + di_minus_val) if (di_plus_val is not None and di_minus_val is not None and (di_plus_val + di_minus_val) > 0) else 0.0

    bull_momentum_weakening = (di_plus_val < prev_di_plus and adx_val < prev_adx) if all(x is not None for x in [di_plus_val, prev_di_plus, adx_val, prev_adx]) else False
    bear_momentum_weakening = (di_minus_val < prev_di_minus and adx_val < prev_adx) if all(x is not None for x in [di_minus_val, prev_di_minus, adx_val, prev_adx]) else False

    # Volume
    volume = df["volume"].iloc[-1]
    prev_volume = df["volume"].iloc[-2] if len(df) > 1 else None
    volume_ma = df["volume"].rolling(VOLUME_LOOKBACK).mean().iloc[-1]
    volume_ratio = volume / volume_ma if volume_ma and volume_ma > 0 else 0.0
    prev_volume_ma = df["volume"].rolling(VOLUME_LOOKBACK).mean().iloc[-2] if len(df) > 1 else None
    prev_volume_ratio = (prev_volume / prev_volume_ma
        if (prev_volume is not None
            and prev_volume_ma is not None
            and prev_volume_ma > 0) else None)

    # Candle basics
    candle_range = h - l
    body = abs(c - o)
    body_percent = body / candle_range if candle_range > 0 else 0.0
    prev_body = abs(c1 - o1) if (c1 is not None and o1 is not None) else None
    prev_candle_range = (h1 - l1) if (h1 is not None and l1 is not None) else None
    prev_body_percent = (prev_body / prev_candle_range
        if (prev_body is not None and prev_candle_range is not None and prev_candle_range > 0) else 0.0)
    upper_wick = h - max(c, o)
    lower_wick = min(c, o) - l
    close_location = (c - l) / candle_range if candle_range > 0 else 0.0
    candle_direction = 1 if c > o else (-1 if c < o else 0)
    displacement_atr = body / atr if atr and atr > 0 else None
    candle_range_atr = candle_range / atr if atr and atr > 0 else None

    change = c - c1 if c1 is not None else None
    change_percent = change / c1 * 100 if change is not None and c1 not in (None, 0) else None

    ctx = MarketContext(
        c=c, c1=c1, h=h, h1=h1, l=l, l1=l1, o=o, o1=o1, current_price=c,
        ema7=ema7, ema25=ema25, ema50=ema50, ema100=ema100, ema200=ema200, ema300=ema300,
        prev_ema7=prev_ema7, prev_ema25=prev_ema25, prev_ema50=prev_ema50,
        prev_ema100=prev_ema100, prev_ema200=prev_ema200, prev_ema300=prev_ema300,
        ema_gap_7_25=ema_gap_7_25, ema_gap_25_50=ema_gap_25_50, ema_gap_50_100=ema_gap_50_100,
        ema_gap_7_25_pct=ema_gap_7_25_pct, ema_gap_25_50_pct=ema_gap_25_50_pct, ema_gap_50_100_pct=ema_gap_50_100_pct,
        ema_compression=ema_compression,
        ema_bull_structure=ema_bull_structure, ema_bear_structure=ema_bear_structure,
        price_above_ema50=c > ema50 if ema50 is not None else False,
        price_below_ema50=c < ema50 if ema50 is not None else False,
        price_above_ema200=c > ema200 if ema200 is not None else False,
        price_below_ema200=c < ema200 if ema200 is not None else False,
        price_above_ema300=c > ema300 if ema300 is not None else False,
        price_below_ema300=c < ema300 if ema300 is not None else False,
        ema50_distance_pct=abs(c - ema50) / c * 100 if ema50 is not None and c != 0 else None,
        ema200_distance_pct=abs(c - ema200) / c * 100 if ema200 is not None and c != 0 else None,
        ema300_distance_pct=abs(c - ema300) / c * 100 if ema300 is not None and c != 0 else None,
        ema50_slope_pct=((ema50 - prev_ema50) / prev_ema50 * 100) if prev_ema50 not in (None, 0) else 0.0,
        ema200_slope_pct=((ema200 - prev_ema200) / prev_ema200 * 100) if prev_ema200 not in (None, 0) else 0.0,
        ema300_slope_pct=((ema300 - prev_ema300) / prev_ema300 * 100) if prev_ema300 not in (None, 0) else 0.0,
        ema50_200_gap_pct=abs(ema50 - ema200) / ema200 * 100 if ema200 not in (None, 0) else 0.0,
        nearest_buy_ema=nearest_buy_ema, nearest_buy_ema_distance=nearest_buy_dist, nearest_buy_ema_distance_pct=nearest_buy_pct,
        nearest_sell_ema=nearest_sell_ema, nearest_sell_ema_distance=nearest_sell_dist, nearest_sell_ema_distance_pct=nearest_sell_pct,
        wma50=wma50, wma50_distance=wma50_distance, wma50_distance_pct=wma50_distance_pct,
        rsi=rsi, prev_rsi=prev_rsi, rsi_change=rsi_change,
        adx=adx_val, prev_adx=prev_adx,
        di_plus=di_plus_val, prev_di_plus=prev_di_plus,
        di_minus=di_minus_val, prev_di_minus=prev_di_minus,
        di_direction=di_direction, di_spread=di_spread, di_dominance=di_dominance,
        bull_momentum_weakening=bull_momentum_weakening,
        bear_momentum_weakening=bear_momentum_weakening,
        atr=atr, atr_ma=atr_ma, atr_ma_ratio=atr_ma_ratio, atr_change=atr_change, atr_percent=atr_percent,
        volume=volume, prev_volume=prev_volume, volume_ma=volume_ma, volume_ratio=volume_ratio,
        candle_range=candle_range, body=body, body_percent=body_percent, prev_body=prev_body, prev_body_percent=prev_body_percent, 
        upper_wick=upper_wick, lower_wick=lower_wick,
        close_location=close_location, candle_direction=candle_direction,
        displacement_atr=displacement_atr, candle_range_atr=candle_range_atr,
        change=change, change_percent=change_percent,
    )
    return ctx