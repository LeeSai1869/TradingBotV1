# ======================================================
# SECTION 2: INPUTS (FULL MULTI-ENGINE)
# ======================================================

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from Section_1_Global_Core.global_packet import (
    normalize_tf,
    is_supported_tf,
    SUPPORTED_TIMEFRAMES,
    ENGINE_SCALP,
    ENGINE_SWING_SCALP,
    ENGINE_SWING,
    ENGINE_BREAKOUT,
    engine_index,
    REF_MARKET_CURRENT,
    REF_MARKET_BTC
)

# =========================
# 2.1 SYMBOL SOURCE
# =========================

SYMBOL_MODE: str = "CURRENT"          # "CURRENT" or "BINANCE:BTCUSDT"
DATA_SYMBOL: str = "BTCUSDT"

# =========================
# 2.2 ENGINE ACTIVATION
# =========================

ENABLE_SCALP_ENGINE: bool = True
ENABLE_SWING_SCALP_ENGINE: bool = False
ENABLE_SWING_ENGINE: bool = False
ENABLE_BREAKOUT_ENGINE: bool = False

# =========================
# 2.3 HUD TIMEFRAME REGISTRY
# =========================

HUD_TF_COUNT: int = 8

HUD_TIMEFRAMES: List[str] = [
    "1",    # TF 1
    "5",    # TF 2
    "15",   # TF 3
    "60",   # TF 4
    "240",  # TF 5
    "1D",   # TF 6
    "30",   # TF 7
    "1W",   # TF 8
]

def get_hud_tf(i: int) -> Optional[str]:
    if i < 0 or i >= HUD_TF_COUNT or i >= len(HUD_TIMEFRAMES):
        return None
    return normalize_tf(HUD_TIMEFRAMES[i])

def is_hud_tf_active(i: int) -> bool:
    return 0 <= i < HUD_TF_COUNT

def find_hud_tf_slot(tf: str) -> int:
    target = normalize_tf(tf)
    if not is_supported_tf(target):
        return -1
    for i in range(8):
        registered = get_hud_tf(i)
        if registered is not None and registered == target:
            return i
    return -1

# =========================
# 2.4 EMA SETTINGS
# =========================

EMA_7_LEN: int = 7
EMA_25_LEN: int = 25
EMA_50_LEN: int = 50
EMA_100_LEN: int = 100
EMA_200_LEN: int = 200
EMA_300_LEN: int = 300

EMA_7_SHOW: bool = True
EMA_25_SHOW: bool = True
EMA_50_SHOW: bool = True
EMA_100_SHOW: bool = True
EMA_200_SHOW: bool = True
EMA_300_SHOW: bool = True

# =========================
# 2.5 VOLUME PROFILE / VOLUME / LIQUIDITY / RANGE / FIB / FVG / VWAP
# =========================

VP_LOOKBACK: int = 200
VP_BINS: int = 24
VP_VALUE_AREA_PCT: float = 70.0

VOLUME_LOOKBACK: int = 20
LIQUIDITY_LOOKBACK: int = 20
RANGE_LOOKBACK: int = 100

FIB_PIVOT_REACTION_ATR: float = 1.0
FVG_ZONE_DISTANCE_ATR: float = 2.0

VWAP_BAND_MULTIPLIER_1: float = 1.0
VWAP_BAND_MULTIPLIER_2: float = 2.0

# =========================
# 2.6 SCALP CONFIG
# =========================

@dataclass
class ScalpConfig:
    adx_trend_start: int = 10
    adx_strong_trend: int = 18
    di_separation_strong: float = 15.0
    di_separation_weak: float = 8.0
    reaction_body_percent: float = 0.60
    reaction_displacement_atr: float = 0.5

    strong_buy_threshold: float = 90.0
    buy_threshold: float = 75.0
    weak_buy_threshold: float = 60.0
    strong_sell_threshold: float = -90.0
    sell_threshold: float = -75.0
    weak_sell_threshold: float = -60.0

    scalp_score_contribution_pct: float = 0.80
    confluence_score_contribution_pct: float = 0.20

    primary_buy_setup_threshold: float = 50.0
    primary_sell_setup_threshold: float = -50.0
    secondary_buy_setup_threshold: float = 40.0
    secondary_sell_setup_threshold: float = -40.0

    scalp_confidence_on_30m: float = 0.40
    scalp_confidence_on_60m: float = 0.30
    scalp_confidence_on_120m: float = 0.20
    scalp_confidence_on_240m: float = 0.10

# =========================
# 2.7 SWING SCALP CONFIG
# =========================

@dataclass
class SwingScalpConfig:
    sr_distance_atr: float = 1.5
    ema_reaction_distance_pct: float = 1.0
    fib_distance_pct: float = 0.5
    liquidity_distance_pct: float = 1.0

    location_fvg_distance_atr: float = 1.0
    location_fvg_max_age: int = 50
    location_fvg_quality_threshold: float = 2.0
    volume_profile_distance_pct: float = 1.0

    ob_max_age: int = 75
    ob_minimum_strength: float = 1.5

    reaction_body_percent: float = 0.60

    volume_expansion_strong: float = 1.8
    volume_expansion_normal: float = 1.2
    volume_expansion_weak: float = 0.6

# =========================
# 2.8 SWING CONFIG
# =========================

@dataclass
class SwingConfig:
    strong_adx: int = 35
    moderate_adx: int = 25
    strong_di_separation: float = 20.0
    moderate_di_separation: float = 10.0

    sr_distance_atr: float = 2.0
    ema_reaction_distance_pct: float = 2.0
    fib_distance_pct: float = 1.0
    liquidity_distance_pct: float = 2.0
    htf_fvg_distance_atr: float = 2.0
    htf_fvg_max_age: int = 150
    htf_fvg_quality_threshold: float = 2.5
    volume_profile_distance_pct: float = 2.0
    location_fvg_distance_atr: float = 0.5

    ob_max_age: int = 150
    ob_minimum_strength: float = 2.0

    rsi_bull_threshold: float = 55.0
    rsi_bear_threshold: float = 45.0

    confirmation_body_percent: float = 0.70

# =========================
# 2.9 BREAKOUT CONFIG
# =========================

@dataclass
class BreakoutConfig:
    structural_min_atr: float = 0.25
    min_bos_distance_atr: float = 0.05
    strong_bos_distance_atr: float = 0.25
    structural_max_age: int = 150
    breakout_max_age: int = 30
    structural_pressure_distance_atr: float = 0.50

    displacement_min_atr: float = 0.50
    displacement_strong_atr: float = 1.00

    participation_normal_ratio: float = 1.30
    participation_strong_ratio: float = 1.50
    participation_extreme_ratio: float = 2.00
    directional_close_threshold: float = 0.65
    abnormal_volume_ratio: float = 5.00
    participation_expansion_normal: float = 0.20
    participation_expansion_strong: float = 0.50
    participation_quality_body_threshold: float = 0.60
    participation_quality_close_threshold: float = 0.65
    participation_validation_distance_atr: float = 0.25

    retest_distance_atr: float = 0.25
    retest_max_bars: int = 10
    bullish_acceptance_close_location: float = 0.65
    bearish_acceptance_close_location: float = 0.35

    failure_min_atr: float = 0.05
    failure_strong_atr: float = 0.25

# =========================
# 2.10 ENGINE CONFIG BUNDLE
# =========================

@dataclass
class EngineConfigBundle:
    scalp: ScalpConfig = field(default_factory=ScalpConfig)
    swing_scalp: SwingScalpConfig = field(default_factory=SwingScalpConfig)
    swing: SwingConfig = field(default_factory=SwingConfig)
    breakout: BreakoutConfig = field(default_factory=BreakoutConfig)

engine_config = EngineConfigBundle()

# Convenience aliases
scalp_config = engine_config.scalp
swing_scalp_config = engine_config.swing_scalp
swing_config = engine_config.swing
breakout_config = engine_config.breakout

# =========================
# 2.11 FEATURE CALCULATION LENGTHS
# =========================

@dataclass
class FeatureCalculationConfig:
    rsi_len: int = 7
    adx_len: int = 10
    atr_len: int = 10
    atr_ma_len: int = 14
    sr_pivot_len: int = 3

# Per-engine feature configs
SCALP_FEATURE_CONFIG = FeatureCalculationConfig(
    rsi_len=7, adx_len=10, atr_len=10, atr_ma_len=14, sr_pivot_len=3
)

SWING_SCALP_FEATURE_CONFIG = FeatureCalculationConfig(
    rsi_len=7, adx_len=10, atr_len=10, atr_ma_len=14, sr_pivot_len=3
)

SWING_FEATURE_CONFIG = FeatureCalculationConfig(
    rsi_len=7, adx_len=10, atr_len=10, atr_ma_len=14, sr_pivot_len=3
)

BREAKOUT_FEATURE_CONFIG = FeatureCalculationConfig(
    rsi_len=7, adx_len=10, atr_len=10, atr_ma_len=14, sr_pivot_len=3
)

feature_config_registry: Dict[str, FeatureCalculationConfig] = {
    ENGINE_SCALP: SCALP_FEATURE_CONFIG,
    ENGINE_SWING_SCALP: SWING_SCALP_FEATURE_CONFIG,
    ENGINE_SWING: SWING_FEATURE_CONFIG,
    ENGINE_BREAKOUT: BREAKOUT_FEATURE_CONFIG,
}

def get_feature_calculation_config(engine_name: str) -> Optional[FeatureCalculationConfig]:
    return feature_config_registry.get(engine_name)

# =========================
# 2.12 STYLE (optional – mostly for future UI)
# =========================

TEXT_SIZE: str = "small"
TABLE_POSITION: str = "top_right"

# ======================================================
# SECTION 2 END
# ======================================================