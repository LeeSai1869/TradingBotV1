# ======================================================
# SECTION 6.2: SWING SCALPING ENGINE
# ======================================================
# Score breakdown:
#   Location Quality              30
#   Trend Direction & Strength    15
#   Trend Exhaustion              08
#   Price Action Confirmation     15
#   Volume / Liquidity            07
#   Structure Context             05
#   TOTAL                         80
# ======================================================

from dataclasses import dataclass
from typing import Optional
from Section_1_Global_Core import (
    CONTROL_BULL, CONTROL_BEAR,
    ENERGY_EXPANDING, ENERGY_NORMAL, ENERGY_CONTRACTING, ENERGY_DEAD,
    TREND_FRESH, TREND_MATURE, TREND_WEAK
)
from Section_6_Base_Scoring_Engines.import_config_packet import SwingScalpConfig
from Section_6_Base_Scoring_Engines.import_features_packet import (
MarketFeatures,
FeaturePacket,
)

from Section_6_Base_Scoring_Engines.import_regime_packet import MarketRegime

@dataclass
class SwingScalpOutput:
    swing_scalp_net_score: float = 0.0
    bull_score: float = 0.0
    bear_score: float = 0.0

@dataclass
class SwingScalpExecutionResult:
    tf: str
    features: Optional[MarketFeatures] = None
    regime: Optional[MarketRegime] = None
    output: Optional[SwingScalpOutput] = None

def swing_scalp_engine(
    features: MarketFeatures,
    regime: MarketRegime,
    cfg: SwingScalpConfig
) -> SwingScalpOutput:

    if features is None or features.context is None:
        return SwingScalpOutput()

    ctx = features.context
    lvls = features.levels
    im = features.imbalance
    loc = features.location
    s = features.structure

    # Safe helpers
    def safe(val, default=0.0):
        return val if val is not None else default

    c = safe(ctx.c)
    atr = safe(ctx.atr, 1.0)

    # ==================================================
    # 1. LOCATION QUALITY (max 30)
    # ==================================================
    bull_loc = 0.0
    bear_loc = 0.0

    # Support / Resistance
    if lvls and lvls.support_distance is not None and lvls.support_distance <= cfg.sr_distance_atr:
        bull_loc += 5
    if lvls and lvls.resistance_distance is not None and lvls.resistance_distance <= cfg.sr_distance_atr:
        bear_loc += 5

    # FVG Location
    if im:
        bull_zone_valid = (
            im.nearest_bull_fvg_low is not None and
            im.nearest_bull_fvg_high is not None and
            safe(im.nearest_bull_fvg_age, 999) <= cfg.location_fvg_max_age and
            safe(im.nearest_bull_fvg_strength, 0) >= cfg.location_fvg_quality_threshold
        )
        bear_zone_valid = (
            im.nearest_bear_fvg_low is not None and
            im.nearest_bear_fvg_high is not None and
            safe(im.nearest_bear_fvg_age, 999) <= cfg.location_fvg_max_age and
            safe(im.nearest_bear_fvg_strength, 0) >= cfg.location_fvg_quality_threshold
        )

        if bull_zone_valid:
            bull_low = im.nearest_bull_fvg_low
            bull_high = im.nearest_bull_fvg_high
            if (c >= bull_low - atr * cfg.location_fvg_distance_atr and
                c <= bull_high + atr * cfg.location_fvg_distance_atr):
                bull_loc += 5

        if bear_zone_valid:
            bear_low = im.nearest_bear_fvg_low
            bear_high = im.nearest_bear_fvg_high
            if (c >= bear_low - atr * cfg.location_fvg_distance_atr and
                c <= bear_high + atr * cfg.location_fvg_distance_atr):
                bear_loc += 5

    # EMA Location
    near_ema50 = ctx.ema50_distance_pct is not None and ctx.ema50_distance_pct <= cfg.ema_reaction_distance_pct
    near_ema200 = ctx.ema200_distance_pct is not None and ctx.ema200_distance_pct <= cfg.ema_reaction_distance_pct

    if near_ema50:
        if ctx.price_above_ema50:
            bull_loc += 1.5
        elif ctx.price_below_ema50:
            bear_loc += 1.5

    if near_ema200:
        if ctx.price_above_ema200:
            bull_loc += 1.5
        elif ctx.price_below_ema200:
            bear_loc += 1.5

    # Fibonacci (simplified – using direction only for now)
    # Full ratio logic can be expanded later when nearestFibRatio is available
    if loc and loc.fib_direction == "BULLISH_LEG":
        bull_loc += 1.5
    elif loc and loc.fib_direction == "BEARISH_LEG":
        bear_loc += 1.5

    # Liquidity
    if loc:
        if loc.distance_to_liquidity_low is not None and loc.distance_to_liquidity_low <= cfg.liquidity_distance_pct:
            bull_loc += 4
        if loc.distance_to_liquidity_high is not None and loc.distance_to_liquidity_high <= cfg.liquidity_distance_pct:
            bear_loc += 4

    # Order Block
    if im:
        valid_bull_ob = (
            im.bull_ob_low is not None and im.bull_ob_high is not None and
            safe(im.bull_ob_age, 999) <= cfg.ob_max_age and
            safe(im.bull_ob_strength, 0) >= cfg.ob_minimum_strength
        )
        valid_bear_ob = (
            im.bear_ob_low is not None and im.bear_ob_high is not None and
            safe(im.bear_ob_age, 999) <= cfg.ob_max_age and
            safe(im.bear_ob_strength, 0) >= cfg.ob_minimum_strength
        )

        if valid_bull_ob and im.bull_ob_low <= c <= im.bull_ob_high:
            bull_loc += 3
        if valid_bear_ob and im.bear_ob_low <= c <= im.bear_ob_high:
            bear_loc += 3

    # Breaker
    if im:
        if (im.bull_breaker_active and im.bull_breaker_low is not None and
            im.bull_breaker_high is not None and
            im.bull_breaker_low <= c <= im.bull_breaker_high):
            bull_loc += 2
        if (im.bear_breaker_active and im.bear_breaker_low is not None and
            im.bear_breaker_high is not None and
            im.bear_breaker_low <= c <= im.bear_breaker_high):
            bear_loc += 2

    # Volume Profile
    if loc:
        if loc.vp_va_low is not None and abs(c - loc.vp_va_low) / c * 100 <= cfg.volume_profile_distance_pct:
            bull_loc += 2.5
        if loc.vp_va_high is not None and abs(c - loc.vp_va_high) / c * 100 <= cfg.volume_profile_distance_pct:
            bear_loc += 2.5
        if loc.distance_to_poc is not None and abs(loc.distance_to_poc) <= cfg.volume_profile_distance_pct:
            bull_loc += 1
            bear_loc += 1
        if loc.distance_to_hvn is not None and abs(loc.distance_to_hvn) <= cfg.volume_profile_distance_pct:
            bull_loc += 0.5
            bear_loc += 0.5
        if loc.distance_to_lvn is not None and abs(loc.distance_to_lvn) <= cfg.volume_profile_distance_pct:
            bull_loc += 0.5
            bear_loc += 0.5
        if loc.inside_value_area:
            bull_loc += 0.5
            bear_loc += 0.5

    bull_loc = min(bull_loc, 30)
    bear_loc = min(bear_loc, 30)

    # ==================================================
    # 2. TREND DIRECTION & STRENGTH (max 15)
    # ==================================================
    bull_trend = 0.0
    bear_trend = 0.0

    if regime:
        if regime.control_state == CONTROL_BULL:
            if regime.trend_state == TREND_FRESH:
                bull_trend = 13
            elif regime.trend_state == TREND_MATURE:
                bull_trend = 9
            elif regime.trend_state == TREND_WEAK:
                bull_trend = 5
        elif regime.control_state == CONTROL_BEAR:
            if regime.trend_state == TREND_FRESH:
                bear_trend = 13
            elif regime.trend_state == TREND_MATURE:
                bear_trend = 9
            elif regime.trend_state == TREND_WEAK:
                bear_trend = 5

        energy_adj = 0.0
        if regime.energy_state == ENERGY_EXPANDING:
            energy_adj = 2
        elif regime.energy_state == ENERGY_CONTRACTING:
            energy_adj = -2
        elif regime.energy_state == ENERGY_DEAD:
            energy_adj = -3

        if bull_trend > 0:
            bull_trend = max(0, min(bull_trend + energy_adj, 15))
        if bear_trend > 0:
            bear_trend = max(0, min(bear_trend + energy_adj, 15))

    # ==================================================
    # 3. TREND EXHAUSTION (max 8)
    # ==================================================
    bull_exh = 0.0
    bear_exh = 0.0

    expansion_reducing = (
        ctx.prev_displacement_atr is not None and
        safe(ctx.displacement_atr) < ctx.prev_displacement_atr
    )
    bull_rejection = (safe(ctx.upper_wick) > safe(ctx.body) and
                      safe(ctx.close_location, 0.5) < 0.6)
    bear_rejection = (safe(ctx.lower_wick) > safe(ctx.body) and
                      safe(ctx.close_location, 0.5) > 0.4)

    if ctx.bull_momentum_weakening:
        if expansion_reducing:
            bear_exh += 3
        if bull_rejection:
            bear_exh += 3

    if ctx.bear_momentum_weakening:
        if expansion_reducing:
            bull_exh += 3
        if bear_rejection:
            bull_exh += 3

    context_bonus = 0.0
    if regime:
        if regime.trend_state == TREND_WEAK:
            context_bonus = 2
        elif regime.trend_state == TREND_MATURE:
            context_bonus = 1

    if bear_exh > 0:
        bear_exh = min(bear_exh + context_bonus, 8)
    if bull_exh > 0:
        bull_exh = min(bull_exh + context_bonus, 8)

    # ==================================================
    # 4. PRICE ACTION CONFIRMATION (max 15)
    # ==================================================
    bull_pa = 0.0
    bear_pa = 0.0

    strong_bull_close = (c > safe(ctx.o) and
                         safe(ctx.body_percent) >= cfg.reaction_body_percent)
    strong_bear_close = (c < safe(ctx.o) and
                         safe(ctx.body_percent) >= cfg.reaction_body_percent)

    if strong_bull_close:
        bull_pa += 3
    if strong_bear_close:
        bear_pa += 3

    # Note: bullSweepReclaim / bearSweepReject / break retest / engulfing
    # are not yet fully exposed in the current location/context modules.
    # They can be added later when those fields are completed.
    # For now we keep the structure ready.

    bull_pa = min(bull_pa, 15)
    bear_pa = min(bear_pa, 15)

    # ==================================================
    # 5. VOLUME PARTICIPATION (max 7)
    # ==================================================
    bull_vol = 0.0
    bear_vol = 0.0

    vol_ratio = safe(ctx.volume_ratio)

    if vol_ratio >= cfg.volume_expansion_strong:
        if c > safe(ctx.o):
            bull_vol = 7
        elif c < safe(ctx.o):
            bear_vol = 7
    elif vol_ratio >= cfg.volume_expansion_normal:
        if c > safe(ctx.o):
            bull_vol = 4
        elif c < safe(ctx.o):
            bear_vol = 4

    bull_vol = min(bull_vol, 7)
    bear_vol = min(bear_vol, 7)

    # ==================================================
    # 6. STRUCTURE CONTEXT (max 5)
    # ==================================================
    bull_struct = 0.0
    bear_struct = 0.0

    if s:
        if (s.current_active_pivot_low is not None and
            c > s.current_active_pivot_low and
            c <= s.current_active_pivot_low + atr * 2):
            bull_struct += 2

        if (s.current_active_pivot_high is not None and
            c < s.current_active_pivot_high and
            c >= s.current_active_pivot_high - atr * 2):
            bear_struct += 2

        if (s.prev_active_pivot_high is not None and
            c > s.prev_active_pivot_high and c > safe(ctx.o)):
            bull_struct += 3

        if (s.prev_active_pivot_low is not None and
            c < s.prev_active_pivot_low and c < safe(ctx.o)):
            bear_struct += 3

    bull_struct = min(bull_struct, 5)
    bear_struct = min(bear_struct, 5)

    # ==================================================
    # FINAL SCORE
    # ==================================================
    bull_total = min(bull_loc + bull_trend + bull_exh + bull_pa + bull_vol + bull_struct, 80)
    bear_total = min(bear_loc + bear_trend + bear_exh + bear_pa + bear_vol + bear_struct, 80)

    net = bull_total - bear_total

    return SwingScalpOutput(
        swing_scalp_net_score=net,
        bull_score=bull_total,
        bear_score=bear_total
    )

def execute_swing_scalp_engine_from_packet(
    packet: FeaturePacket,
    cfg: SwingScalpConfig
) -> SwingScalpExecutionResult:

    if packet is None or not packet.valid or packet.features is None:
        return SwingScalpExecutionResult(tf=packet.tf if packet else "")

    output = swing_scalp_engine(packet.features, packet.regime, cfg)

    return SwingScalpExecutionResult(
        tf=packet.tf,
        features=packet.features,
        regime=packet.regime,
        output=output
    )