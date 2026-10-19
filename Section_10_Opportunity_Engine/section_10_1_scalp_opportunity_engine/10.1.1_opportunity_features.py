# ======================================================
# SECTION 10: OPPORTUNITY ENGINE
# 10.1 SCALP OPPORTUNITY ENGINE
# Opportunity Features
# ======================================================

from dataclasses import dataclass
from typing import Optional

from import_features_packet import FeaturePacket

# ------------------------------------------------------
# FAMILY IDS
# ------------------------------------------------------

FAMILY_LIQUIDITY = 0
FAMILY_ORDER_BLOCK = 1
FAMILY_BREAKER = 2
FAMILY_VOLUME_PROFILE = 3
FAMILY_SWINGHL = 4
FAMILY_SESSIONHL = 5
FAMILY_EMA = 6
FAMILY_VWAP = 7
FAMILY_WMA = 8
FAMILY_PROTECTEDHL = 9
FAMILY_FIBONACCI = 10
FAMILY_SR = 11
FAMILY_FVG = 12
FAMILY_HLVN = 13


# ------------------------------------------------------
# OPPORTUNITY SCORE WEIGHTS
# Fixed spatial allocation — no quality modifiers
# ------------------------------------------------------

OP_SCORE_LIQUIDITY = 15.0
OP_SCORE_ORDER_BLOCK = 10.0
OP_SCORE_BREAKER = 8.0
OP_SCORE_VOLUME_PROFILE = 7.5
OP_SCORE_SWINGHL = 6.0
OP_SCORE_SESSIONHL = 3.0
OP_SCORE_EMA = 3.0
OP_SCORE_VWAP = 5.0
OP_SCORE_WMA = 1.0
OP_SCORE_PROTECTEDHL = 6.0
OP_SCORE_FIBONACCI = 3.0
OP_SCORE_SR = 15.0
OP_SCORE_FVG = 10.0
OP_SCORE_HLVN = 7.5
OP_SCORE_TOTAL = 100.0


# ------------------------------------------------------
# 10.1 INTERNAL OUTPUT
#
# This is NOT the final UI packet.
# It is the internal result consumed by the next
# Opportunity Engine stage.
# ------------------------------------------------------

@dataclass
class OpportunityFeatures:
    # ------------------------------
    # S/R
    # ------------------------------
    support_opportunity_score: float = 0.0
    resistance_opportunity_score: float = 0.0

    nearest_support_zone_low: Optional[float] = None
    nearest_support_zone_high: Optional[float] = None
    nearest_support_zone_bar: Optional[int] = None

    nearest_resistance_zone_low: Optional[float] = None
    nearest_resistance_zone_high: Optional[float] = None
    nearest_resistance_zone_bar: Optional[int] = None

    sr_buy_positive_distance: Optional[float] = None
    sr_sell_positive_distance: Optional[float] = None

    # ------------------------------
    # Liquidity
    # ------------------------------
    liquidity_buy_opportunity_score: Optional[float] = None
    liquidity_sell_opportunity_score: Optional[float] = None

    # ------------------------------
    # Volume Profile
    # ------------------------------
    vp_buy_opportunity_score: float = 0.0
    vp_sell_opportunity_score: float = 0.0

    vp_buy_poc_score: float = 0.0
    vp_buy_vah_score: float = 0.0
    vp_buy_val_score: float = 0.0

    vp_sell_poc_score: float = 0.0
    vp_sell_vah_score: float = 0.0
    vp_sell_val_score: float = 0.0

    vp_buy_hvn_score: float = 0.0
    vp_sell_hvn_score: float = 0.0

    vp_sell_lvn_score: float = 0.0
    vp_buy_lvn_score: float = 0.0

    max_distance_to_poc: Optional[float] = None
    max_distance_to_vah: Optional[float] = None
    max_distance_to_val: Optional[float] = None

    # ------------------------------
    # FVG
    # ------------------------------
    fvg_buy_opportunity_score: float = 0.0
    fvg_sell_opportunity_score: float = 0.0

    fvg_buy_positive_distance: Optional[float] = None
    fvg_sell_positive_distance: Optional[float] = None

    # ------------------------------
    # Order Block
    # ------------------------------
    ob_opportunity_max_age: int = 50

    ob_buy_opportunity_score: float = 0.0
    ob_sell_opportunity_score: float = 0.0

    # ------------------------------
    # Breaker
    # ------------------------------
    breaker_opportunity_max_age: int = 50

    breaker_buy_opportunity_score: float = 0.0
    breaker_sell_opportunity_score: float = 0.0

    # ------------------------------
    # Protected H/L
    # ------------------------------
    phl_buy_opportunity_score: float = 0.0
    phl_sell_opportunity_score: float = 0.0

    # ------------------------------
    # Session H/L
    # ------------------------------
    shl_buy_opportunity_score: float = 0.0
    shl_sell_opportunity_score: float = 0.0

    max_session_high_distance: float = 0.0
    max_session_low_distance: float = 0.0

    # ------------------------------
    # Swing H/L
    # ------------------------------
    swing_buy_opportunity_score: float = 0.0
    swing_sell_opportunity_score: float = 0.0

    swing_confluence_tolerance: float = 0.0
    swing_high_confluence_count: int = 0
    swing_low_confluence_count: int = 0

    # ------------------------------
    # Fibonacci
    # ------------------------------
    fib_buy_opportunity_score: float = 0.0
    fib_sell_opportunity_score: float = 0.0

    max_fib_level_distance: Optional[float] = None

    # ------------------------------
    # VWAP
    # ------------------------------
    vwap_buy_opportunity_score: float = 0.0
    vwap_sell_opportunity_score: float = 0.0

    # ------------------------------
    # EMA
    # ------------------------------
    ema_buy_opportunity_score: float = 0.0
    ema_sell_opportunity_score: float = 0.0

    # ------------------------------
    # WMA
    # ------------------------------
    wma_buy_opportunity_score: float = 0.0
    wma_sell_opportunity_score: float = 0.0


# ------------------------------------------------------
# SAFE HELPERS
# ------------------------------------------------------

def _safe(value, default=0.0):
    return default if value is None else value


def _distance_score(distance, maximum, score):
    """
    Preserves the supplied Pine calculation:

        min(score,
            (abs(distance) / maximum * score) >= score
            ? score
            : 0)

    Therefore this is effectively an all-or-nothing
    score when maximum > 0.
    """
    if distance is None or maximum is None:
        return 0.0

    if maximum <= 0:
        return 0.0

    calculated = abs(distance) / maximum * score

    return min(
        score,
        score if calculated >= score else 0.0
    )


# ======================================================
# 10.1 OPPORTUNITY FEATURES
# ======================================================

def calculate_opportunity_features(
    f: FeaturePacket,
    htf120: Optional[FeaturePacket] = None,
    htf240: Optional[FeaturePacket] = None,
    htf1d: Optional[FeaturePacket] = None,
    htf1w: Optional[FeaturePacket] = None,
) -> OpportunityFeatures:

    result = OpportunityFeatures()

    if f is None:
        return result

    # --------------------------------------------------
    # CURRENT PRICE / ATR
    # --------------------------------------------------

    c = _safe(getattr(f, "c", None))

    if getattr(f, "context", None) is not None:
        c = _safe(getattr(f.context, "c", c))

    # ==================================================
    # 10.1.1 SUPPORT AND RESISTANCE
    # ==================================================

    support_price = getattr(f, "nearestSupportZonePrice", None)
    resistance_price = getattr(f, "nearestResistanceZonePrice", None)

    # Python naming compatibility if MarketFeatures uses
    # snake_case instead of the Pine-style names.
    if support_price is None:
        support_price = getattr(
            f,
            "nearest_support_zone_price",
            None
        )

    if resistance_price is None:
        resistance_price = getattr(
            f,
            "nearest_resistance_zone_price",
            None
        )

    if support_price is not None:
        result.sr_sell_positive_distance = c - support_price

    if resistance_price is not None:
        result.sr_buy_positive_distance = resistance_price - c

    support_zone_id = getattr(
        f,
        "nearestSupportZonePriceID",
        None
    )

    if support_zone_id is None:
        support_zone_id = getattr(
            f,
            "nearest_support_zone_price_id",
            None
        )

    resistance_zone_id = getattr(
        f,
        "nearestResistanceZonePriceID",
        None
    )

    if resistance_zone_id is None:
        resistance_zone_id = getattr(
            f,
            "nearest_resistance_zone_price_id",
            None
        )

    # Arrays are expected to remain part of the existing
    # MarketFeatures structure.
    support_ids = getattr(
        f,
        "supportZoneIDArray",
        None
    )

    if support_ids is None:
        support_ids = getattr(
            f,
            "support_zone_id_array",
            None
        )

    support_lows = getattr(
        f,
        "supportLowArray",
        None
    )

    if support_lows is None:
        support_lows = getattr(
            f,
            "support_low_array",
            None
        )

    support_highs = getattr(
        f,
        "supportHighArray",
        None
    )

    if support_highs is None:
        support_highs = getattr(
            f,
            "support_high_array",
            None
        )

    support_bars = getattr(
        f,
        "supportBarArray",
        None
    )

    if support_bars is None:
        support_bars = getattr(
            f,
            "support_bar_array",
            None
        )

    resistance_ids = getattr(
        f,
        "resistanceZoneIDArray",
        None
    )

    if resistance_ids is None:
        resistance_ids = getattr(
            f,
            "resistance_zone_id_array",
            None
        )

    resistance_lows = getattr(
        f,
        "resistanceLowArray",
        None
    )

    if resistance_lows is None:
        resistance_lows = getattr(
            f,
            "resistance_low_array",
            None
        )

    resistance_highs = getattr(
        f,
        "resistanceHighArray",
        None
    )

    if resistance_highs is None:
        resistance_highs = getattr(
            f,
            "resistance_high_array",
            None
        )

    resistance_bars = getattr(
        f,
        "resistanceBarArray",
        None
    )

    if resistance_bars is None:
        resistance_bars = getattr(
            f,
            "resistance_bar_array",
            None
        )

    # Support zone lookup.
    if (
        support_zone_id is not None
        and support_ids is not None
    ):
        try:
            support_zone_index = support_ids.index(
                support_zone_id
            )
        except ValueError:
            support_zone_index = -1

        if support_zone_index >= 0:
            result.nearest_support_zone_low = (
                support_lows[support_zone_index]
                if support_lows is not None
                else None
            )

            result.nearest_support_zone_high = (
                support_highs[support_zone_index]
                if support_highs is not None
                else None
            )

            result.nearest_support_zone_bar = (
                support_bars[support_zone_index]
                if support_bars is not None
                else None
            )

            result.support_opportunity_score = 15.0

    # Resistance zone lookup.
    if (
        resistance_zone_id is not None
        and resistance_ids is not None
    ):
        try:
            resistance_zone_index = resistance_ids.index(
                resistance_zone_id
            )
        except ValueError:
            resistance_zone_index = -1

        if resistance_zone_index >= 0:
            result.nearest_resistance_zone_low = (
                resistance_lows[resistance_zone_index]
                if resistance_lows is not None
                else None
            )

            result.nearest_resistance_zone_high = (
                resistance_highs[resistance_zone_index]
                if resistance_highs is not None
                else None
            )

            result.nearest_resistance_zone_bar = (
                resistance_bars[resistance_zone_index]
                if resistance_bars is not None
                else None
            )

            result.resistance_opportunity_score = 15.0

    # ==================================================
    # 10.1.2 LIQUIDITY OPPORTUNITY
    # ==================================================

    nearest_buy_liquidity = getattr(
        f,
        "nearestBuyLiquidityPrice",
        None
    )

    if nearest_buy_liquidity is None:
        nearest_buy_liquidity = getattr(
            f,
            "nearest_buy_liquidity_price",
            None
        )

    nearest_sell_liquidity = getattr(
        f,
        "nearestSellLiquidityPrice",
        None
    )

    if nearest_sell_liquidity is None:
        nearest_sell_liquidity = getattr(
            f,
            "nearest_sell_liquidity_price",
            None
        )

    external_high = getattr(
        f,
        "externalHighLiquidity",
        None
    )

    if external_high is None:
        external_high = getattr(
            f,
            "external_high_liquidity",
            None
        )

    internal_high = getattr(
        f,
        "internalHighLiquidity",
        None
    )

    if internal_high is None:
        internal_high = getattr(
            f,
            "internal_high_liquidity",
            None
        )

    external_low = getattr(
        f,
        "externalLowLiquidity",
        None
    )

    if external_low is None:
        external_low = getattr(
            f,
            "external_low_liquidity",
            None
        )

    internal_low = getattr(
        f,
        "internalLowLiquidity",
        None
    )

    if internal_low is None:
        internal_low = getattr(
            f,
            "internal_low_liquidity",
            None
        )

    high_cluster = getattr(
        f,
        "highLiquidityCluster",
        False
    )

    equal_high = getattr(
        f,
        "equalHighLiquidity",
        False
    )

    bear_sweep = getattr(
        f,
        "bearSweepDetected",
        False
    )

    low_cluster = getattr(
        f,
        "lowLiquidityCluster",
        False
    )

    equal_low = getattr(
        f,
        "equalLowLiquidity",
        False
    )

    bull_sweep = getattr(
        f,
        "bullSweepDetected",
        False
    )

    # Buy side.
    if nearest_buy_liquidity is not None:

        if (
            external_high is not None
            and abs(
                nearest_buy_liquidity - external_high
            ) <= 0.000001
        ):

            if high_cluster:
                if equal_high:
                    result.liquidity_buy_opportunity_score = 15.0
                elif bear_sweep:
                    result.liquidity_buy_opportunity_score = 15.0
                else:
                    result.liquidity_buy_opportunity_score = 15.0
            else:
                result.liquidity_buy_opportunity_score = 15.0

        elif (
            internal_high is not None
            and abs(
                nearest_buy_liquidity - internal_high
            ) <= 0.000001
        ):

            if high_cluster:
                if equal_high:
                    result.liquidity_buy_opportunity_score = 15.0
                elif bear_sweep:
                    result.liquidity_buy_opportunity_score = 15.0
                else:
                    result.liquidity_buy_opportunity_score = 15.0
            else:
                result.liquidity_buy_opportunity_score = 15.0

    # Sell side.
    if nearest_sell_liquidity is not None:

        if (
            external_low is not None
            and abs(
                nearest_sell_liquidity - external_low
            ) <= 0.000001
        ):

            if low_cluster:
                if equal_low:
                    result.liquidity_sell_opportunity_score = 15.0
                elif bull_sweep:
                    result.liquidity_sell_opportunity_score = 15.0
                else:
                    result.liquidity_sell_opportunity_score = 15.0
            else:
                result.liquidity_sell_opportunity_score = 15.0

        elif (
            internal_low is not None
            and abs(
                nearest_sell_liquidity - internal_low
            ) <= 0.000001
        ):

            if low_cluster:
                if equal_low:
                    result.liquidity_sell_opportunity_score = 15.0
                elif bull_sweep:
                    result.liquidity_sell_opportunity_score = 15.0
                else:
                    result.liquidity_sell_opportunity_score = 15.0
            else:
                result.liquidity_sell_opportunity_score = 15.0

    # ==================================================
    # 10.1.3 VOLUME PROFILE
    # ==================================================

    vp_poc = getattr(f, "vpPOC", None)
    vp_val_low = getattr(f, "vpVALow", None)
    vp_val_high = getattr(f, "vpVAHigh", None)
    vp_hvn_low = getattr(f, "vpHVNLow", None)
    vp_hvn_high = getattr(f, "vpHVNHigh", None)
    vp_lvn_low = getattr(f, "vpLVNLow", None)
    vp_lvn_high = getattr(f, "vpLVNHigh", None)

    # Support snake_case if present.
    vp_poc = (
        vp_poc
        if vp_poc is not None
        else getattr(f, "vp_poc", None)
    )

    vp_val_low = (
        vp_val_low
        if vp_val_low is not None
        else getattr(f, "vp_val_low", None)
    )

    vp_val_high = (
        vp_val_high
        if vp_val_high is not None
        else getattr(f, "vp_val_high", None)
    )

    vp_hvn_low = (
        vp_hvn_low
        if vp_hvn_low is not None
        else getattr(f, "vp_hvn_low", None)
    )

    vp_hvn_high = (
        vp_hvn_high
        if vp_hvn_high is not None
        else getattr(f, "vp_hvn_high", None)
    )

    vp_lvn_low = (
        vp_lvn_low
        if vp_lvn_low is not None
        else getattr(f, "vp_lvn_low", None)
    )

    vp_lvn_high = (
        vp_lvn_high
        if vp_lvn_high is not None
        else getattr(f, "vp_lvn_high", None)
    )

    distance_to_poc = getattr(
        f,
        "distanceToPOC",
        getattr(f, "distance_to_poc", None)
    )

    distance_to_vah = getattr(
        f,
        "distanceToVAH",
        getattr(f, "distance_to_vah", None)
    )

    distance_to_val = getattr(
        f,
        "distanceToVAL",
        getattr(f, "distance_to_val", None)
    )

    result.max_distance_to_poc = distance_to_poc
    result.max_distance_to_vah = distance_to_vah
    result.max_distance_to_val = distance_to_val

    # BUY.
    if (
        vp_poc is not None
        and vp_val_low is not None
        and c < vp_poc
    ):
        if c >= vp_val_low:

            result.vp_buy_poc_score = _distance_score(
                distance_to_poc,
                distance_to_poc,
                7.5
            )

            result.vp_buy_vah_score = _distance_score(
                distance_to_vah,
                distance_to_vah,
                7.5
            )

    if vp_hvn_low is not None and c < vp_hvn_low:

        if (
            vp_lvn_low is not None
            and vp_lvn_high is not None
        ):
            if (
                c < vp_lvn_low
                and vp_lvn_high <= vp_hvn_low
            ):
                result.vp_buy_hvn_score = 7.5
            else:
                result.vp_buy_lvn_score = 7.5
        else:
            result.vp_buy_hvn_score = 7.5

    # SELL.
    if (
        vp_poc is not None
        and vp_val_low is not None
        and c > vp_poc
    ):
        if (
            vp_val_high is not None
            and c <= vp_val_high
        ):
            result.vp_sell_poc_score = _distance_score(
                distance_to_poc,
                distance_to_poc,
                7.5
            )

            result.vp_sell_val_score = _distance_score(
                distance_to_val,
                distance_to_val,
                7.5
            )

    if vp_hvn_high is not None and c > vp_hvn_high:

        if (
            vp_lvn_low is not None
            and vp_lvn_high is not None
        ):
            if (
                c > vp_lvn_high
                and vp_lvn_low >= vp_hvn_high
            ):
                result.vp_sell_hvn_score = 7.5
            else:
                result.vp_sell_lvn_score = 7.5
        else:
            result.vp_sell_hvn_score = 7.5

    result.vp_buy_opportunity_score = (
        result.vp_buy_poc_score
        + result.vp_buy_vah_score
        + result.vp_buy_val_score
        + result.vp_buy_hvn_score
        + result.vp_buy_lvn_score
    )

    result.vp_sell_opportunity_score = (
        result.vp_sell_poc_score
        + result.vp_sell_vah_score
        + result.vp_sell_val_score
        + result.vp_sell_hvn_score
        + result.vp_sell_lvn_score
    )

    # ==================================================
    # 10.1.4 FAIR VALUE GAP
    # ==================================================

    nearest_bear_fvg_low = getattr(
        f,
        "nearestBearFVGLow",
        getattr(f, "nearest_bear_fvg_low", None)
    )

    nearest_bull_fvg_high = getattr(
        f,
        "nearestBullFVGHigh",
        getattr(f, "nearest_bull_fvg_high", None)
    )

    if nearest_bear_fvg_low is not None:
        result.fvg_buy_positive_distance = (
            nearest_bear_fvg_low - c
        )

        if result.fvg_buy_positive_distance > 0:
            result.fvg_buy_opportunity_score = 10.0

    if nearest_bull_fvg_high is not None:
        result.fvg_sell_positive_distance = (
            c - nearest_bull_fvg_high
        )

        if result.fvg_sell_positive_distance > 0:
            result.fvg_sell_opportunity_score = 10.0

    # ==================================================
    # 10.1.5 ORDER BLOCK
    # ==================================================

    result.ob_opportunity_max_age = 50

    active_strict_bear_ob_low = getattr(
        f,
        "activeStrictBearOBLow",
        getattr(f, "active_strict_bear_ob_low", None)
    )

    active_bear_ob_low = getattr(
        f,
        "activeBearOBLow",
        getattr(f, "active_bear_ob_low", None)
    )

    active_strict_bull_ob_high = getattr(
        f,
        "activeStrictBullOBHigh",
        getattr(f, "active_strict_bull_ob_high", None)
    )

    active_bull_ob_high = getattr(
        f,
        "activeBullOBHigh",
        getattr(f, "active_bull_ob_high", None)
    )

    # BUY: strict bearish OB above.
    if (
        active_strict_bear_ob_low is not None
        and active_bear_ob_low is not None
        and active_strict_bear_ob_low > c
        and active_bear_ob_low > c
    ):
        if active_strict_bear_ob_low <= active_bear_ob_low:
            result.ob_buy_opportunity_score = 10.0
        else:
            result.ob_buy_opportunity_score = 10.0

    elif (
        active_strict_bear_ob_low is not None
        and active_strict_bear_ob_low > c
    ):
        result.ob_buy_opportunity_score = 10.0

    elif (
        active_bear_ob_low is not None
        and active_bear_ob_low > c
    ):
        result.ob_buy_opportunity_score = 10.0

    # SELL: strict bullish OB below.
    if (
        active_strict_bull_ob_high is not None
        and active_bull_ob_high is not None
        and active_strict_bull_ob_high < c
        and active_bull_ob_high < c
    ):
        if active_strict_bull_ob_high >= active_bull_ob_high:
            result.ob_sell_opportunity_score = 10.0
        else:
            result.ob_sell_opportunity_score = 10.0

    elif (
        active_strict_bull_ob_high is not None
        and active_strict_bull_ob_high < c
    ):
        result.ob_sell_opportunity_score = 10.0

    elif (
        active_bull_ob_high is not None
        and active_bull_ob_high < c
    ):
        result.ob_sell_opportunity_score = 10.0

    # ==================================================
    # 10.1.6 BREAKER
    # ==================================================

    result.breaker_opportunity_max_age = 50

    strict_bear_breaker_low = getattr(
        f,
        "strictBearBreakerLow",
        getattr(f, "strict_bear_breaker_low", None)
    )

    bear_breaker_low = getattr(
        f,
        "bearBreakerLow",
        getattr(f, "bear_breaker_low", None)
    )

    strict_bull_breaker_high = getattr(
        f,
        "strictBullBreakerHigh",
        getattr(f, "strict_bull_breaker_high", None)
    )

    bull_breaker_high = getattr(
        f,
        "bullBreakerHigh",
        getattr(f, "bull_breaker_high", None)
    )

    # BUY.
    if (
        strict_bear_breaker_low is not None
        and bear_breaker_low is not None
        and strict_bear_breaker_low > c
        and bear_breaker_low > c
    ):
        if strict_bear_breaker_low <= bear_breaker_low:
            result.breaker_buy_opportunity_score = 8.0
        elif bear_breaker_low < strict_bear_breaker_low:
            result.breaker_buy_opportunity_score = 8.0

    elif (
        strict_bear_breaker_low is not None
        and strict_bear_breaker_low > c
    ):
        result.breaker_buy_opportunity_score = 8.0

    elif (
        bear_breaker_low is not None
        and bear_breaker_low > c
    ):
        result.breaker_buy_opportunity_score = 8.0

    # SELL.
    if (
        strict_bull_breaker_high is not None
        and bull_breaker_high is not None
        and strict_bull_breaker_high < c
        and bull_breaker_high < c
    ):
        if strict_bull_breaker_high >= bull_breaker_high:
            result.breaker_sell_opportunity_score = 8.0
        elif bull_breaker_high > strict_bull_breaker_high:
            result.breaker_sell_opportunity_score = 8.0

    elif (
        strict_bull_breaker_high is not None
        and strict_bull_breaker_high < c
    ):
        result.breaker_sell_opportunity_score = 8.0

    elif (
        bull_breaker_high is not None
        and bull_breaker_high < c
    ):
        result.breaker_sell_opportunity_score = 8.0

    # ==================================================
    # 10.1.7 PROTECTED HIGH / LOW
    # ==================================================

    protected_high = getattr(
        f,
        "protectedHigh",
        getattr(f, "protected_high", None)
    )

    protected_low = getattr(
        f,
        "protectedLow",
        getattr(f, "protected_low", None)
    )

    protected_high_type = getattr(
        f,
        "protectedHighType",
        getattr(f, "protected_high_type", None)
    )

    protected_low_type = getattr(
        f,
        "protectedLowType",
        getattr(f, "protected_low_type", None)
    )

    active_transition_type = getattr(
        f,
        "activeTransitionType",
        getattr(f, "active_transition_type", None)
    )

    bullish_structure_active = getattr(
        f,
        "bullishStructureActive",
        getattr(f, "bullish_structure_active", False)
    )

    bearish_structure_active = getattr(
        f,
        "bearishStructureActive",
        getattr(f, "bearish_structure_active", False)
    )

    range_structure_active = getattr(
        f,
        "rangeStructureActive",
        getattr(f, "range_structure_active", False)
    )

    # Protected High.
    if protected_high is not None and c < protected_high:

        if (
            active_transition_type != "bullishTransition"
            and active_transition_type != "bearishTransition"
        ):

            if (
                bullish_structure_active
                and protected_high_type == "HH"
            ):
                result.phl_buy_opportunity_score = 6.0

            elif (
                range_structure_active
                and protected_high_type == "EH"
            ):
                result.phl_buy_opportunity_score = 6.0

            elif (
                bearish_structure_active
                and protected_high_type == "LH"
            ):
                result.phl_buy_opportunity_score = 6.0

        elif (
            active_transition_type == "bearishTransition"
            and active_transition_type != "bullishTransition"
        ):

            if (
                bearish_structure_active
                and protected_high_type == "LH"
            ):
                result.phl_buy_opportunity_score = 6.0

            elif (
                range_structure_active
                and protected_high_type == "EH"
            ):
                result.phl_buy_opportunity_score = 6.0

        elif (
            active_transition_type == "bullishTransition"
            and active_transition_type != "bearishTransition"
        ):

            if (
                bullish_structure_active
                and protected_high_type == "HH"
            ):
                result.phl_buy_opportunity_score = 6.0

            elif (
                range_structure_active
                and protected_high_type == "EH"
            ):
                result.phl_buy_opportunity_score = 6.0

    # Protected Low.
    if protected_low is not None and c > protected_low:

        if (
            active_transition_type != "bullishTransition"
            and active_transition_type != "bearishTransition"
        ):

            if (
                bearish_structure_active
                and protected_low_type == "LL"
            ):
                result.phl_sell_opportunity_score = 6.0

            elif (
                range_structure_active
                and protected_low_type == "EL"
            ):
                result.phl_sell_opportunity_score = 6.0

            elif (
                bullish_structure_active
                and protected_low_type == "HL"
            ):
                result.phl_sell_opportunity_score = 6.0

        elif (
            active_transition_type == "bullishTransition"
            and active_transition_type != "bearishTransition"
        ):

            if (
                bullish_structure_active
                and protected_low_type == "HL"
            ):
                result.phl_sell_opportunity_score = 6.0

            elif (
                range_structure_active
                and protected_low_type == "EL"
            ):
                result.phl_sell_opportunity_score = 6.0

        elif (
            active_transition_type == "bearishTransition"
            and active_transition_type != "bullishTransition"
        ):

            if (
                bearish_structure_active
                and protected_low_type == "LL"
            ):
                result.phl_sell_opportunity_score = 6.0

            elif (
                range_structure_active
                and protected_low_type == "EL"
            ):
                result.phl_sell_opportunity_score = 6.0

    # ==================================================
    # 10.1.8 SESSION HIGH / LOW
    # ==================================================

    nearest_high_price = getattr(
        f,
        "nearestHighPrice",
        getattr(f, "nearest_high_price", None)
    )

    nearest_low_price = getattr(
        f,
        "nearestLowPrice",
        getattr(f, "nearest_low_price", None)
    )

    nearest_high_distance = getattr(
        f,
        "nearestHighPriceDistance",
        getattr(f, "nearest_high_price_distance", None)
    )

    nearest_low_distance = getattr(
        f,
        "nearestLowPriceDistance",
        getattr(f, "nearest_low_price_distance", None)
    )

    if (
        nearest_high_price is not None
        and nearest_low_price is not None
    ):

        result.max_session_high_distance = _safe(
            nearest_high_distance
        )

        if (
            c < nearest_high_price
            and c < nearest_low_price
        ):
            result.shl_buy_opportunity_score = (
                _distance_score(
                    nearest_low_distance,
                    result.max_session_high_distance,
                    3.0
                )
            )

        elif (
            c < nearest_high_price
            and c > nearest_low_price
        ):
            result.shl_buy_opportunity_score = (
                _distance_score(
                    nearest_high_distance,
                    result.max_session_high_distance,
                    3.0
                )
            )

    if (
        nearest_high_price is not None
        and nearest_low_price is not None
    ):

        result.max_session_low_distance = _safe(
            nearest_low_distance
        )

        if (
            c > nearest_high_price
            and c > nearest_low_price
        ):
            result.shl_sell_opportunity_score = (
                _distance_score(
                    nearest_high_distance,
                    result.max_session_low_distance,
                    3.0
                )
            )

        elif (
            c < nearest_high_price
            and c > nearest_low_price
        ):
            result.shl_sell_opportunity_score = (
                _distance_score(
                    nearest_low_distance,
                    result.max_session_low_distance,
                    3.0
                )
            )

    # ==================================================
    # 10.1.9 SWING HIGH / LOW
    # ==================================================

    atr = _safe(
        getattr(
            f,
            "atr",
            getattr(
                getattr(f, "context", None),
                "atr",
                0.0
            )
        )
    )

    result.swing_confluence_tolerance = atr * 0.25

    nearest_swing_high = getattr(
        f,
        "nearestSwingHigh",
        getattr(f, "nearest_swing_high", None)
    )

    nearest_swing_low = getattr(
        f,
        "nearestSwingLow",
        getattr(f, "nearest_swing_low", None)
    )

    # BUY side.
    if (
        nearest_swing_high is not None
        and c < nearest_swing_high
    ):

        result.swing_high_confluence_count = 1

        if htf240 is not None:
            htf240_swing_high = getattr(
                htf240,
                "nearestSwingHigh",
                getattr(htf240, "nearest_swing_high", None)
            )

            if (
                htf240_swing_high is not None
                and abs(
                    nearest_swing_high
                    - htf240_swing_high
                ) <= result.swing_confluence_tolerance
            ):
                result.swing_high_confluence_count += 1

        if htf1d is not None:
            htf1d_swing_high = getattr(
                htf1d,
                "nearestSwingHigh",
                getattr(htf1d, "nearest_swing_high", None)
            )

            if (
                htf1d_swing_high is not None
                and abs(
                    nearest_swing_high
                    - htf1d_swing_high
                ) <= result.swing_confluence_tolerance
            ):
                result.swing_high_confluence_count += 1

        if htf1w is not None:
            htf1w_swing_high = getattr(
                htf1w,
                "nearestSwingHigh",
                getattr(htf1w, "nearest_swing_high", None)
            )

            if (
                htf1w_swing_high is not None
                and abs(
                    nearest_swing_high
                    - htf1w_swing_high
                ) <= result.swing_confluence_tolerance
            ):
                result.swing_high_confluence_count += 1

        # Exact supplied logic:
        # 1, 2, 3 and 4+ all receive 6.
        if result.swing_high_confluence_count >= 4:
            result.swing_buy_opportunity_score = 6.0

        elif result.swing_high_confluence_count == 3:
            result.swing_buy_opportunity_score = 6.0

        elif result.swing_high_confluence_count == 2:
            result.swing_buy_opportunity_score = 6.0

        elif result.swing_high_confluence_count == 1:
            result.swing_buy_opportunity_score = 6.0

    # SELL side.
    if (
        nearest_swing_low is not None
        and c > nearest_swing_low
    ):

        result.swing_low_confluence_count = 1

        if htf240 is not None:
            htf240_swing_low = getattr(
                htf240,
                "nearestSwingLow",
                getattr(htf240, "nearest_swing_low", None)
            )

            if (
                htf240_swing_low is not None
                and abs(
                    nearest_swing_low
                    - htf240_swing_low
                ) <= result.swing_confluence_tolerance
            ):
                result.swing_low_confluence_count += 1

        if htf1d is not None:
            htf1d_swing_low = getattr(
                htf1d,
                "nearestSwingLow",
                getattr(htf1d, "nearest_swing_low", None)
            )

            if (
                htf1d_swing_low is not None
                and abs(
                    nearest_swing_low
                    - htf1d_swing_low
                ) <= result.swing_confluence_tolerance
            ):
                result.swing_low_confluence_count += 1

        if htf1w is not None:
            htf1w_swing_low = getattr(
                htf1w,
                "nearestSwingLow",
                getattr(htf1w, "nearest_swing_low", None)
            )

            if (
                htf1w_swing_low is not None
                and abs(
                    nearest_swing_low
                    - htf1w_swing_low
                ) <= result.swing_confluence_tolerance
            ):
                result.swing_low_confluence_count += 1

        if result.swing_low_confluence_count >= 4:
            result.swing_sell_opportunity_score = 6.0

        elif result.swing_low_confluence_count == 3:
            result.swing_sell_opportunity_score = 4.5

        elif result.swing_low_confluence_count == 2:
            result.swing_sell_opportunity_score = 3.0

        elif result.swing_low_confluence_count == 1:
            result.swing_sell_opportunity_score = 1.5

    # ==================================================
    # 10.1.10 FIBONACCI
    # ==================================================

    nearest_fib_price = None
    nearest_fib_distance = None

    if htf240 is not None:
        nearest_fib_price = getattr(
            htf240,
            "nearestFibPrice",
            getattr(htf240, "nearest_fib_price", None)
        )

        nearest_fib_distance = getattr(
            htf240,
            "nearestFibDistance",
            getattr(htf240, "nearest_fib_distance", None)
        )

    result.max_fib_level_distance = nearest_fib_distance

    if nearest_fib_price is not None:

        if nearest_fib_price > c:
            result.fib_buy_opportunity_score = (
                _distance_score(
                    nearest_fib_distance,
                    result.max_fib_level_distance,
                    3.0
                )
            )

        if nearest_fib_price < c:
            result.fib_sell_opportunity_score = (
                _distance_score(
                    nearest_fib_distance,
                    result.max_fib_level_distance,
                    3.0
                )
            )

    # ==================================================
    # 10.1.11 VWAP
    # ==================================================

    nearest_buy_vwap = getattr(
        f,
        "nearestBuyVWAP",
        getattr(f, "nearest_buy_vwap", None)
    )

    nearest_sell_vwap = getattr(
        f,
        "nearestSellVWAP",
        getattr(f, "nearest_sell_vwap", None)
    )

    if (
        nearest_buy_vwap is not None
        and c < nearest_buy_vwap
    ):
        result.vwap_buy_opportunity_score = 5.0

    if (
        nearest_sell_vwap is not None
        and c > nearest_sell_vwap
    ):
        result.vwap_sell_opportunity_score = 5.0

    # ==================================================
    # 10.1.12 EMA
    # ==================================================

    nearest_buy_ema = getattr(
        f,
        "nearestBuyEMA",
        getattr(f, "nearest_buy_ema", None)
    )

    nearest_sell_ema = getattr(
        f,
        "nearestSellEMA",
        getattr(f, "nearest_sell_ema", None)
    )

    if (
        nearest_buy_ema is not None
        and nearest_buy_ema > c
    ):
        result.ema_buy_opportunity_score = 3.0

    if (
        nearest_sell_ema is not None
        and nearest_sell_ema < c
    ):
        result.ema_sell_opportunity_score = 3.0

    # ==================================================
    # 10.1.13 WMA
    # ==================================================

    wma50 = getattr(
        f,
        "wma50",
        None
    )

    if wma50 is not None:

        if wma50 > c:
            result.wma_buy_opportunity_score = 1.0

        if wma50 < c:
            result.wma_sell_opportunity_score = 1.0

    return result