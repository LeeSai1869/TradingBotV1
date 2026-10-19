# ======================================================
# SECTION 6.4: BREAKOUT ENGINE
# ======================================================
# Structural break + displacement + participation engine.
# Score breakdown (80-point system for consistency):
#   Structural Break / BOS          25
#   Price Displacement              20
#   Volume / Participation          15
#   Retest / Acceptance             12
#   Structural Failure / Invalidation  8
#   TOTAL                           80
# ======================================================

from dataclasses import dataclass
from typing import Optional

from section_02_inputs import BreakoutConfig
from section_04_features.market_features import MarketFeatures
from section_05_regime import MarketRegime
from section_04_features import FeaturePacket


@dataclass
class BreakoutOutput:
    breakout_net_score: float = 0.0
    bull_score: float = 0.0
    bear_score: float = 0.0
    breakout_stage: int = 0          # 0 = none, 1 = break, 2 = retest, 3 = accepted
    breakout_state: str = "NONE"     # NONE / BULL_BREAK / BEAR_BREAK / BULL_ACCEPTED / BEAR_ACCEPTED / FAILED


@dataclass
class BreakoutExecutionResult:
    tf: str
    features: Optional[MarketFeatures] = None
    regime: Optional[MarketRegime] = None
    output: Optional[BreakoutOutput] = None


def breakout_engine(
    features: MarketFeatures,
    regime: MarketRegime,
    cfg: BreakoutConfig
) -> BreakoutOutput:
    """
    Calculate the 80-point Breakout score + stage / state.
    """
    if features is None or features.context is None:
        return BreakoutOutput()

    ctx = features.context
    s = features.structure
    im = features.imbalance
    loc = features.location

    def safe(val, default=0.0):
        return val if val is not None else default

    c = safe(ctx.c)
    o = safe(ctx.o)
    h = safe(ctx.h)
    l = safe(ctx.l)
    atr = max(safe(ctx.atr, 1.0), 1e-9)
    body = safe(ctx.body)
    body_pct = safe(ctx.body_percent)
    close_loc = safe(ctx.close_location, 0.5)
    displacement_atr = safe(ctx.displacement_atr)
    volume_ratio = safe(ctx.volume_ratio)
    candle_dir = safe(ctx.candle_direction)

    # ==================================================
    # 1. STRUCTURAL BREAK / BOS (max 25)
    # ==================================================
    bull_bos = 0.0
    bear_bos = 0.0
    active_bos_type = None          # "BULL" or "BEAR"
    bos_distance_atr = 0.0

    if s:
        # Bullish BOS (break of previous swing high / protected high)
        if s.prev_active_pivot_high is not None:
            bos_dist = (c - s.prev_active_pivot_high) / atr
            if bos_dist >= cfg.min_bos_distance_atr:
                bull_bos = 12
                if bos_dist >= cfg.strong_bos_distance_atr:
                    bull_bos = 20
                if displacement_atr >= cfg.displacement_min_atr:
                    bull_bos += 5
                active_bos_type = "BULL"
                bos_distance_atr = bos_dist

        # Bearish BOS (break of previous swing low / protected low)
        if s.prev_active_pivot_low is not None:
            bos_dist = (s.prev_active_pivot_low - c) / atr
            if bos_dist >= cfg.min_bos_distance_atr:
                bear_bos = 12
                if bos_dist >= cfg.strong_bos_distance_atr:
                    bear_bos = 20
                if displacement_atr >= cfg.displacement_min_atr:
                    bear_bos += 5
                active_bos_type = "BEAR"
                bos_distance_atr = bos_dist

        # Structural significance filter
        if active_bos_type and bos_distance_atr < cfg.structural_min_atr:
            bull_bos = 0.0
            bear_bos = 0.0
            active_bos_type = None

    bull_bos = min(bull_bos, 25)
    bear_bos = min(bear_bos, 25)

    # ==================================================
    # 2. PRICE DISPLACEMENT (max 20)
    # ==================================================
    bull_disp = 0.0
    bear_disp = 0.0

    if displacement_atr >= cfg.displacement_strong_atr:
        if candle_dir > 0:
            bull_disp = 20
        elif candle_dir < 0:
            bear_disp = 20
    elif displacement_atr >= cfg.displacement_min_atr:
        if candle_dir > 0:
            bull_disp = 12
        elif candle_dir < 0:
            bear_disp = 12

    # Body quality bonus
    if body_pct >= 0.60:
        if candle_dir > 0:
            bull_disp = min(bull_disp + 3, 20)
        elif candle_dir < 0:
            bear_disp = min(bear_disp + 3, 20)

    # ==================================================
    # 3. VOLUME / PARTICIPATION (max 15)
    # ==================================================
    bull_vol = 0.0
    bear_vol = 0.0

    if volume_ratio >= cfg.participation_extreme_ratio:
        score = 15
    elif volume_ratio >= cfg.participation_strong_ratio:
        score = 11
    elif volume_ratio >= cfg.participation_normal_ratio:
        score = 7
    else:
        score = 0

    if candle_dir > 0 and close_loc >= cfg.directional_close_threshold:
        bull_vol = score
    elif candle_dir < 0 and close_loc <= (1.0 - cfg.directional_close_threshold):
        bear_vol = score

    # Abnormal volume penalty / bonus
    if volume_ratio >= cfg.abnormal_volume_ratio:
        if candle_dir > 0:
            bull_vol = min(bull_vol + 2, 15)
        elif candle_dir < 0:
            bear_vol = min(bear_vol + 2, 15)

    bull_vol = min(bull_vol, 15)
    bear_vol = min(bear_vol, 15)

    # ==================================================
    # 4. RETEST / ACCEPTANCE (max 12)
    # ==================================================
    bull_retest = 0.0
    bear_retest = 0.0
    stage = 0
    state = "NONE"

    if s and active_bos_type:
        # Simple proximity-based retest detection
        # (full multi-bar retest memory can be added later with state)
        if active_bos_type == "BULL" and s.prev_active_pivot_high is not None:
            dist_to_level = abs(c - s.prev_active_pivot_high) / atr
            if dist_to_level <= cfg.retest_distance_atr:
                if close_loc >= cfg.bullish_acceptance_close_location and candle_dir > 0:
                    bull_retest = 12
                    stage = 3
                    state = "BULL_ACCEPTED"
                else:
                    bull_retest = 6
                    stage = 2
                    state = "BULL_BREAK"
            else:
                stage = 1
                state = "BULL_BREAK"

        elif active_bos_type == "BEAR" and s.prev_active_pivot_low is not None:
            dist_to_level = abs(c - s.prev_active_pivot_low) / atr
            if dist_to_level <= cfg.retest_distance_atr:
                if close_loc <= cfg.bearish_acceptance_close_location and candle_dir < 0:
                    bear_retest = 12
                    stage = 3
                    state = "BEAR_ACCEPTED"
                else:
                    bear_retest = 6
                    stage = 2
                    state = "BEAR_BREAK"
            else:
                stage = 1
                state = "BEAR_BREAK"

    bull_retest = min(bull_retest, 12)
    bear_retest = min(bear_retest, 12)

    # ==================================================
    # 5. STRUCTURAL FAILURE / INVALIDATION (max 8)
    # ==================================================
    bull_fail = 0.0
    bear_fail = 0.0

    if s:
        # Failure of a bullish break (price falls back below the broken level with force)
        if active_bos_type == "BULL" and s.prev_active_pivot_high is not None:
            failure_dist = (s.prev_active_pivot_high - c) / atr
            if failure_dist >= cfg.failure_strong_atr and candle_dir < 0:
                bear_fail = 8
                state = "FAILED"
                stage = 0
            elif failure_dist >= cfg.failure_min_atr and candle_dir < 0:
                bear_fail = 4

        # Failure of a bearish break
        if active_bos_type == "BEAR" and s.prev_active_pivot_low is not None:
            failure_dist = (c - s.prev_active_pivot_low) / atr
            if failure_dist >= cfg.failure_strong_atr and candle_dir > 0:
                bull_fail = 8
                state = "FAILED"
                stage = 0
            elif failure_dist >= cfg.failure_min_atr and candle_dir > 0:
                bull_fail = 4

    bull_fail = min(bull_fail, 8)
    bear_fail = min(bear_fail, 8)

    # ==================================================
    # FINAL SCORE
    # ==================================================
    bull_total = min(
        bull_bos + bull_disp + bull_vol + bull_retest + bull_fail, 80
    )
    bear_total = min(
        bear_bos + bear_disp + bear_vol + bear_retest + bear_fail, 80
    )

    net = bull_total - bear_total

    return BreakoutOutput(
        breakout_net_score=net,
        bull_score=bull_total,
        bear_score=bear_total,
        breakout_stage=stage,
        breakout_state=state
    )


def execute_breakout_engine_from_packet(
    packet: FeaturePacket,
    cfg: BreakoutConfig
) -> BreakoutExecutionResult:
    """
    Execute Breakout Engine from a FeaturePacket.
    """
    if packet is None or not packet.valid or packet.features is None:
        return BreakoutExecutionResult(
            tf=packet.tf if packet else "",
            output=BreakoutOutput()
        )

    output = breakout_engine(packet.features, packet.regime, cfg)

    return BreakoutExecutionResult(
        tf=packet.tf,
        features=packet.features,
        regime=packet.regime,
        output=output
    )