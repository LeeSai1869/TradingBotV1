"""Section 4 — feature modules. Each file exposes a pure compute(df) -> dataclass."""
from .ema import EMAFeatures, compute as compute_ema
from .wma import WMAFeatures, compute as compute_wma
from .rsi import RSIFeatures, compute as compute_rsi
from .di_adx import DMIFeatures, compute as compute_dmi
from .atr import ATRFeatures, compute as compute_atr
from .volume import VolumeFeatures, compute as compute_volume
from .candle import CandleFeatures, compute as compute_candle
from .vwap import VWAPFeatures, compute as compute_vwap

__all__ = [
    "EMAFeatures", "compute_ema",
    "WMAFeatures", "compute_wma",
    "RSIFeatures", "compute_rsi",
    "DMIFeatures", "compute_dmi",
    "ATRFeatures", "compute_atr",
    "VolumeFeatures", "compute_volume",
    "CandleFeatures", "compute_candle",
    "VWAPFeatures", "compute_vwap",
]
