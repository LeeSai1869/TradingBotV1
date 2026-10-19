from dataclasses import dataclass, field
from typing import Any, Optional, List


# ============================================================
# 10.1.3 OPPORTUNITY BASE LAYERS
# ============================================================

# ------------------------------------------------------------
# 3.1 ANCHOR INDEXES
# ------------------------------------------------------------

OP_ANCHOR_SR = 0
OP_ANCHOR_FVG = 1
OP_ANCHOR_OB = 2
OP_ANCHOR_BREAKER = 3
OP_ANCHOR_HVN = 4
OP_ANCHOR_LVN = 5
OP_ANCHOR_FIB0618 = 6
OP_ANCHOR_FIB0786 = 7

# Independent price references
OP_ANCHOR_PROTECTED = 8
OP_ANCHOR_SWING = 9
OP_ANCHOR_PREV_DAY = 10
OP_ANCHOR_SESSION = 11
OP_ANCHOR_EXT_LIQ = 12
OP_ANCHOR_INT_LIQ = 13
OP_ANCHOR_VWAP = 14
OP_ANCHOR_EMA = 15
OP_ANCHOR_WMA = 16
OP_ANCHOR_FIB_EXT = 17

# Higher-timeframe swing references
OP_ANCHOR_HTF120_SWING = 18
OP_ANCHOR_HTF240_SWING = 19
OP_ANCHOR_HTF1D_SWING = 20
OP_ANCHOR_HTF1W_SWING = 21

OP_ANCHOR_COUNT = 22

# Pseudo-zone ownership state
OP_ANCHOR_CONSUMED = -2
OP_ANCHOR_UNASSIGNED = -1

# IMPORTANT:
# The supplied Pine code actually writes 1 / 2 / 3 into the
# layer arrays, even though the comments describe 0 / 1 / 2.
# This implementation preserves the ACTUAL Pine assignments.
OP_BASE_LAYER_1 = 1
OP_BASE_LAYER_2 = 2
OP_BASE_LAYER_3 = 3


# ============================================================
# RESULT
# ============================================================

@dataclass
class OpportunityBaseLayersResult:
    """
    Internal result of 10.1.3 Opportunity Base Layers.

    This is NOT the final Scalp Opportunity Score Packet.

    It contains:
        - candidate anchor geometry
        - anchor ownership
        - spatially ordered anchors
        - Base Layer 1/2/3 anchor geometry
        - expanded layer extremes
    """

    opportunity_layer_gap: Optional[float] = None
    opportunity_cluster_gap: Optional[float] = None

    # --------------------------------------------------------
    # ABOVE ANCHOR CANDIDATES
    # --------------------------------------------------------

    opportunity_anchor_above_low: List[Optional[float]] = field(
        default_factory=lambda: [None] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_above_high: List[Optional[float]] = field(
        default_factory=lambda: [None] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_above_bar: List[Optional[int]] = field(
        default_factory=lambda: [None] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_above_valid: List[bool] = field(
        default_factory=lambda: [False] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_above_layer: List[int] = field(
        default_factory=lambda: [OP_ANCHOR_UNASSIGNED] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_above_is_zone: List[bool] = field(
        default_factory=lambda: [True] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_above_is_pseudo: List[bool] = field(
        default_factory=lambda: [False] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_above_reference_count: List[int] = field(
        default_factory=lambda: [1] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_above_pseudo_checked: List[bool] = field(
        default_factory=lambda: [False] * OP_ANCHOR_COUNT
    )

    # --------------------------------------------------------
    # BELOW ANCHOR CANDIDATES
    # --------------------------------------------------------

    opportunity_anchor_below_low: List[Optional[float]] = field(
        default_factory=lambda: [None] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_below_high: List[Optional[float]] = field(
        default_factory=lambda: [None] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_below_bar: List[Optional[int]] = field(
        default_factory=lambda: [None] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_below_valid: List[bool] = field(
        default_factory=lambda: [False] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_below_layer: List[int] = field(
        default_factory=lambda: [OP_ANCHOR_UNASSIGNED] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_below_is_zone: List[bool] = field(
        default_factory=lambda: [True] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_below_is_pseudo: List[bool] = field(
        default_factory=lambda: [False] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_below_reference_count: List[int] = field(
        default_factory=lambda: [1] * OP_ANCHOR_COUNT
    )
    opportunity_anchor_below_pseudo_checked: List[bool] = field(
        default_factory=lambda: [False] * OP_ANCHOR_COUNT
    )

    # --------------------------------------------------------
    # ORDERED ABOVE POSITIONS
    # --------------------------------------------------------

    opportunity_above_position_anchor: List[int] = field(
        default_factory=list
    )
    opportunity_above_position_low: List[Optional[float]] = field(
        default_factory=list
    )
    opportunity_above_position_high: List[Optional[float]] = field(
        default_factory=list
    )
    opportunity_above_position_bar: List[Optional[int]] = field(
        default_factory=list
    )
    opportunity_above_position_is_zone: List[bool] = field(
        default_factory=list
    )
    opportunity_above_position_is_pseudo: List[bool] = field(
        default_factory=list
    )
    opportunity_above_family_anchor: List[int] = field(
        default_factory=list
    )
    opportunity_above_position_price: List[Optional[float]] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # ORDERED BELOW POSITIONS
    # --------------------------------------------------------

    opportunity_below_position_anchor: List[int] = field(
        default_factory=list
    )
    opportunity_below_position_low: List[Optional[float]] = field(
        default_factory=list
    )
    opportunity_below_position_high: List[Optional[float]] = field(
        default_factory=list
    )
    opportunity_below_position_bar: List[Optional[int]] = field(
        default_factory=list
    )
    opportunity_below_position_is_zone: List[bool] = field(
        default_factory=list
    )
    opportunity_below_position_is_pseudo: List[bool] = field(
        default_factory=list
    )
    opportunity_below_family_anchor: List[int] = field(
        default_factory=list
    )
    opportunity_below_position_price: List[Optional[float]] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # ABOVE BASE LAYERS
    # --------------------------------------------------------

    opportunity_above_layer_anchor_low: List[float] = field(
        default_factory=list
    )
    opportunity_above_layer_anchor_high: List[float] = field(
        default_factory=list
    )
    opportunity_above_layer_extreme_low: List[float] = field(
        default_factory=list
    )
    opportunity_above_layer_extreme_high: List[float] = field(
        default_factory=list
    )
    opportunity_above_layer_anchor: List[int] = field(
        default_factory=list
    )

    # --------------------------------------------------------
    # BELOW BASE LAYERS
    # --------------------------------------------------------

    opportunity_below_layer_anchor_low: List[float] = field(
        default_factory=list
    )
    opportunity_below_layer_anchor_high: List[float] = field(
        default_factory=list
    )
    opportunity_below_layer_extreme_low: List[float] = field(
        default_factory=list
    )
    opportunity_below_layer_extreme_high: List[float] = field(
        default_factory=list
    )
    opportunity_below_layer_anchor: List[int] = field(
        default_factory=list
    )


# ============================================================
# HELPERS
# ============================================================

def _value(obj: Any, name: str, default=None):
    """
    Safe attribute access.

    This does not transform the Feature/MTF contract.
    It only prevents an absent optional attribute from crashing
    the entire opportunity stage.
    """
    return getattr(obj, name, default)


def _set_above(
    result: OpportunityBaseLayersResult,
    anchor: int,
    low,
    high,
    bar,
    is_zone: bool = True,
) -> None:
    result.opportunity_anchor_above_low[anchor] = low
    result.opportunity_anchor_above_high[anchor] = high
    result.opportunity_anchor_above_bar[anchor] = bar
    result.opportunity_anchor_above_valid[anchor] = True
    result.opportunity_anchor_above_is_zone[anchor] = is_zone


def _set_below(
    result: OpportunityBaseLayersResult,
    anchor: int,
    low,
    high,
    bar,
    is_zone: bool = True,
) -> None:
    result.opportunity_anchor_below_low[anchor] = low
    result.opportunity_anchor_below_high[anchor] = high
    result.opportunity_anchor_below_bar[anchor] = bar
    result.opportunity_anchor_below_valid[anchor] = True
    result.opportunity_anchor_below_is_zone[anchor] = is_zone


def _overlaps(
    candidate_low,
    candidate_high,
    extreme_low,
    extreme_high,
) -> bool:

    if candidate_low is None or candidate_high is None:
        return False

    if extreme_low is None or extreme_high is None:
        return False

    return (
        candidate_high >= extreme_low
        and candidate_low <= extreme_high
    )


# ============================================================
# MAIN 10.1.3 ENGINE
# ============================================================

def build_opportunity_base_layers(
    f: Any,
    htf120: Any,
    htf240: Any,
    htf1d: Any,
    htf1w: Any,
    *,
    nearest_resistance_zone_low=None,
    nearest_resistance_zone_high=None,
    nearest_resistance_zone_bar=None,
    nearest_support_zone_low=None,
    nearest_support_zone_high=None,
    nearest_support_zone_bar=None,
) -> OpportunityBaseLayersResult:

    result = OpportunityBaseLayersResult()

    c = _value(f, "c")
    atr = _value(f, "atr")

    # --------------------------------------------------------
    # 3.2 DISTANCE PARAMETERS
    # --------------------------------------------------------

    if atr is not None and atr > 0:
        result.opportunity_layer_gap = atr * 2.0
        result.opportunity_cluster_gap = atr * 1.0

    opportunity_cluster_gap = result.opportunity_cluster_gap

    # ========================================================
    # 3.3 ZONE ANCHOR CANDIDATE GEOMETRY
    # ========================================================

    # --------------------------------------------------------
    # SUPPORT / RESISTANCE
    # --------------------------------------------------------

    # Buy Side
    if (
        nearest_resistance_zone_low is not None
        and nearest_resistance_zone_high is not None
        and c < nearest_resistance_zone_low
    ):
        _set_above(
            result,
            OP_ANCHOR_SR,
            nearest_resistance_zone_low,
            nearest_resistance_zone_high,
            nearest_resistance_zone_bar,
            True,
        )

    # Sell Side
    if (
        nearest_support_zone_low is not None
        and nearest_support_zone_high is not None
        and c > nearest_support_zone_high
    ):
        _set_below(
            result,
            OP_ANCHOR_SR,
            nearest_support_zone_low,
            nearest_support_zone_high,
            nearest_support_zone_bar,
            True,
        )

    # --------------------------------------------------------
    # FVG
    # --------------------------------------------------------

    # Buy Side
    if (
        _value(f, "hasBearFVG", False)
        and _value(f, "nearestBearFVGLow") is not None
        and _value(f, "nearestBearFVGHigh") is not None
        and f.nearestBearFVGLow <= f.nearestBearFVGHigh
        and f.nearestBearFVGLow > c
    ):
        _set_above(
            result,
            OP_ANCHOR_FVG,
            f.nearestBearFVGLow,
            f.nearestBearFVGHigh,
            f.nearestBearFVGCreatedBar,
            True,
        )

    # Sell Side
    if (
        _value(f, "hasBullFVG", False)
        and _value(f, "nearestBullFVGLow") is not None
        and _value(f, "nearestBullFVGHigh") is not None
        and f.nearestBullFVGLow <= f.nearestBullFVGHigh
        and f.nearestBullFVGHigh < c
    ):
        _set_below(
            result,
            OP_ANCHOR_FVG,
            f.nearestBullFVGLow,
            f.nearestBullFVGHigh,
            f.nearestBullFVGCreatedBar,
            True,
        )

    # --------------------------------------------------------
    # ORDER BLOCK
    # --------------------------------------------------------

    strict_bear_low = _value(f, "activeStrictBearOBLow")
    strict_bear_high = _value(f, "activeStrictBearOBHigh")
    bear_low = _value(f, "activeBearOBLow")
    bear_high = _value(f, "activeBearOBHigh")

    # Buy Side
    if (
        strict_bear_low is not None
        and strict_bear_high is not None
        and bear_low is not None
        and bear_high is not None
        and strict_bear_low <= strict_bear_high
        and bear_low <= bear_high
        and strict_bear_low > c
        and bear_low > c
    ):
        if strict_bear_low <= bear_low:
            _set_above(
                result,
                OP_ANCHOR_OB,
                strict_bear_low,
                strict_bear_high,
                _value(f, "activeStrictBearOBBar"),
                True,
            )
        elif bear_low < strict_bear_low:
            _set_above(
                result,
                OP_ANCHOR_OB,
                bear_low,
                bear_high,
                _value(f, "activeBearOBBar"),
                True,
            )

    elif (
        strict_bear_low is not None
        and strict_bear_high is not None
        and strict_bear_low <= strict_bear_high
        and strict_bear_low > c
    ):
        _set_above(
            result,
            OP_ANCHOR_OB,
            strict_bear_low,
            strict_bear_high,
            _value(f, "activeStrictBearOBBar"),
            True,
        )

    elif (
        bear_low is not None
        and bear_high is not None
        and bear_low <= bear_high
        and bear_low > c
    ):
        _set_above(
            result,
            OP_ANCHOR_OB,
            bear_low,
            bear_high,
            _value(f, "activeBearOBBar"),
            True,
        )

    strict_bull_low = _value(f, "activeStrictBullOBLow")
    strict_bull_high = _value(f, "activeStrictBullOBHigh")
    bull_low = _value(f, "activeBullOBLow")
    bull_high = _value(f, "activeBullOBHigh")

    # Sell Side
    if (
        strict_bull_low is not None
        and strict_bull_high is not None
        and bull_low is not None
        and bull_high is not None
        and strict_bull_low <= strict_bull_high
        and bull_low <= bull_high
        and strict_bull_high < c
        and bull_high < c
    ):
        if strict_bull_high >= bull_high:
            _set_below(
                result,
                OP_ANCHOR_OB,
                strict_bull_low,
                strict_bull_high,
                _value(f, "activeStrictBullOBBar"),
                True,
            )
        elif bull_high > strict_bull_high:
            _set_below(
                result,
                OP_ANCHOR_OB,
                bull_low,
                bull_high,
                _value(f, "activeBullOBBar"),
                True,
            )

    elif (
        strict_bull_low is not None
        and strict_bull_high is not None
        and strict_bull_low <= strict_bull_high
        and strict_bull_high < c
    ):
        _set_below(
            result,
            OP_ANCHOR_OB,
            strict_bull_low,
            strict_bull_high,
            _value(f, "activeStrictBullOBBar"),
            True,
        )

    elif (
        bull_low is not None
        and bull_high is not None
        and bull_low <= bull_high
        and bull_high < c
    ):
        _set_below(
            result,
            OP_ANCHOR_OB,
            bull_low,
            bull_high,
            _value(f, "activeBullOBBar"),
            True,
        )

    # --------------------------------------------------------
    # BREAKER
    # --------------------------------------------------------

    strict_bear_breaker_low = _value(f, "strictBearBreakerLow")
    strict_bear_breaker_high = _value(f, "strictBearBreakerHigh")
    bear_breaker_low = _value(f, "bearBreakerLow")
    bear_breaker_high = _value(f, "bearBreakerHigh")

    # Buy Side
    if (
        strict_bear_breaker_low is not None
        and strict_bear_breaker_high is not None
        and bear_breaker_low is not None
        and bear_breaker_high is not None
        and strict_bear_breaker_low <= strict_bear_breaker_high
        and bear_breaker_low <= bear_breaker_high
        and strict_bear_breaker_low > c
        and bear_breaker_low > c
    ):
        if strict_bear_breaker_low <= bear_breaker_low:
            _set_above(
                result,
                OP_ANCHOR_BREAKER,
                strict_bear_breaker_low,
                strict_bear_breaker_high,
                None,
                True,
            )
        elif bear_breaker_low < strict_bear_breaker_low:
            _set_above(
                result,
                OP_ANCHOR_BREAKER,
                bear_breaker_low,
                bear_breaker_high,
                None,
                True,
            )

    elif (
        strict_bear_breaker_low is not None
        and strict_bear_breaker_high is not None
        and strict_bear_breaker_low <= strict_bear_breaker_high
        and strict_bear_breaker_low > c
    ):
        _set_above(
            result,
            OP_ANCHOR_BREAKER,
            strict_bear_breaker_low,
            strict_bear_breaker_high,
            None,
            True,
        )

    elif (
        bear_breaker_low is not None
        and bear_breaker_high is not None
        and bear_breaker_low <= bear_breaker_high
        and bear_breaker_low > c
    ):
        _set_above(
            result,
            OP_ANCHOR_BREAKER,
            bear_breaker_low,
            bear_breaker_high,
            None,
            True,
        )

    strict_bull_breaker_low = _value(f, "strictBullBreakerLow")
    strict_bull_breaker_high = _value(f, "strictBullBreakerHigh")
    bull_breaker_low = _value(f, "bullBreakerLow")
    bull_breaker_high = _value(f, "bullBreakerHigh")

    # Sell Side
    if (
        strict_bull_breaker_low is not None
        and strict_bull_breaker_high is not None
        and bull_breaker_low is not None
        and bull_breaker_high is not None
        and strict_bull_breaker_low <= strict_bull_breaker_high
        and bull_breaker_low <= bull_breaker_high
        and strict_bull_breaker_high < c
        and bull_breaker_high < c
    ):
        if strict_bull_breaker_high >= bull_breaker_high:
            _set_below(
                result,
                OP_ANCHOR_BREAKER,
                strict_bull_breaker_low,
                strict_bull_breaker_high,
                None,
                True,
            )
        elif bull_breaker_high > strict_bull_breaker_high:
            _set_below(
                result,
                OP_ANCHOR_BREAKER,
                bull_breaker_low,
                bull_breaker_high,
                None,
                True,
            )

    elif (
        strict_bull_breaker_low is not None
        and strict_bull_breaker_high is not None
        and strict_bull_breaker_low <= strict_bull_breaker_high
        and strict_bull_breaker_high < c
    ):
        _set_below(
            result,
            OP_ANCHOR_BREAKER,
            strict_bull_breaker_low,
            strict_bull_breaker_high,
            None,
            True,
        )

    elif (
        bull_breaker_low is not None
        and bull_breaker_high is not None
        and bull_breaker_low <= bull_breaker_high
        and bull_breaker_high < c
    ):
        _set_below(
            result,
            OP_ANCHOR_BREAKER,
            bull_breaker_low,
            bull_breaker_high,
            None,
            True,
        )

    # --------------------------------------------------------
    # HVN
    # --------------------------------------------------------

    hvn_low = _value(f, "vpHVNLow")
    hvn_high = _value(f, "vpHVNHigh")

    if (
        hvn_low is not None
        and hvn_high is not None
        and hvn_low <= hvn_high
        and hvn_low > c
    ):
        _set_above(
            result,
            OP_ANCHOR_HVN,
            hvn_low,
            hvn_high,
            None,
            True,
        )

    if (
        hvn_low is not None
        and hvn_high is not None
        and hvn_low <= hvn_high
        and hvn_high < c
    ):
        _set_below(
            result,
            OP_ANCHOR_HVN,
            hvn_low,
            hvn_high,
            None,
            True,
        )

    # --------------------------------------------------------
    # LVN
    # --------------------------------------------------------

    lvn_low = _value(f, "vpLVNLow")
    lvn_high = _value(f, "vpLVNHigh")

    if (
        lvn_low is not None
        and lvn_high is not None
        and lvn_low <= lvn_high
        and lvn_low > c
    ):
        _set_above(
            result,
            OP_ANCHOR_LVN,
            lvn_low,
            lvn_high,
            None,
            True,
        )

    if (
        lvn_low is not None
        and lvn_high is not None
        and lvn_low <= lvn_high
        and lvn_high < c
    ):
        _set_below(
            result,
            OP_ANCHOR_LVN,
            lvn_low,
            lvn_high,
            None,
            True,
        )

    # --------------------------------------------------------
    # FIB 0.500 - 0.618
    # --------------------------------------------------------

    fib050 = _value(f, "fib050Price")
    fib0618 = _value(f, "fib0618Price")

    if (
        fib050 is not None
        and fib0618 is not None
        and fib050 <= fib0618
        and fib050 > c
    ):
        _set_above(
            result,
            OP_ANCHOR_FIB0618,
            fib050,
            fib0618,
            None,
            True,
        )

    if (
        fib050 is not None
        and fib0618 is not None
        and fib050 <= fib0618
        and fib0618 < c
    ):
        _set_below(
            result,
            OP_ANCHOR_FIB0618,
            fib050,
            fib0618,
            None,
            True,
        )

    # --------------------------------------------------------
    # FIB 0.618 - 0.786
    # --------------------------------------------------------

    fib0786 = _value(f, "fib0786Price")

    if (
        fib0618 is not None
        and fib0786 is not None
        and fib0618 <= fib0786
        and fib0618 > c
    ):
        _set_above(
            result,
            OP_ANCHOR_FIB0786,
            fib0618,
            fib0786,
            None,
            True,
        )

    if (
        fib0618 is not None
        and fib0786 is not None
        and fib0618 <= fib0786
        and fib0786 < c
    ):
        _set_below(
            result,
            OP_ANCHOR_FIB0786,
            fib0618,
            fib0786,
            None,
            True,
        )

    # ========================================================
    # 3.4 INDEPENDENT PRICE ANCHOR CANDIDATES
    # ========================================================

    # --------------------------------------------------------
    # PROTECTED HIGH / LOW
    # --------------------------------------------------------

    protected_high = _value(f, "protectedHigh")
    protected_low = _value(f, "protectedLow")

    if protected_high is not None and protected_high > c:
        _set_above(
            result,
            OP_ANCHOR_PROTECTED,
            protected_high,
            protected_high,
            None,
            False,
        )

    if protected_low is not None and protected_low < c:
        _set_below(
            result,
            OP_ANCHOR_PROTECTED,
            protected_low,
            protected_low,
            None,
            False,
        )

    # --------------------------------------------------------
    # NEAREST SWING HIGH / LOW
    # --------------------------------------------------------

    nearest_swing_high = _value(f, "nearestSwingHigh")
    nearest_swing_low = _value(f, "nearestSwingLow")

    if nearest_swing_high is not None and nearest_swing_high > c:
        _set_above(
            result,
            OP_ANCHOR_SWING,
            nearest_swing_high,
            nearest_swing_high,
            None,
            False,
        )

    if nearest_swing_low is not None and nearest_swing_low < c:
        _set_below(
            result,
            OP_ANCHOR_SWING,
            nearest_swing_low,
            nearest_swing_low,
            None,
            False,
        )

    # --------------------------------------------------------
    # PREVIOUS DAY HIGH / LOW
    # --------------------------------------------------------

    previous_day_high = _value(f, "previousDayHigh")
    previous_day_low = _value(f, "previousDayLow")

    if previous_day_high is not None and previous_day_high > c:
        _set_above(
            result,
            OP_ANCHOR_PREV_DAY,
            previous_day_high,
            previous_day_high,
            None,
            False,
        )

    if previous_day_low is not None and previous_day_low < c:
        _set_below(
            result,
            OP_ANCHOR_PREV_DAY,
            previous_day_low,
            previous_day_low,
            None,
            False,
        )

    # --------------------------------------------------------
    # SESSION HIGH / LOW
    # --------------------------------------------------------

    nearest_high_price = _value(f, "nearestHighPrice")
    nearest_low_price = _value(f, "nearestLowPrice")

    if nearest_high_price is not None and nearest_high_price > c:
        _set_above(
            result,
            OP_ANCHOR_SESSION,
            nearest_high_price,
            nearest_high_price,
            None,
            False,
        )

    if nearest_low_price is not None and nearest_low_price < c:
        _set_below(
            result,
            OP_ANCHOR_SESSION,
            nearest_low_price,
            nearest_low_price,
            None,
            False,
        )

    # --------------------------------------------------------
    # EXTERNAL LIQUIDITY
    # --------------------------------------------------------

    external_high_liquidity = _value(f, "externalHighLiquidity")
    external_low_liquidity = _value(f, "externalLowLiquidity")

    if external_high_liquidity is not None and external_high_liquidity > c:
        _set_above(
            result,
            OP_ANCHOR_EXT_LIQ,
            external_high_liquidity,
            external_high_liquidity,
            None,
            False,
        )

    if external_low_liquidity is not None and external_low_liquidity < c:
        _set_below(
            result,
            OP_ANCHOR_EXT_LIQ,
            external_low_liquidity,
            external_low_liquidity,
            None,
            False,
        )

    # --------------------------------------------------------
    # INTERNAL LIQUIDITY
    # --------------------------------------------------------

    internal_high_liquidity = _value(f, "internalHighLiquidity")
    internal_low_liquidity = _value(f, "internalLowLiquidity")

    if internal_high_liquidity is not None and internal_high_liquidity > c:
        _set_above(
            result,
            OP_ANCHOR_INT_LIQ,
            internal_high_liquidity,
            internal_high_liquidity,
            None,
            False,
        )

    if internal_low_liquidity is not None and internal_low_liquidity < c:
        _set_below(
            result,
            OP_ANCHOR_INT_LIQ,
            internal_low_liquidity,
            internal_low_liquidity,
            None,
            False,
        )

    # --------------------------------------------------------
    # VWAP
    # --------------------------------------------------------

    nearest_buy_vwap = _value(f, "nearestBuyVWAP")
    nearest_sell_vwap = _value(f, "nearestSellVWAP")

    if nearest_buy_vwap is not None and nearest_buy_vwap > c:
        _set_above(
            result,
            OP_ANCHOR_VWAP,
            nearest_buy_vwap,
            nearest_buy_vwap,
            None,
            False,
        )

    if nearest_sell_vwap is not None and nearest_sell_vwap < c:
        _set_below(
            result,
            OP_ANCHOR_VWAP,
            nearest_sell_vwap,
            nearest_sell_vwap,
            None,
            False,
        )

    # --------------------------------------------------------
    # EMA
    # --------------------------------------------------------

    nearest_buy_ema = _value(f, "nearestBuyEMA")
    nearest_sell_ema = _value(f, "nearestSellEMA")

    if nearest_buy_ema is not None and nearest_buy_ema > c:
        _set_above(
            result,
            OP_ANCHOR_EMA,
            nearest_buy_ema,
            nearest_buy_ema,
            None,
            False,
        )

    if nearest_sell_ema is not None and nearest_sell_ema < c:
        _set_below(
            result,
            OP_ANCHOR_EMA,
            nearest_sell_ema,
            nearest_sell_ema,
            None,
            False,
        )

    # --------------------------------------------------------
    # WMA
    # --------------------------------------------------------

    wma50 = _value(f, "wma50")

    if wma50 is not None and wma50 > c:
        _set_above(
            result,
            OP_ANCHOR_WMA,
            wma50,
            wma50,
            None,
            False,
        )

    if wma50 is not None and wma50 < c:
        _set_below(
            result,
            OP_ANCHOR_WMA,
            wma50,
            wma50,
            None,
            False,
        )

    # --------------------------------------------------------
    # FIB EXTENSION ABOVE / BELOW
    # --------------------------------------------------------

    fib_extension_active = _value(
        htf240,
        "fibExtensionActive",
        False,
    )
    nearest_fib_extension_price = _value(
        htf240,
        "nearestFibExtensionPrice",
    )

    if (
        fib_extension_active
        and nearest_fib_extension_price is not None
        and nearest_fib_extension_price > c
    ):
        _set_above(
            result,
            OP_ANCHOR_FIB_EXT,
            nearest_fib_extension_price,
            nearest_fib_extension_price,
            None,
            False,
        )

    if (
        fib_extension_active
        and nearest_fib_extension_price is not None
        and nearest_fib_extension_price < c
    ):
        _set_below(
            result,
            OP_ANCHOR_FIB_EXT,
            nearest_fib_extension_price,
            nearest_fib_extension_price,
            None,
            False,
        )

    # ========================================================
    # 3.5 HTF INDEPENDENT PRICE ANCHOR CANDIDATES
    # ========================================================

    htf_swing_data = (
        (OP_ANCHOR_HTF120_SWING, htf120),
        (OP_ANCHOR_HTF240_SWING, htf240),
        (OP_ANCHOR_HTF1D_SWING, htf1d),
        (OP_ANCHOR_HTF1W_SWING, htf1w),
    )

    for anchor_id, htf in htf_swing_data:

        htf_swing_high = _value(htf, "nearestSwingHigh")
        htf_swing_low = _value(htf, "nearestSwingLow")

        # HTF swing high
        if htf_swing_high is not None and htf_swing_high > c:
            _set_above(
                result,
                anchor_id,
                htf_swing_high,
                htf_swing_high,
                None,
                False,
            )

        # HTF swing low
        if htf_swing_low is not None and htf_swing_low < c:
            _set_below(
                result,
                anchor_id,
                htf_swing_low,
                htf_swing_low,
                None,
                False,
            )

    # ========================================================
    # 10.1.4 ORDERED OPPORTUNITY ANCHOR POSITIONS
    # ========================================================

    # --------------------------------------------------------
    # ABOVE PRICE
    # --------------------------------------------------------

    # First gather the valid family anchors.
    #
    # The supplied Pine loop effectively gives each family
    # anchor one entry in the family-anchor list if valid.
    for family_index in range(OP_ANCHOR_COUNT):

        nearest_anchor = -1
        nearest_price = None

        for anchor_position_index in range(OP_ANCHOR_COUNT):

            valid = result.opportunity_anchor_above_valid[
                anchor_position_index
            ]

            assigned_layer = result.opportunity_anchor_above_layer[
                anchor_position_index
            ]

            candidate_price = result.opportunity_anchor_above_low[
                anchor_position_index
            ]

            # Consumed pseudo-zone members are excluded.
            if (
                valid
                and assigned_layer != OP_ANCHOR_CONSUMED
                and candidate_price is not None
            ):
                if anchor_position_index == family_index:
                    if (
                        nearest_price is None
                        or candidate_price < nearest_price
                    ):
                        nearest_price = candidate_price
                        nearest_anchor = anchor_position_index

        if nearest_anchor >= 0:
            result.opportunity_above_family_anchor.append(
                nearest_anchor
            )

    # --------------------------------------------------------
    # Order selected ABOVE family anchors by distance.
    #
    # Lowest price first = nearest to current price.
    # --------------------------------------------------------

    above_family_count = len(
        result.opportunity_above_family_anchor
    )

    for position in range(above_family_count):

        nearest_family_anchor = -1
        nearest_family_price = None

        for family_position in range(above_family_count):

            candidate_anchor = (
                result.opportunity_above_family_anchor[
                    family_position
                ]
            )

            already_selected = False

            if position > 0:
                for selected_position in range(position):
                    if (
                        result.opportunity_above_position_anchor[
                            selected_position
                        ]
                        == candidate_anchor
                    ):
                        already_selected = True
                        break

            if not already_selected:

                candidate_price = (
                    result.opportunity_anchor_above_low[
                        candidate_anchor
                    ]
                )

                if (
                    nearest_family_price is None
                    or candidate_price < nearest_family_price
                ):
                    nearest_family_price = candidate_price
                    nearest_family_anchor = candidate_anchor

        if nearest_family_anchor >= 0:

            result.opportunity_above_position_anchor.append(
                nearest_family_anchor
            )

            result.opportunity_above_position_low.append(
                result.opportunity_anchor_above_low[
                    nearest_family_anchor
                ]
            )

            result.opportunity_above_position_high.append(
                result.opportunity_anchor_above_high[
                    nearest_family_anchor
                ]
            )

            result.opportunity_above_position_bar.append(
                result.opportunity_anchor_above_bar[
                    nearest_family_anchor
                ]
            )

            result.opportunity_above_position_is_zone.append(
                result.opportunity_anchor_above_is_zone[
                    nearest_family_anchor
                ]
            )

            result.opportunity_above_position_is_pseudo.append(
                result.opportunity_anchor_above_is_pseudo[
                    nearest_family_anchor
                ]
            )

            if result.opportunity_anchor_above_is_zone[
                nearest_family_anchor
            ]:
                above_anchor_price = None
            else:
                above_anchor_price = (
                    result.opportunity_anchor_above_low[
                        nearest_family_anchor
                    ]
                )

            result.opportunity_above_position_price.append(
                above_anchor_price
            )

    # --------------------------------------------------------
    # BELOW PRICE
    # --------------------------------------------------------

    for family_index in range(OP_ANCHOR_COUNT):

        nearest_anchor = -1
        nearest_price = None

        for anchor_position_index in range(OP_ANCHOR_COUNT):

            valid = result.opportunity_anchor_below_valid[
                anchor_position_index
            ]

            assigned_layer = result.opportunity_anchor_below_layer[
                anchor_position_index
            ]

            candidate_price = result.opportunity_anchor_below_high[
                anchor_position_index
            ]

            if (
                valid
                and assigned_layer != OP_ANCHOR_CONSUMED
                and candidate_price is not None
            ):
                if anchor_position_index == family_index:
                    if (
                        nearest_price is None
                        or candidate_price > nearest_price
                    ):
                        nearest_price = candidate_price
                        nearest_anchor = anchor_position_index

        if nearest_anchor >= 0:
            result.opportunity_below_family_anchor.append(
                nearest_anchor
            )

    # --------------------------------------------------------
    # Order selected BELOW family anchors.
    #
    # Larger price first = nearest to current price.
    # --------------------------------------------------------

    below_family_count = len(
        result.opportunity_below_family_anchor
    )

    for position in range(below_family_count):

        nearest_family_anchor = -1
        nearest_family_price = None

        for family_position in range(below_family_count):

            candidate_anchor = (
                result.opportunity_below_family_anchor[
                    family_position
                ]
            )

            already_selected = False

            if position > 0:
                for selected_position in range(position):
                    if (
                        result.opportunity_below_position_anchor[
                            selected_position
                        ]
                        == candidate_anchor
                    ):
                        already_selected = True
                        break

            if not already_selected:

                candidate_price = (
                    result.opportunity_anchor_below_high[
                        candidate_anchor
                    ]
                )

                if (
                    nearest_family_price is None
                    or candidate_price > nearest_family_price
                ):
                    nearest_family_price = candidate_price
                    nearest_family_anchor = candidate_anchor

        if nearest_family_anchor >= 0:

            result.opportunity_below_position_anchor.append(
                nearest_family_anchor
            )

            result.opportunity_below_position_low.append(
                result.opportunity_anchor_below_low[
                    nearest_family_anchor
                ]
            )

            result.opportunity_below_position_high.append(
                result.opportunity_anchor_below_high[
                    nearest_family_anchor
                ]
            )

            result.opportunity_below_position_bar.append(
                result.opportunity_anchor_below_bar[
                    nearest_family_anchor
                ]
            )

            result.opportunity_below_position_is_zone.append(
                result.opportunity_anchor_below_is_zone[
                    nearest_family_anchor
                ]
            )

            result.opportunity_below_position_is_pseudo.append(
                result.opportunity_anchor_below_is_pseudo[
                    nearest_family_anchor
                ]
            )

            if result.opportunity_anchor_below_is_zone[
                nearest_family_anchor
            ]:
                below_anchor_price = None
            else:
                below_anchor_price = (
                    result.opportunity_anchor_below_high[
                        nearest_family_anchor
                    ]
                )

            result.opportunity_below_position_price.append(
                below_anchor_price
            )

    # ========================================================
    # 10.1.5 ZONE LAYERS
    # ========================================================

    # ========================================================
    # ABOVE PRICE — LAYER 1
    # ========================================================

    above_layer1_anchor = -1

    above_position_count = len(
        result.opportunity_above_position_anchor
    )

    if above_position_count > 0:

        for position in range(above_position_count):

            candidate_anchor = (
                result.opportunity_above_position_anchor[position]
            )

            candidate_valid = (
                result.opportunity_anchor_above_valid[
                    candidate_anchor
                ]
            )

            candidate_layer = (
                result.opportunity_anchor_above_layer[
                    candidate_anchor
                ]
            )

            candidate_is_zone = (
                result.opportunity_anchor_above_is_zone[
                    candidate_anchor
                ]
            )

            if (
                candidate_valid
                and candidate_layer == OP_ANCHOR_UNASSIGNED
                and candidate_is_zone
            ):
                above_layer1_anchor = candidate_anchor
                break

    if above_layer1_anchor >= 0:

        layer_anchor_low = (
            result.opportunity_anchor_above_low[
                above_layer1_anchor
            ]
        )

        layer_anchor_high = (
            result.opportunity_anchor_above_high[
                above_layer1_anchor
            ]
        )

        if (
            layer_anchor_low is not None
            and layer_anchor_high is not None
            and opportunity_cluster_gap is not None
        ):

            result.opportunity_above_layer_anchor_low.append(
                layer_anchor_low
            )
            result.opportunity_above_layer_anchor_high.append(
                layer_anchor_high
            )
            result.opportunity_above_layer_anchor.append(
                above_layer1_anchor
            )

            layer_extreme_low = (
                layer_anchor_low - opportunity_cluster_gap
            )

            layer_extreme_high = (
                layer_anchor_high + opportunity_cluster_gap
            )

            for anchor_index in range(OP_ANCHOR_COUNT):

                anchor_valid = (
                    result.opportunity_anchor_above_valid[
                        anchor_index
                    ]
                )

                anchor_layer = (
                    result.opportunity_anchor_above_layer[
                        anchor_index
                    ]
                )

                if (
                    anchor_valid
                    and anchor_layer == OP_ANCHOR_UNASSIGNED
                ):

                    candidate_low = (
                        result.opportunity_anchor_above_low[
                            anchor_index
                        ]
                    )

                    candidate_high = (
                        result.opportunity_anchor_above_high[
                            anchor_index
                        ]
                    )

                    if _overlaps(
                        candidate_low,
                        candidate_high,
                        layer_extreme_low,
                        layer_extreme_high,
                    ):

                        result.opportunity_anchor_above_layer[
                            anchor_index
                        ] = OP_BASE_LAYER_1

                        layer_extreme_low = min(
                            layer_extreme_low,
                            candidate_low,
                        )

                        layer_extreme_high = max(
                            layer_extreme_high,
                            candidate_high,
                        )

            result.opportunity_above_layer_extreme_low.append(
                layer_extreme_low
            )
            result.opportunity_above_layer_extreme_high.append(
                layer_extreme_high
            )

    # ========================================================
    # ABOVE PRICE — LAYER 2
    # ========================================================

    above_layer2_anchor = -1

    if above_position_count > 0:

        for position in range(above_position_count):

            candidate_anchor = (
                result.opportunity_above_position_anchor[position]
            )

            candidate_valid = (
                result.opportunity_anchor_above_valid[
                    candidate_anchor
                ]
            )

            candidate_layer = (
                result.opportunity_anchor_above_layer[
                    candidate_anchor
                ]
            )

            candidate_is_zone = (
                result.opportunity_anchor_above_is_zone[
                    candidate_anchor
                ]
            )

            if (
                candidate_valid
                and candidate_layer == OP_ANCHOR_UNASSIGNED
                and candidate_is_zone
            ):
                above_layer2_anchor = candidate_anchor
                break

    if above_layer2_anchor >= 0:

        layer_anchor_low = (
            result.opportunity_anchor_above_low[
                above_layer2_anchor
            ]
        )

        layer_anchor_high = (
            result.opportunity_anchor_above_high[
                above_layer2_anchor
            ]
        )

        if (
            layer_anchor_low is not None
            and layer_anchor_high is not None
            and opportunity_cluster_gap is not None
        ):

            result.opportunity_above_layer_anchor_low.append(
                layer_anchor_low
            )
            result.opportunity_above_layer_anchor_high.append(
                layer_anchor_high
            )
            result.opportunity_above_layer_anchor.append(
                above_layer2_anchor
            )

            layer_extreme_low = (
                layer_anchor_low - opportunity_cluster_gap
            )

            layer_extreme_high = (
                layer_anchor_high + opportunity_cluster_gap
            )

            for anchor_index in range(OP_ANCHOR_COUNT):

                anchor_valid = (
                    result.opportunity_anchor_above_valid[
                        anchor_index
                    ]
                )

                anchor_layer = (
                    result.opportunity_anchor_above_layer[
                        anchor_index
                    ]
                )

                if (
                    anchor_valid
                    and anchor_layer == OP_ANCHOR_UNASSIGNED
                ):

                    candidate_low = (
                        result.opportunity_anchor_above_low[
                            anchor_index
                        ]
                    )

                    candidate_high = (
                        result.opportunity_anchor_above_high[
                            anchor_index
                        ]
                    )

                    if _overlaps(
                        candidate_low,
                        candidate_high,
                        layer_extreme_low,
                        layer_extreme_high,
                    ):

                        result.opportunity_anchor_above_layer[
                            anchor_index
                        ] = OP_BASE_LAYER_2

                        layer_extreme_low = min(
                            layer_extreme_low,
                            candidate_low,
                        )

                        layer_extreme_high = max(
                            layer_extreme_high,
                            candidate_high,
                        )

            result.opportunity_above_layer_extreme_low.append(
                layer_extreme_low
            )
            result.opportunity_above_layer_extreme_high.append(
                layer_extreme_high
            )

    # ========================================================
    # ABOVE PRICE — LAYER 3
    # ========================================================

    above_layer3_anchor = -1

    if above_position_count > 0:

        for position in range(above_position_count):

            candidate_anchor = (
                result.opportunity_above_position_anchor[position]
            )

            candidate_valid = (
                result.opportunity_anchor_above_valid[
                    candidate_anchor
                ]
            )

            candidate_layer = (
                result.opportunity_anchor_above_layer[
                    candidate_anchor
                ]
            )

            candidate_is_zone = (
                result.opportunity_anchor_above_is_zone[
                    candidate_anchor
                ]
            )

            if (
                candidate_valid
                and candidate_layer == OP_ANCHOR_UNASSIGNED
                and candidate_is_zone
            ):
                above_layer3_anchor = candidate_anchor
                break

    if above_layer3_anchor >= 0:

        layer_anchor_low = (
            result.opportunity_anchor_above_low[
                above_layer3_anchor
            ]
        )

        layer_anchor_high = (
            result.opportunity_anchor_above_high[
                above_layer3_anchor
            ]
        )

        if (
            layer_anchor_low is not None
            and layer_anchor_high is not None
            and opportunity_cluster_gap is not None
        ):

            result.opportunity_above_layer_anchor_low.append(
                layer_anchor_low
            )
            result.opportunity_above_layer_anchor_high.append(
                layer_anchor_high
            )
            result.opportunity_above_layer_anchor.append(
                above_layer3_anchor
            )

            layer_extreme_low = (
                layer_anchor_low - opportunity_cluster_gap
            )

            layer_extreme_high = (
                layer_anchor_high + opportunity_cluster_gap
            )

            for anchor_index in range(OP_ANCHOR_COUNT):

                anchor_valid = (
                    result.opportunity_anchor_above_valid[
                        anchor_index
                    ]
                )

                anchor_layer = (
                    result.opportunity_anchor_above_layer[
                        anchor_index
                    ]
                )

                if (
                    anchor_valid
                    and anchor_layer == OP_ANCHOR_UNASSIGNED
                ):

                    candidate_low = (
                        result.opportunity_anchor_above_low[
                            anchor_index
                        ]
                    )

                    candidate_high = (
                        result.opportunity_anchor_above_high[
                            anchor_index
                        ]
                    )

                    if _overlaps(
                        candidate_low,
                        candidate_high,
                        layer_extreme_low,
                        layer_extreme_high,
                    ):

                        result.opportunity_anchor_above_layer[
                            anchor_index
                        ] = OP_BASE_LAYER_3

                        layer_extreme_low = min(
                            layer_extreme_low,
                            candidate_low,
                        )

                        layer_extreme_high = max(
                            layer_extreme_high,
                            candidate_high,
                        )

            result.opportunity_above_layer_extreme_low.append(
                layer_extreme_low
            )
            result.opportunity_above_layer_extreme_high.append(
                layer_extreme_high
            )

    # ========================================================
    # BELOW PRICE — LAYER 1
    # ========================================================

    below_layer1_anchor = -1

    below_position_count = len(
        result.opportunity_below_position_anchor
    )

    if below_position_count > 0:

        for position in range(below_position_count):

            candidate_anchor = (
                result.opportunity_below_position_anchor[position]
            )

            candidate_valid = (
                result.opportunity_anchor_below_valid[
                    candidate_anchor
                ]
            )

            candidate_layer = (
                result.opportunity_anchor_below_layer[
                    candidate_anchor
                ]
            )

            candidate_is_zone = (
                result.opportunity_anchor_below_is_zone[
                    candidate_anchor
                ]
            )

            if (
                candidate_valid
                and candidate_layer == OP_ANCHOR_UNASSIGNED
                and candidate_is_zone
            ):
                below_layer1_anchor = candidate_anchor
                break

    if below_layer1_anchor >= 0:

        layer_anchor_low = (
            result.opportunity_anchor_below_low[
                below_layer1_anchor
            ]
        )

        layer_anchor_high = (
            result.opportunity_anchor_below_high[
                below_layer1_anchor
            ]
        )

        if (
            layer_anchor_low is not None
            and layer_anchor_high is not None
            and opportunity_cluster_gap is not None
        ):

            result.opportunity_below_layer_anchor_low.append(
                layer_anchor_low
            )
            result.opportunity_below_layer_anchor_high.append(
                layer_anchor_high
            )
            result.opportunity_below_layer_anchor.append(
                below_layer1_anchor
            )

            layer_extreme_low = (
                layer_anchor_low - opportunity_cluster_gap
            )

            layer_extreme_high = (
                layer_anchor_high + opportunity_cluster_gap
            )

            for anchor_index in range(OP_ANCHOR_COUNT):

                anchor_valid = (
                    result.opportunity_anchor_below_valid[
                        anchor_index
                    ]
                )

                anchor_layer = (
                    result.opportunity_anchor_below_layer[
                        anchor_index
                    ]
                )

                if (
                    anchor_valid
                    and anchor_layer == OP_ANCHOR_UNASSIGNED
                ):

                    candidate_low = (
                        result.opportunity_anchor_below_low[
                            anchor_index
                        ]
                    )

                    candidate_high = (
                        result.opportunity_anchor_below_high[
                            anchor_index
                        ]
                    )

                    if _overlaps(
                        candidate_low,
                        candidate_high,
                        layer_extreme_low,
                        layer_extreme_high,
                    ):

                        result.opportunity_anchor_below_layer[
                            anchor_index
                        ] = OP_BASE_LAYER_1

                        layer_extreme_low = min(
                            layer_extreme_low,
                            candidate_low,
                        )

                        layer_extreme_high = max(
                            layer_extreme_high,
                            candidate_high,
                        )

            result.opportunity_below_layer_extreme_low.append(
                layer_extreme_low
            )
            result.opportunity_below_layer_extreme_high.append(
                layer_extreme_high
            )

    # ========================================================
    # BELOW PRICE — LAYER 2
    # ========================================================

    below_layer2_anchor = -1

    if below_position_count > 0:

        for position in range(below_position_count):

            candidate_anchor = (
                result.opportunity_below_position_anchor[position]
            )

            candidate_valid = (
                result.opportunity_anchor_below_valid[
                    candidate_anchor
                ]
            )

            candidate_layer = (
                result.opportunity_anchor_below_layer[
                    candidate_anchor
                ]
            )

            candidate_is_zone = (
                result.opportunity_anchor_below_is_zone[
                    candidate_anchor
                ]
            )

            if (
                candidate_valid
                and candidate_layer == OP_ANCHOR_UNASSIGNED
                and candidate_is_zone
            ):
                below_layer2_anchor = candidate_anchor
                break

    if below_layer2_anchor >= 0:

        layer_anchor_low = (
            result.opportunity_anchor_below_low[
                below_layer2_anchor
            ]
        )

        layer_anchor_high = (
            result.opportunity_anchor_below_high[
                below_layer2_anchor
            ]
        )

        if (
            layer_anchor_low is not None
            and layer_anchor_high is not None
            and opportunity_cluster_gap is not None
        ):

            result.opportunity_below_layer_anchor_low.append(
                layer_anchor_low
            )
            result.opportunity_below_layer_anchor_high.append(
                layer_anchor_high
            )
            result.opportunity_below_layer_anchor.append(
                below_layer2_anchor
            )

            layer_extreme_low = (
                layer_anchor_low - opportunity_cluster_gap
            )

            layer_extreme_high = (
                layer_anchor_high + opportunity_cluster_gap
            )

            for anchor_index in range(OP_ANCHOR_COUNT):

                anchor_valid = (
                    result.opportunity_anchor_below_valid[
                        anchor_index
                    ]
                )

                anchor_layer = (
                    result.opportunity_anchor_below_layer[
                        anchor_index
                    ]
                )

                if (
                    anchor_valid
                    and anchor_layer == OP_ANCHOR_UNASSIGNED
                ):

                    candidate_low = (
                        result.opportunity_anchor_below_low[
                            anchor_index
                        ]
                    )

                    candidate_high = (
                        result.opportunity_anchor_below_high[
                            anchor_index
                        ]
                    )

                    if _overlaps(
                        candidate_low,
                        candidate_high,
                        layer_extreme_low,
                        layer_extreme_high,
                    ):

                        result.opportunity_anchor_below_layer[
                            anchor_index
                        ] = OP_BASE_LAYER_2

                        layer_extreme_low = min(
                            layer_extreme_low,
                            candidate_low,
                        )

                        layer_extreme_high = max(
                            layer_extreme_high,
                            candidate_high,
                        )

            result.opportunity_below_layer_extreme_low.append(
                layer_extreme_low
            )
            result.opportunity_below_layer_extreme_high.append(
                layer_extreme_high
            )

    # ========================================================
    # BELOW PRICE — LAYER 3
    # ========================================================

    below_layer3_anchor = -1

    if below_position_count > 0:

        for position in range(below_position_count):

            candidate_anchor = (
                result.opportunity_below_position_anchor[position]
            )

            candidate_valid = (
                result.opportunity_anchor_below_valid[
                    candidate_anchor
                ]
            )

            candidate_layer = (
                result.opportunity_anchor_below_layer[
                    candidate_anchor
                ]
            )

            candidate_is_zone = (
                result.opportunity_anchor_below_is_zone[
                    candidate_anchor
                ]
            )

            if (
                candidate_valid
                and candidate_layer == OP_ANCHOR_UNASSIGNED
                and candidate_is_zone
            ):
                below_layer3_anchor = candidate_anchor
                break

    if below_layer3_anchor >= 0:

        layer_anchor_low = (
            result.opportunity_anchor_below_low[
                below_layer3_anchor
            ]
        )

        layer_anchor_high = (
            result.opportunity_anchor_below_high[
                below_layer3_anchor
            ]
        )

        if (
            layer_anchor_low is not None
            and layer_anchor_high is not None
            and opportunity_cluster_gap is not None
        ):

            result.opportunity_below_layer_anchor_low.append(
                layer_anchor_low
            )
            result.opportunity_below_layer_anchor_high.append(
                layer_anchor_high
            )
            result.opportunity_below_layer_anchor.append(
                below_layer3_anchor
            )

            layer_extreme_low = (
                layer_anchor_low - opportunity_cluster_gap
            )

            layer_extreme_high = (
                layer_anchor_high + opportunity_cluster_gap
            )

            for anchor_index in range(OP_ANCHOR_COUNT):

                anchor_valid = (
                    result.opportunity_anchor_below_valid[
                        anchor_index
                    ]
                )

                anchor_layer = (
                    result.opportunity_anchor_below_layer[
                        anchor_index
                    ]
                )

                if (
                    anchor_valid
                    and anchor_layer == OP_ANCHOR_UNASSIGNED
                ):

                    candidate_low = (
                        result.opportunity_anchor_below_low[
                            anchor_index
                        ]
                    )

                    candidate_high = (
                        result.opportunity_anchor_below_high[
                            anchor_index
                        ]
                    )

                    if _overlaps(
                        candidate_low,
                        candidate_high,
                        layer_extreme_low,
                        layer_extreme_high,
                    ):

                        result.opportunity_anchor_below_layer[
                            anchor_index
                        ] = OP_BASE_LAYER_3

                        layer_extreme_low = min(
                            layer_extreme_low,
                            candidate_low,
                        )

                        layer_extreme_high = max(
                            layer_extreme_high,
                            candidate_high,
                        )

            result.opportunity_below_layer_extreme_low.append(
                layer_extreme_low
            )
            result.opportunity_below_layer_extreme_high.append(
                layer_extreme_high
            )

    return result