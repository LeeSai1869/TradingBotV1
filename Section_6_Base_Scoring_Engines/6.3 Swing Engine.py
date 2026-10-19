# ======================================================
# SECTION 6.3: SWING ENGINE
# ======================================================
# Macro / Higher-Timeframe engine.
# Score breakdown (80-point system for consistency):
#   Macro Structure & Control     25
#   Macro Location Quality        25
#   Momentum Regime               15
#   Price Action Confirmation     10
#   Order Block / HTF Context      5
#   TOTAL                         80
# ======================================================

from dataclasses import dataclass
from typing import Optional

from section_01_globals import (
    CONTROL_BULL, CONTROL_BEAR, CONTROL_BALANCED, CONTROL_NONE,
    ENERGY_EXPANDING, ENERGY_NORMAL, ENERGY_CONTRACTING, ENERGY_DEAD,
    TREND_FRESH, TREND_MATURE, TREND_WEAK, TREND_NONE
)
from section_02_inputs import SwingConfig
from section_04_features.market_features import MarketFeatures
from section_05_regime import MarketRegime
from section_04_features import FeaturePacket


@dataclass
class SwingOutput:
    swing_net_score: float = 0.0
    bull_score: float = 0.0
    bear_score: float = 0.0


@dataclass
class SwingExecutionResult:
    tf: str
    features: Optional[MarketFeatures] = None
    regime: Optional[MarketRegime] = None
    output: Optional[SwingOutput] = None


def swing_engine(
    features: MarketFeatures,
    regime: MarketRegime,
    cfg: SwingConfig
) -> SwingOutput:
    """
    Calculate the 80-point Swing (macro) score.
    """
    if features is None or features.context is None:
        return SwingOutput()

    ctx = features.context
    lvls = features.levels
    im = features.imbalance
    loc = features.location
    s = features.structure

    def safe(val, default=0.0):
        return val if val is not None else default

    c = safe(ctx.c)
    atr = safe(ctx.atr, 1.0)
    rsi = safe(ctx.rsi, 50.0)
    adx = safe(ctx.adx, 0.0)
    di_plus = safe(ctx.di_plus, 0.0)
    di_minus = safe(ctx.di_minus, 0.0)
    di_spread = safe(ctx.di_spread, 0.0)

    # ==================================================
    # 1. MACRO STRUCTURE & CONTROL (max 25)
    # ==================================================
    bull_struct = 0.0
    bear_struct = 0.0

    # Control + Trend state from regime
    if regime:
        if regime.control_state == CONTROL_BULL:
            if regime.trend_state == TREND_FRESH:
                bull_struct = 18
            elif regime.trend_state == TREND_MATURE:
                bull_struct = 14
            elif regime.trend_state == TREND_WEAK:
                bull_struct = 8
            else:
                bull_struct = 5
        elif regime.control_state == CONTROL_BEAR:
            if regime.trend_state == TREND_FRESH:
                bear_struct = 18
            elif regime.trend_state == TREND_MATURE:
                bear_struct = 14
            elif regime.trend_state == TREND_WEAK:
                bear_struct = 8
            else:
                bear_struct = 5

    # ADX + DI separation boost (macro thresholds)
    if di_plus > di_minus:
        if adx >= cfg.strong_adx and di_spread >= cfg.strong_di_separation:
            bull_struct += 7
        elif adx >= cfg.moderate_adx and di_spread >= cfg.moderate_di_separation:
            bull_struct += 4
    elif di_minus > di_plus:
        if adx >= cfg.strong_adx and di_spread >= cfg.strong_di_separation:
            bear_struct += 7
        elif adx >= cfg.moderate_adx and di_spread >= cfg.moderate_di_separation:
            bear_struct += 4

    # Energy adjustment
    energy_adj = 0.0
    if regime:
        if regime.energy_state == ENERGY_EXPANDING:
            energy_adj = 2
        elif regime.energy_state == ENERGY_CONTRACTING:
            energy_adj = -2
        elif regime.energy_state == ENERGY_DEAD:
            energy_adj = -4

    if bull_struct > 0:
        bull_struct = max(0.0, min(bull_struct + energy_adj, 25))
    if bear_struct > 0:
        bear_struct = max(0.0, min(bear_struct + energy_adj, 25))

    # ==================================================
    # 2. MACRO LOCATION QUALITY (max 25)
    # ==================================================
    bull_loc = 0.0
    bear_loc = 0.0

    # Support / Resistance (wider macro distances)
    if lvls:
        if lvls.support_distance is not None and lvls.support_distance <= cfg.sr_distance_atr:
            bull_loc += 6
        if lvls.resistance_distance is not None and lvls.resistance_distance <= cfg.sr_distance_atr:
            bear_loc += 6

    # EMA200 / EMA300 reaction (macro)
    near_ema200 = ctx.ema200_distance_pct is not None and ctx.ema200_distance_pct <= cfg.ema_reaction_distance_pct
    near_ema300 = ctx.ema300_distance_pct is not None and ctx.ema300_distance_pct <= cfg.ema_reaction_distance_pct

    if near_ema200:
        if ctx.price_above_ema200:
            bull_loc += 3
        elif ctx.price_below_ema200:
            bear_loc += 3

    if near_ema300:
        if ctx.price_above_ema300:
            bull_loc += 2
        elif ctx.price_below_ema300:
            bear_loc += 2

    # HTF FVG (higher quality threshold + age)
    if im:
        bull_htf_fvg_valid = (
            im.nearest_bull_fvg_low is not None and
            im.nearest_bull_fvg_high is not None and
            safe(im.nearest_bull_fvg_age, 999) <= cfg.htf_fvg_max_age and
            safe(im.nearest_bull_fvg_strength, 0) >= cfg.htf_fvg_quality_threshold
        )
        bear_htf_fvg_valid = (
            im.nearest_bear_fvg_low is not None and
            im.nearest_bear_fvg_high is not None and
            safe(im.nearest_bear_fvg_age, 999) <= cfg.htf_fvg_max_age and
            safe(im.nearest_bear_fvg_strength, 0) >= cfg.htf_fvg_quality_threshold
        )

        if bull_htf_fvg_valid:
            bull_low = im.nearest_bull_fvg_low
            bull_high = im.nearest_bull_fvg_high
            if (c >= bull_low - atr * cfg.htf_fvg_distance_atr and
                    c <= bull_high + atr * cfg.htf_fvg_distance_atr):
                bull_loc += 5

        if bear_htf_fvg_valid:
            bear_low = im.nearest_bear_fvg_low
            bear_high = im.nearest_bear_fvg_high
            if (c >= bear_low - atr * cfg.htf_fvg_distance_atr and
                    c <= bear_high + atr * cfg.htf_fvg_distance_atr):
                bear_loc += 5

    # Liquidity (macro)
    if loc:
        if loc.distance_to_liquidity_low is not None and loc.distance_to_liquidity_low <= cfg.liquidity_distance_pct:
            bull_loc += 3
        if loc.distance_to_liquidity_high is not None and loc.distance_to_liquidity_high <= cfg.liquidity_distance_pct:
            bear_loc += 3

    # Volume Profile
    if loc:
        if loc.vp_va_low is not None and abs(c - loc.vp_va_low) / max(c, 1e-9) * 100 <= cfg.volume_profile_distance_pct:
            bull_loc += 2
        if loc.vp_va_high is not None and abs(c - loc.vp_va_high) / max(c, 1e-9) * 100 <= cfg.volume_profile_distance_pct:
            bear_loc += 2
        if loc.distance_to_poc is not None and abs(loc.distance_to_poc) <= cfg.volume_profile_distance_pct:
            bull_loc += 1
            bear_loc += 1

    # Fibonacci
    if loc:
        if loc.fib_direction == "BULLISH_LEG":
            bull_loc += 2
        elif loc.fib_direction == "BEARISH_LEG":
            bear_loc += 2

    bull_loc = min(bull_loc, 25)
    bear_loc = min(bear_loc, 25)

    # ==================================================
    # 3. MOMENTUM REGIME (max 15)
    # ==================================================
    bull_mom = 0.0
    bear_mom = 0.0

    if rsi >= cfg.rsi_bull_threshold:
        bull_mom = 10
        if rsi > 60:
            bull_mom += 3
        if di_plus > di_minus and adx >= cfg.moderate_adx:
            bull_mom += 2
    elif rsi <= cfg.rsi_bear_threshold:
        bear_mom = 10
        if rsi < 40:
            bear_mom += 3
        if di_minus > di_plus and adx >= cfg.moderate_adx:
            bear_mom += 2

    bull_mom = min(bull_mom, 15)
    bear_mom = min(bear_mom, 15)

    # ==================================================
    # 4. PRICE ACTION CONFIRMATION (max 10)
    # ==================================================
    bull_pa = 0.0
    bear_pa = 0.0

    body_pct = safe(ctx.body_percent)
    close_loc = safe(ctx.close_location, 0.5)
    candle_dir = safe(ctx.candle_direction)

    strong_bull_candle = (
        candle_dir > 0 and
        body_pct >= cfg.confirmation_body_percent and
        close_loc >= 0.65
    )
    strong_bear_candle = (
        candle_dir < 0 and
        body_pct >= cfg.confirmation_body_percent and
        close_loc <= 0.35
    )

    if strong_bull_candle:
        bull_pa = 8
        if safe(ctx.displacement_atr) >= 0.8:
            bull_pa += 2
    if strong_bear_candle:
        bear_pa = 8
        if safe(ctx.displacement_atr) >= 0.8:
            bear_pa += 2

    bull_pa = min(bull_pa, 10)
    bear_pa = min(bear_pa, 10)

    # ==================================================
    # 5. ORDER BLOCK / HTF CONTEXT (max 5)
    # ==================================================
    bull_ob = 0.0
    bear_ob = 0.0

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
            bull_ob += 3
        if valid_bear_ob and im.bear_ob_low <= c <= im.bear_ob_high:
            bear_ob += 3

        # Breaker bonus
        if (im.bull_breaker_active and im.bull_breaker_low is not None and
                im.bull_breaker_high is not None and
                im.bull_breaker_low <= c <= im.bull_breaker_high):
            bull_ob += 2
        if (im.bear_breaker_active and im.bear_breaker_low is not None and
                im.bear_breaker_high is not None and
                im.bear_breaker_low <= c <= im.bear_breaker_high):
            bear_ob += 2

    bull_ob = min(bull_ob, 5)
    bear_ob = min(bear_ob, 5)

    # ==================================================
    # FINAL SCORE
    # ==================================================
    bull_total = min(
        bull_struct + bull_loc + bull_mom + bull_pa + bull_ob, 80
    )
    bear_total = min(
        bear_struct + bear_loc + bear_mom + bear_pa + bear_ob, 80
    )

    net = bull_total - bear_total

    return SwingOutput(
        swing_net_score=net,
        bull_score=bull_total,
        bear_score=bear_total
    )


def execute_swing_engine_from_packet(
    packet: FeaturePacket,
    cfg: SwingConfig
) -> SwingExecutionResult:
    """
    Execute Swing Engine from a FeaturePacket.
    """
    if packet is None or not packet.valid or packet.features is None:
        return SwingExecutionResult(tf=packet.tf if packet else "", output=SwingOutput())

    output = swing_engine(packet.features, packet.regime, cfg)

    return SwingExecutionResult(
        tf=packet.tf,
        features=packet.features,
        regime=packet.regime,
        output=output
    )