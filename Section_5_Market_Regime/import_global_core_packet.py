# ======================================================
# IMPORT GLOBAL CORE PACKET
# Section 5 → Section 1 interface
# ======================================================
#
# This file is the Section 5 adapter for the canonical
# Global Core packet.
#
# It contains NO Global Core logic.
# It only exposes the stable public gateway owned by
# Section 1 Global Core.
# ======================================================

from Section_1_Global_Core.global_packet import (
    GlobalCorePacket,
    create_global_core_packet,

    # Section 1.2 — Market Definitions
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


__all__ = [
    "GlobalCorePacket",
    "create_global_core_packet",

    "CONTROL_BULL",
    "CONTROL_BEAR",
    "CONTROL_BALANCED",
    "CONTROL_NONE",

    "ENERGY_EXPANDING",
    "ENERGY_NORMAL",
    "ENERGY_CONTRACTING",
    "ENERGY_DEAD",

    "REGIME_BULL_EXPANSION",
    "REGIME_BEAR_EXPANSION",
    "REGIME_BULL_TREND",
    "REGIME_BEAR_TREND",
    "REGIME_COMPRESSION",
    "REGIME_RANGE",

    "FATIGUE_BULLISH",
    "FATIGUE_BEARISH",
    "FATIGUE_NONE",

    "TREND_FRESH",
    "TREND_MATURE",
    "TREND_WEAK",
    "TREND_NONE",

    "TRANSITION_NONE",
    "TRANSITION_RISK",
    "TRANSITION_ACTIVE",
]