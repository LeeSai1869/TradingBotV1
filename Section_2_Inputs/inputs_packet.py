from dataclasses import dataclass
from typing import List

from . import Inputs as inputs


@dataclass
class InputsPacket:
    symbol_mode: str
    data_symbol: str

    enable_scalp_engine: bool
    enable_swing_scalp_engine: bool
    enable_swing_engine: bool
    enable_breakout_engine: bool

    hud_tf_count: int
    hud_timeframes: List[str]

    ema_7: int
    ema_25: int
    ema_50: int
    ema_100: int
    ema_200: int
    ema_300: int

    show_ema_7: bool
    show_ema_25: bool
    show_ema_50: bool
    show_ema_100: bool
    show_ema_200: bool
    show_ema_300: bool

    vp_lookback: int
    vp_bins: int
    vp_value_area_pct: float

    volume_lookback: int
    liquidity_lookback: int
    range_lookback: int

    fib_pivot_reaction_atr: float
    fvg_zone_distance_atr: float

    vwap_band_1: float
    vwap_band_2: float

    scalp_config: object
    swing_scalp_config: object
    swing_config: object
    breakout_config: object

    feature_calculation_config: object
    scalp_feature_config: object
    swing_scalp_feature_config: object
    swing_feature_config: object
    breakout_feature_config: object

    text_size: str
    table_position: str


def create_inputs_packet() -> InputsPacket:
    return InputsPacket(
        symbol_mode=inputs.SYMBOL_MODE,
        data_symbol=inputs.DATA_SYMBOL,

        enable_scalp_engine=inputs.ENABLE_SCALP_ENGINE,
        enable_swing_scalp_engine=inputs.ENABLE_SWING_SCALP_ENGINE,
        enable_swing_engine=inputs.ENABLE_SWING_ENGINE,
        enable_breakout_engine=inputs.ENABLE_BREAKOUT_ENGINE,

        hud_tf_count=inputs.HUD_TF_COUNT,
        hud_timeframes=inputs.HUD_TIMEFRAMES.copy(),

        # Section 2.4 — EMA lengths
        ema_7=inputs.EMA_7_LEN,
        ema_25=inputs.EMA_25_LEN,
        ema_50=inputs.EMA_50_LEN,
        ema_100=inputs.EMA_100_LEN,
        ema_200=inputs.EMA_200_LEN,
        ema_300=inputs.EMA_300_LEN,

        # Section 2.4 — EMA visibility
        show_ema_7=inputs.EMA_7_SHOW,
        show_ema_25=inputs.EMA_25_SHOW,
        show_ema_50=inputs.EMA_50_SHOW,
        show_ema_100=inputs.EMA_100_SHOW,
        show_ema_200=inputs.EMA_200_SHOW,
        show_ema_300=inputs.EMA_300_SHOW,

        # Section 2.5 — Volume Profile / Volume / Liquidity / Range
        vp_lookback=inputs.VP_LOOKBACK,
        vp_bins=inputs.VP_BINS,
        vp_value_area_pct=inputs.VP_VALUE_AREA_PCT,

        volume_lookback=inputs.VOLUME_LOOKBACK,
        liquidity_lookback=inputs.LIQUIDITY_LOOKBACK,
        range_lookback=inputs.RANGE_LOOKBACK,

        # Section 2.5 — Fibonacci / FVG / VWAP
        fib_pivot_reaction_atr=inputs.FIB_PIVOT_REACTION_ATR,
        fvg_zone_distance_atr=inputs.FVG_ZONE_DISTANCE_ATR,

        vwap_band_1=inputs.VWAP_BAND_MULTIPLIER_1,
        vwap_band_2=inputs.VWAP_BAND_MULTIPLIER_2,

        # Section 2.10 — Engine configuration bundle
        scalp_config=inputs.scalp_config,
        swing_scalp_config=inputs.swing_scalp_config,
        swing_config=inputs.swing_config,
        breakout_config=inputs.breakout_config,

        # Section 2.11 — Feature calculation configuration
        # No single global FEATURE_CALCULATION_CONFIG exists in
        # the current canonical Inputs.py. The Scalp feature
        # configuration is used as the packet's compatibility
        # field for this legacy/general slot.
        feature_calculation_config=inputs.SCALP_FEATURE_CONFIG,

        scalp_feature_config=inputs.SCALP_FEATURE_CONFIG,
        swing_scalp_feature_config=inputs.SWING_SCALP_FEATURE_CONFIG,
        swing_feature_config=inputs.SWING_FEATURE_CONFIG,
        breakout_feature_config=inputs.BREAKOUT_FEATURE_CONFIG,

        # Section 2.12 — Style
        text_size=inputs.TEXT_SIZE,
        table_position=inputs.TABLE_POSITION,
    )


__all__ = [
    "InputsPacket",
    "create_inputs_packet",
]