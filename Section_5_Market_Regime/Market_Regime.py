# ======================================================
# SECTION 5: MARKET REGIME ENGINE
# ======================================================
#
# Section 5 consumes:
#
#   Section 4 → FeaturePacket
#   Section 1 → GlobalCorePacket
#
# This module does NOT calculate features.
# It only interprets the already-produced FeaturePacket.
# ======================================================

from dataclasses import dataclass

from .import_features_packet import FeaturePacket
from .import_global_core_packet import (
    create_global_core_packet,

    CONTROL_BULL,
    CONTROL_BEAR,
    CONTROL_BALANCED,
    CONTROL_NONE,

    ENERGY_EXPANDING,
    ENERGY_NORMAL,
    ENERGY_CONTRACTING,
    ENERGY_DEAD,

    REGIME_BULL_EXPANSION,
    REGIME_BEAR_EXPANSION,
    REGIME_BULL_TREND,
    REGIME_BEAR_TREND,
    REGIME_COMPRESSION,
    REGIME_RANGE,

    FATIGUE_BULLISH,
    FATIGUE_BEARISH,
    FATIGUE_NONE,

    TREND_FRESH,
    TREND_MATURE,
    TREND_WEAK,
    TREND_NONE,

    TRANSITION_NONE,
    TRANSITION_RISK,
    TRANSITION_ACTIVE,
)


@dataclass
class MarketRegime:
    control_state: str = CONTROL_NONE
    energy_state: str = ENERGY_DEAD
    regime_state: str = REGIME_RANGE
    fatigue_state: str = FATIGUE_NONE
    trend_state: str = TREND_NONE
    transition_state: str = TRANSITION_NONE


def calculate_market_regime(
    feature_packet: FeaturePacket
) -> MarketRegime:

    # --------------------------------------------------
    # Invalid FeaturePacket
    # --------------------------------------------------

    if feature_packet is None or not feature_packet.valid:
        return MarketRegime()

    # --------------------------------------------------
    # FeaturePacket canonical payload
    # --------------------------------------------------
    #
    # Section 4 stores all calculated feature values
    # inside the canonical .features dictionary.
    #
    # Section 5 consumes those values.
    # It does NOT recalculate them.
    # --------------------------------------------------

    features = feature_packet.features

    if features is None:
        return MarketRegime()

    # --------------------------------------------------
    # Global Core canonical packet
    # --------------------------------------------------
    #
    # Global Core owns market memory.
    # We access it through the Section 5 adapter rather
    # than importing Section 1 implementation modules.
    # --------------------------------------------------

    global_packet = create_global_core_packet()
    market_memory = global_packet.market_memory

    # ==================================================
    # 1 CONTROL
    # ==================================================

    di_plus = features.get("di_plus", 0.0) or 0.0
    di_minus = features.get("di_minus", 0.0) or 0.0

    di_direction = di_plus - di_minus
    di_strength = abs(di_direction)

    if di_direction > 10:
        control_state = CONTROL_BULL
    elif di_direction < -10:
        control_state = CONTROL_BEAR
    elif di_strength < 5:
        control_state = CONTROL_NONE
    else:
        control_state = CONTROL_BALANCED

    # ==================================================
    # 2 ENERGY
    # ==================================================

    atr_ma_ratio = features.get("atr_ma_ratio", 1.0) or 1.0
    adx = features.get("adx", 0.0) or 0.0

    atr_expanding = atr_ma_ratio > 1.20
    atr_contracting = atr_ma_ratio < 0.80

    if atr_expanding and adx >= 35:
        energy_state = ENERGY_EXPANDING
    elif atr_contracting:
        energy_state = ENERGY_CONTRACTING
    elif adx >= 25:
        energy_state = ENERGY_NORMAL
    else:
        energy_state = ENERGY_DEAD

    # ==================================================
    # 3 REGIME
    # ==================================================

    ema_bull_structure = bool(
        features.get("ema_bull_structure", False)
    )

    ema_bear_structure = bool(
        features.get("ema_bear_structure", False)
    )

    price_above_ema50 = bool(
        features.get("price_above_ema50", False)
    )

    price_above_ema200 = bool(
        features.get("price_above_ema200", False)
    )

    price_above_vwap = bool(
        features.get("price_above_vwap", False)
    )

    price_below_ema50 = bool(
        features.get("price_below_ema50", False)
    )

    price_below_ema200 = bool(
        features.get("price_below_ema200", False)
    )

    price_below_vwap = bool(
        features.get("price_below_vwap", False)
    )

    bull_trend = (
        ema_bull_structure
        and price_above_ema50
        and price_above_ema200
        and price_above_vwap
    )

    bear_trend = (
        ema_bear_structure
        and price_below_ema50
        and price_below_ema200
        and price_below_vwap
    )

    if bull_trend:
        regime_state = (
            REGIME_BULL_EXPANSION
            if atr_expanding
            else REGIME_BULL_TREND
        )

    elif bear_trend:
        regime_state = (
            REGIME_BEAR_EXPANSION
            if atr_expanding
            else REGIME_BEAR_TREND
        )

    elif atr_contracting:
        regime_state = REGIME_COMPRESSION

    else:
        regime_state = REGIME_RANGE

    # ==================================================
    # 4 FATIGUE
    # ==================================================

    prev_di_plus = features.get("prev_di_plus", 0.0) or 0.0
    prev_di_minus = features.get("prev_di_minus", 0.0) or 0.0
    prev_adx = features.get("prev_adx", 0.0) or 0.0

    bull_fatigue = (
        ema_bull_structure
        and di_plus < prev_di_plus
        and adx < prev_adx
    )

    bear_fatigue = (
        ema_bear_structure
        and di_minus < prev_di_minus
        and adx < prev_adx
    )

    if bull_fatigue:
        fatigue_state = FATIGUE_BULLISH
    elif bear_fatigue:
        fatigue_state = FATIGUE_BEARISH
    else:
        fatigue_state = FATIGUE_NONE

    # ==================================================
    # 5 TREND
    # ==================================================

    prev_di_strength = abs(
        prev_di_plus - prev_di_minus
    )

    trend_strength_increasing = (
        adx > prev_adx
        and di_strength > prev_di_strength
    )

    trend_strength_decreasing = (
        adx < prev_adx
        and di_strength < prev_di_strength
    )

    if ema_bull_structure or ema_bear_structure:

        if trend_strength_increasing:
            trend_state = TREND_FRESH

        elif trend_strength_decreasing:
            trend_state = TREND_WEAK

        else:
            trend_state = TREND_MATURE

    else:
        trend_state = TREND_NONE

    # ==================================================
    # 6 TRANSITION
    # ==================================================

    last_regime = market_memory.last_regime

    regime_changed = (
        last_regime not in ("", "UNKNOWN")
        and last_regime != regime_state
    )

    weakening_trend = (
        regime_state in (
            REGIME_BULL_TREND,
            REGIME_BEAR_TREND,
            REGIME_BULL_EXPANSION,
            REGIME_BEAR_EXPANSION,
        )
        and adx < prev_adx
    )

    ema_compression = features.get(
        "ema_compression",
        0
    ) or 0

    compression_building = (
        ema_compression > 0
        and atr_contracting
    )

    if regime_changed:
        transition_state = TRANSITION_ACTIVE

    elif weakening_trend or compression_building:
        transition_state = TRANSITION_RISK

    else:
        transition_state = TRANSITION_NONE

    # ==================================================
    # UPDATE GLOBAL MARKET MEMORY
    # ==================================================

    market_memory.last_regime = regime_state

    # ==================================================
    # RETURN REGIME
    # ==================================================

    return MarketRegime(
        control_state=control_state,
        energy_state=energy_state,
        regime_state=regime_state,
        fatigue_state=fatigue_state,
        trend_state=trend_state,
        transition_state=transition_state,
    )