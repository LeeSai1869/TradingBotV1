from dataclasses import dataclass, field
from typing import Optional, List, Any


# ============================================================
# 10.1.2 OPPORTUNITY ANCHORS
# ============================================================

OPPORTUNITY_LAYER_SEPARATION_ATR = 2.0
OPPORTUNITY_CONFLUENCE_ATR = 1.0


@dataclass
class OpportunityAnchorResult:
    """
    Internal result of 10.1.2 Opportunity Anchors.

    This is NOT the final Opportunity Score Packet.
    It is consumed directly by the later Base Layers stage.
    """

    opportunity_layer_separation_atr: float = OPPORTUNITY_LAYER_SEPARATION_ATR
    opportunity_confluence_atr: float = OPPORTUNITY_CONFLUENCE_ATR

    # Last processed anchor state
    anchor_low: Optional[float] = None
    anchor_high: Optional[float] = None
    anchor_front: Optional[float] = None
    anchor_exists: bool = False
    anchor_bar: Optional[int] = None

    # All accepted opportunity zones
    opportunity_zone_low: List[Optional[float]] = field(default_factory=list)
    opportunity_zone_high: List[Optional[float]] = field(default_factory=list)
    opportunity_zone_bar: List[Optional[int]] = field(default_factory=list)


def _add_anchor(
    result: OpportunityAnchorResult,
    low: Optional[float],
    high: Optional[float],
    front: Optional[float],
    bar: Optional[int],
) -> None:
    """
    Equivalent to the repeated Pine anchor assignment + array.push()
    sequence.

    No scoring or geometry is changed here.
    """

    result.anchor_low = low
    result.anchor_high = high
    result.anchor_front = front
    result.anchor_bar = bar
    result.anchor_exists = True

    result.opportunity_zone_low.append(low)
    result.opportunity_zone_high.append(high)
    result.opportunity_zone_bar.append(bar)


def build_opportunity_anchors(
    f: Any,
    *,
    nearest_support_zone_low: Optional[float] = None,
    nearest_support_zone_high: Optional[float] = None,
    nearest_support_zone_bar: Optional[int] = None,
    nearest_resistance_zone_low: Optional[float] = None,
    nearest_resistance_zone_high: Optional[float] = None,
    nearest_resistance_zone_bar: Optional[int] = None,
    resistance_zone_id_array: Optional[list] = None,
    support_zone_id_array: Optional[list] = None,
) -> OpportunityAnchorResult:
    """
    10.1.2 Opportunity Anchors.

    Preserves the supplied Pine ordering:

        2.1 Support / Resistance
        2.2 FVG
        2.3 Order Block
        2.4 Breaker
        2.5 Volume Profile HVN
        2.6 Volume Profile LVN
        2.7 Fibonacci 0.500 - 0.618
        2.8 Fibonacci 0.618 - 0.786

    The function deliberately does NOT:
        - calculate layer scores
        - select Layer 1/2/3
        - perform enrichment
        - perform final-layer construction
        - make a BUY/SELL decision
    """

    result = OpportunityAnchorResult()

    # --------------------------------------------------------
    # 2.1 SUPPORT / RESISTANCE
    # --------------------------------------------------------

    # Buy Side
    if (
        nearest_resistance_zone_low is not None
        and nearest_resistance_zone_high is not None
        and f.c < nearest_resistance_zone_low
    ):
        resistance_anchor_index = -1

        if resistance_zone_id_array is not None:
            try:
                resistance_anchor_index = resistance_zone_id_array.index(
                    f.nearestResistanceZonePriceID
                )
            except (ValueError, AttributeError):
                resistance_anchor_index = -1

        if resistance_anchor_index >= 0:
            _add_anchor(
                result,
                nearest_resistance_zone_low,
                nearest_resistance_zone_high,
                nearest_resistance_zone_low,
                nearest_resistance_zone_bar,
            )

    # Sell Side
    if (
        nearest_support_zone_low is not None
        and nearest_support_zone_high is not None
        and f.c > nearest_support_zone_high
    ):
        support_anchor_index = -1

        if support_zone_id_array is not None:
            try:
                support_anchor_index = support_zone_id_array.index(
                    f.nearestSupportZonePriceID
                )
            except (ValueError, AttributeError):
                support_anchor_index = -1

        if support_anchor_index >= 0:
            # Pine uses array.get(supportBarArray, supportAnchorIndex)
            # rather than nearestSupportZoneBar here.
            support_bar = nearest_support_zone_bar

            _add_anchor(
                result,
                nearest_support_zone_low,
                nearest_support_zone_high,
                nearest_support_zone_high,
                support_bar,
            )

    # --------------------------------------------------------
    # 2.2 FVG
    # --------------------------------------------------------

    # Bear FVG above price
    if (
        getattr(f, "hasBearFVG", False)
        and f.nearestBearFVGLow is not None
        and f.nearestBearFVGHigh is not None
        and f.nearestBearFVGLow > f.c
    ):
        _add_anchor(
            result,
            f.nearestBearFVGLow,
            f.nearestBearFVGHigh,
            f.nearestBearFVGLow,
            f.nearestBearFVGCreatedBar,
        )

    # Bull FVG below price
    if (
        getattr(f, "hasBullFVG", False)
        and f.nearestBullFVGLow is not None
        and f.nearestBullFVGHigh is not None
        and f.c > f.nearestBullFVGHigh
    ):
        _add_anchor(
            result,
            f.nearestBullFVGLow,
            f.nearestBullFVGHigh,
            f.nearestBullFVGHigh,
            f.nearestBullFVGCreatedBar,
        )

    # --------------------------------------------------------
    # 2.3 ORDER BLOCK
    # --------------------------------------------------------

    # Buy Side — strict bear OB first
    if (
        f.activeStrictBearOBLow is not None
        and f.activeStrictBearOBHigh is not None
        and f.activeStrictBearOBLow > f.c
    ):
        _add_anchor(
            result,
            f.activeStrictBearOBLow,
            f.activeStrictBearOBHigh,
            f.activeStrictBearOBLow,
            f.activeStrictBearOBBar,
        )

    # Buy Side — normal bear OB fallback
    elif (
        f.activeBearOBLow is not None
        and f.activeBearOBHigh is not None
        and f.activeBearOBLow > f.c
    ):
        _add_anchor(
            result,
            f.activeBearOBLow,
            f.activeBearOBHigh,
            f.activeBearOBLow,
            f.activeBearOBBar,
        )

    # Sell Side — strict bull OB first
    if (
        f.activeStrictBullOBLow is not None
        and f.activeStrictBullOBHigh is not None
        and f.activeStrictBullOBHigh < f.c
    ):
        _add_anchor(
            result,
            f.activeStrictBullOBLow,
            f.activeStrictBullOBHigh,
            f.activeStrictBullOBHigh,
            f.activeStrictBullOBBar,
        )

    # Sell Side — normal bull OB fallback
    elif (
        f.activeBullOBLow is not None
        and f.activeBullOBHigh is not None
        and f.activeBullOBHigh < f.c
    ):
        _add_anchor(
            result,
            f.activeBullOBLow,
            f.activeBullOBHigh,
            f.activeBullOBHigh,
            f.activeBullOBBar,
        )

    # --------------------------------------------------------
    # 2.4 BREAKER
    # --------------------------------------------------------

    # Buy Side — strict bull breaker
    if (
        f.strictBullBreakerLow is not None
        and f.strictBullBreakerHigh is not None
        and f.strictBullBreakerLow > f.c
    ):
        _add_anchor(
            result,
            f.strictBullBreakerLow,
            f.strictBullBreakerHigh,
            f.strictBullBreakerLow,
            None,
        )

    # Buy Side — normal bull breaker
    elif (
        f.bullBreakerLow is not None
        and f.bullBreakerHigh is not None
        and f.bullBreakerLow > f.c
    ):
        _add_anchor(
            result,
            f.bullBreakerLow,
            f.bullBreakerHigh,
            f.bullBreakerLow,
            None,
        )

    # Sell Side — strict bear breaker
    if (
        f.strictBearBreakerLow is not None
        and f.strictBearBreakerHigh is not None
        and f.strictBearBreakerHigh < f.c
    ):
        _add_anchor(
            result,
            f.strictBearBreakerLow,
            f.strictBearBreakerHigh,
            f.strictBearBreakerHigh,
            None,
        )

    # Sell Side — normal bear breaker
    elif (
        f.bearBreakerLow is not None
        and f.bearBreakerHigh is not None
        and f.bearBreakerHigh < f.c
    ):
        _add_anchor(
            result,
            f.bearBreakerLow,
            f.bearBreakerHigh,
            f.bearBreakerHigh,
            None,
        )

    # --------------------------------------------------------
    # 2.5 VOLUME PROFILE — HVN
    # --------------------------------------------------------

    # HVN ABOVE
    if (
        f.vpHVNLow is not None
        and f.vpHVNHigh is not None
        and f.vpHVNLow <= f.vpHVNHigh
        and f.vpHVNLow > f.c
    ):
        _add_anchor(
            result,
            f.vpHVNLow,
            f.vpHVNHigh,
            f.vpHVNLow,
            None,
        )

    # HVN BELOW
    if (
        f.vpHVNLow is not None
        and f.vpHVNHigh is not None
        and f.vpHVNLow <= f.vpHVNHigh
        and f.vpHVNHigh < f.c
    ):
        _add_anchor(
            result,
            f.vpHVNLow,
            f.vpHVNHigh,
            f.vpHVNHigh,
            None,
        )

    # --------------------------------------------------------
    # 2.6 VOLUME PROFILE — LVN
    # --------------------------------------------------------

    # LVN ABOVE
    if (
        f.vpLVNLow is not None
        and f.vpLVNHigh is not None
        and f.vpLVNLow <= f.vpLVNHigh
        and f.vpLVNLow > f.c
    ):
        _add_anchor(
            result,
            f.vpLVNLow,
            f.vpLVNHigh,
            f.vpLVNLow,
            None,
        )

    # LVN BELOW
    if (
        f.vpLVNLow is not None
        and f.vpLVNHigh is not None
        and f.vpLVNLow <= f.vpLVNHigh
        and f.vpLVNHigh < f.c
    ):
        _add_anchor(
            result,
            f.vpLVNLow,
            f.vpLVNHigh,
            f.vpLVNHigh,
            None,
        )

    # --------------------------------------------------------
    # 2.7 FIBONACCI 0.500 - 0.618
    # --------------------------------------------------------

    # Zone ABOVE
    if (
        f.fib050Price is not None
        and f.fib0618Price is not None
        and f.fib050Price <= f.fib0618Price
        and f.fib050Price > f.c
    ):
        _add_anchor(
            result,
            f.fib050Price,
            f.fib0618Price,
            f.fib050Price,
            None,
        )

    # Zone BELOW
    if (
        f.fib050Price is not None
        and f.fib0618Price is not None
        and f.fib050Price <= f.fib0618Price
        and f.fib0618Price < f.c
    ):
        _add_anchor(
            result,
            f.fib050Price,
            f.fib0618Price,
            f.fib0618Price,
            None,
        )

    # --------------------------------------------------------
    # 2.8 FIBONACCI 0.618 - 0.786
    # --------------------------------------------------------

    # Zone ABOVE
    if (
        f.fib0618Price is not None
        and f.fib0786Price is not None
        and f.fib0618Price <= f.fib0786Price
        and f.fib0618Price > f.c
    ):
        _add_anchor(
            result,
            f.fib0618Price,
            f.fib0786Price,
            f.fib0618Price,
            None,
        )

    # Zone BELOW
    if (
        f.fib0618Price is not None
        and f.fib0786Price is not None
        and f.fib0618Price <= f.fib0786Price
        and f.fib0786Price < f.c
    ):
        _add_anchor(
            result,
            f.fib0618Price,
            f.fib0786Price,
            f.fib0786Price,
            None,
        )

    return result