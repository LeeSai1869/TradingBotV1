"""
10.1.6 Opportunity Pseudo-Zones

Purpose:
    Form pseudo-zones from unconsumed individual price references remaining
    after the three real Base Layers have been created.

Rules preserved from Pine:
    - Pseudo-zone susceptible distance = ATR * 3.0
    - Starting point is the authoritative anchor price.
    - Real zones remain authoritative and limit the susceptible search area.
    - A pseudo-zone requires at least two consumed references.
    - Stored geometry is compressed to the extreme consumed references.
    - If compressed width > ATR, geometry is reduced to exactly ATR around
      the midpoint.
    - Consumed anchors receive OP_ANCHOR_CONSUMED ownership.
    - The next pseudo-zone starts from the nearest remaining unconsumed point.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

OP_PSEUDO_ZONE_ATR = 3.0

# Must match the ownership constant used by 10.1.3 Base Layers.
OP_ANCHOR_CONSUMED = -2


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------

@dataclass
class PseudoZoneResult:
    """
    Internal result consumed by later Opportunity Engine stages.

    These are deliberately not exposed as the final Opportunity Score Packet.
    """

    pseudo_zone_distance: Optional[float] = None

    # ABOVE
    above_pseudo_low: List[float] = field(default_factory=list)
    above_pseudo_high: List[float] = field(default_factory=list)
    above_pseudo_extreme_low: List[float] = field(default_factory=list)
    above_pseudo_extreme_high: List[float] = field(default_factory=list)
    above_pseudo_anchor: List[int] = field(default_factory=list)

    # BELOW
    below_pseudo_low: List[float] = field(default_factory=list)
    below_pseudo_high: List[float] = field(default_factory=list)
    below_pseudo_extreme_low: List[float] = field(default_factory=list)
    below_pseudo_extreme_high: List[float] = field(default_factory=list)
    below_pseudo_anchor: List[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _get(value: Any, name: str, default: Any = None) -> Any:
    """
    Safe attribute access.

    This allows the stage to work with the existing MarketFeatures / internal
    objects without changing their structure.
    """
    return getattr(value, name, default)


def _valid_price(value: Any) -> bool:
    return value is not None


# ---------------------------------------------------------------------------
# ABOVE PSEUDO-ZONES
# ---------------------------------------------------------------------------

def _build_above_pseudo_zones(
    f: Any,
    above_position_anchor: List[int],
    anchor_above_valid: List[bool],
    anchor_above_layer: List[int],
    anchor_above_is_zone: List[bool],
    anchor_above_low: List[Optional[float]],
    above_layer_extreme_low: List[Optional[float]],
    pseudo_zone_distance: float,
    result: PseudoZoneResult,
) -> None:

    above_position_count = len(above_position_anchor)

    if above_position_count <= 0:
        return

    atr = _get(f, "atr")

    if atr is None or atr <= 0:
        return

    continue_search = True

    while continue_search:
        continue_search = False

        # ---------------------------------------------------------------
        # Find nearest remaining individual price anchor.
        # ABOVE = lowest remaining price.
        # ---------------------------------------------------------------

        nearest_point_anchor = -1
        nearest_point_price = None

        for position_index in range(above_position_count):

            candidate_anchor = above_position_anchor[position_index]

            candidate_valid = anchor_above_valid[candidate_anchor]
            candidate_ownership = anchor_above_layer[candidate_anchor]
            candidate_is_zone = anchor_above_is_zone[candidate_anchor]
            candidate_price = anchor_above_low[candidate_anchor]

            if (
                candidate_valid
                and candidate_ownership == -1
                and not candidate_is_zone
                and _valid_price(candidate_price)
            ):
                if (
                    nearest_point_price is None
                    or candidate_price < nearest_point_price
                ):
                    nearest_point_anchor = candidate_anchor
                    nearest_point_price = candidate_price

        # ---------------------------------------------------------------
        # Establish authoritative starting edge.
        # ---------------------------------------------------------------

        if (
            nearest_point_anchor < 0
            or nearest_point_price is None
        ):
            continue

        # ---------------------------------------------------------------
        # Find nearest real-zone boundary ABOVE the anchor.
        # Real zones remain authoritative.
        # ---------------------------------------------------------------

        next_real_zone_low = None

        above_layer_count = len(above_layer_extreme_low)

        for layer_index in range(above_layer_count):

            real_zone_low = above_layer_extreme_low[layer_index]

            if (
                real_zone_low is not None
                and real_zone_low > nearest_point_price
            ):
                if (
                    next_real_zone_low is None
                    or real_zone_low < next_real_zone_low
                ):
                    next_real_zone_low = real_zone_low

        # ---------------------------------------------------------------
        # 3 ATR susceptible range.
        # ---------------------------------------------------------------

        susceptible_high = (
            nearest_point_price + pseudo_zone_distance
        )

        if next_real_zone_low is not None:
            susceptible_high = min(
                susceptible_high,
                next_real_zone_low - atr,
            )

        # ---------------------------------------------------------------
        # Find second individual price.
        #
        # This does not consume anything yet.
        # It only determines whether a pseudo-zone can exist.
        # ---------------------------------------------------------------

        second_point_anchor = -1
        second_point_price = None

        for position_index in range(above_position_count):

            candidate_anchor = above_position_anchor[position_index]

            candidate_valid = anchor_above_valid[candidate_anchor]
            candidate_ownership = anchor_above_layer[candidate_anchor]
            candidate_is_zone = anchor_above_is_zone[candidate_anchor]
            candidate_price = anchor_above_low[candidate_anchor]

            if (
                candidate_valid
                and candidate_ownership == -1
                and not candidate_is_zone
                and _valid_price(candidate_price)
            ):
                if (
                    candidate_anchor != nearest_point_anchor
                    and candidate_price > nearest_point_price
                    and candidate_price <= susceptible_high
                ):
                    if (
                        second_point_price is None
                        or candidate_price < second_point_price
                    ):
                        second_point_price = candidate_price
                        second_point_anchor = candidate_anchor

        # ---------------------------------------------------------------
        # SECOND PRICE EXISTS
        # ---------------------------------------------------------------

        if second_point_anchor < 0:
            continue

        pseudo_extreme_low = nearest_point_price
        pseudo_extreme_high = nearest_point_price
        consumed_reference_count = 0

        # ---------------------------------------------------------------
        # Consume all qualifying unconsumed individual references.
        # ---------------------------------------------------------------

        for position_index in range(above_position_count):

            candidate_anchor = above_position_anchor[position_index]

            candidate_valid = anchor_above_valid[candidate_anchor]
            candidate_ownership = anchor_above_layer[candidate_anchor]
            candidate_is_zone = anchor_above_is_zone[candidate_anchor]
            candidate_price = anchor_above_low[candidate_anchor]

            if (
                candidate_valid
                and candidate_ownership == -1
                and not candidate_is_zone
                and _valid_price(candidate_price)
            ):
                if (
                    candidate_price >= nearest_point_price
                    and candidate_price <= susceptible_high
                ):
                    anchor_above_layer[candidate_anchor] = (
                        OP_ANCHOR_CONSUMED
                    )

                    pseudo_extreme_low = min(
                        pseudo_extreme_low,
                        candidate_price,
                    )

                    pseudo_extreme_high = max(
                        pseudo_extreme_high,
                        candidate_price,
                    )

                    consumed_reference_count += 1

        # ---------------------------------------------------------------
        # Minimum two references.
        # ---------------------------------------------------------------

        if consumed_reference_count >= 2:

            pseudo_zone_width = (
                pseudo_extreme_high - pseudo_extreme_low
            )

            final_pseudo_low = pseudo_extreme_low
            final_pseudo_high = pseudo_extreme_high

            # -----------------------------------------------------------
            # Compress pseudo-zone to ATR width when necessary.
            # -----------------------------------------------------------

            if pseudo_zone_width > atr:

                pseudo_zone_mid = (
                    pseudo_extreme_low + pseudo_extreme_high
                ) / 2.0

                final_pseudo_low = (
                    pseudo_zone_mid - atr / 2.0
                )

                final_pseudo_high = (
                    pseudo_zone_mid + atr / 2.0
                )

            # -----------------------------------------------------------
            # Store pseudo-zone.
            # -----------------------------------------------------------

            result.above_pseudo_low.append(final_pseudo_low)
            result.above_pseudo_high.append(final_pseudo_high)

            result.above_pseudo_extreme_low.append(
                pseudo_extreme_low
            )
            result.above_pseudo_extreme_high.append(
                pseudo_extreme_high
            )

            result.above_pseudo_anchor.append(
                nearest_point_anchor
            )

            # -----------------------------------------------------------
            # Continue from the next nearest unconsumed reference.
            # -----------------------------------------------------------

            continue_search = True


# ---------------------------------------------------------------------------
# BELOW PSEUDO-ZONES
# ---------------------------------------------------------------------------

def _build_below_pseudo_zones(
    f: Any,
    below_position_anchor: List[int],
    anchor_below_valid: List[bool],
    anchor_below_layer: List[int],
    anchor_below_is_zone: List[bool],
    anchor_below_high: List[Optional[float]],
    below_layer_extreme_high: List[Optional[float]],
    pseudo_zone_distance: float,
    result: PseudoZoneResult,
) -> None:

    below_position_count = len(below_position_anchor)

    if below_position_count <= 0:
        return

    atr = _get(f, "atr")

    if atr is None or atr <= 0:
        return

    continue_search = True

    while continue_search:
        continue_search = False

        # ---------------------------------------------------------------
        # Find nearest remaining individual price anchor.
        # BELOW = highest remaining price.
        # ---------------------------------------------------------------

        nearest_point_anchor = -1
        nearest_point_price = None

        for position_index in range(below_position_count):

            candidate_anchor = below_position_anchor[position_index]

            candidate_valid = anchor_below_valid[candidate_anchor]
            candidate_ownership = anchor_below_layer[candidate_anchor]
            candidate_is_zone = anchor_below_is_zone[candidate_anchor]
            candidate_price = anchor_below_high[candidate_anchor]

            if (
                candidate_valid
                and candidate_ownership == -1
                and not candidate_is_zone
                and _valid_price(candidate_price)
            ):
                if (
                    nearest_point_price is None
                    or candidate_price > nearest_point_price
                ):
                    nearest_point_anchor = candidate_anchor
                    nearest_point_price = candidate_price

        # ---------------------------------------------------------------
        # Establish authoritative starting edge.
        # ---------------------------------------------------------------

        if (
            nearest_point_anchor < 0
            or nearest_point_price is None
        ):
            continue

        # ---------------------------------------------------------------
        # Find nearest real-zone boundary BELOW the anchor.
        # ---------------------------------------------------------------

        next_real_zone_high = None

        below_layer_count = len(below_layer_extreme_high)

        for layer_index in range(below_layer_count):

            real_zone_high = below_layer_extreme_high[layer_index]

            if (
                real_zone_high is not None
                and real_zone_high < nearest_point_price
            ):
                if (
                    next_real_zone_high is None
                    or real_zone_high > next_real_zone_high
                ):
                    next_real_zone_high = real_zone_high

        # ---------------------------------------------------------------
        # 3 ATR susceptible range downward.
        # ---------------------------------------------------------------

        susceptible_low = (
            nearest_point_price - pseudo_zone_distance
        )

        if next_real_zone_high is not None:
            susceptible_low = max(
                susceptible_low,
                next_real_zone_high + atr,
            )

        # ---------------------------------------------------------------
        # Find second individual price.
        # ---------------------------------------------------------------

        second_point_anchor = -1
        second_point_price = None

        for position_index in range(below_position_count):

            candidate_anchor = below_position_anchor[position_index]

            candidate_valid = anchor_below_valid[candidate_anchor]
            candidate_ownership = anchor_below_layer[candidate_anchor]
            candidate_is_zone = anchor_below_is_zone[candidate_anchor]
            candidate_price = anchor_below_high[candidate_anchor]

            if (
                candidate_valid
                and candidate_ownership == -1
                and not candidate_is_zone
                and _valid_price(candidate_price)
            ):
                if (
                    candidate_anchor != nearest_point_anchor
                    and candidate_price < nearest_point_price
                    and candidate_price >= susceptible_low
                ):
                    if (
                        second_point_price is None
                        or candidate_price > second_point_price
                    ):
                        second_point_price = candidate_price
                        second_point_anchor = candidate_anchor

        # ---------------------------------------------------------------
        # SECOND PRICE EXISTS
        # ---------------------------------------------------------------

        if second_point_anchor < 0:
            continue

        pseudo_extreme_low = nearest_point_price
        pseudo_extreme_high = nearest_point_price
        consumed_reference_count = 0

        # ---------------------------------------------------------------
        # Consume all qualifying unconsumed individual references.
        # ---------------------------------------------------------------

        for position_index in range(below_position_count):

            candidate_anchor = below_position_anchor[position_index]

            candidate_valid = anchor_below_valid[candidate_anchor]
            candidate_ownership = anchor_below_layer[candidate_anchor]
            candidate_is_zone = anchor_below_is_zone[candidate_anchor]
            candidate_price = anchor_below_high[candidate_anchor]

            if (
                candidate_valid
                and candidate_ownership == -1
                and not candidate_is_zone
                and _valid_price(candidate_price)
            ):
                if (
                    candidate_price <= nearest_point_price
                    and candidate_price >= susceptible_low
                ):
                    anchor_below_layer[candidate_anchor] = (
                        OP_ANCHOR_CONSUMED
                    )

                    pseudo_extreme_low = min(
                        pseudo_extreme_low,
                        candidate_price,
                    )

                    pseudo_extreme_high = max(
                        pseudo_extreme_high,
                        candidate_price,
                    )

                    consumed_reference_count += 1

        # ---------------------------------------------------------------
        # Minimum two references.
        # ---------------------------------------------------------------

        if consumed_reference_count >= 2:

            pseudo_zone_width = (
                pseudo_extreme_high - pseudo_extreme_low
            )

            final_pseudo_low = pseudo_extreme_low
            final_pseudo_high = pseudo_extreme_high

            # -----------------------------------------------------------
            # Compress pseudo-zone to ATR width when necessary.
            # -----------------------------------------------------------

            if pseudo_zone_width > atr:

                pseudo_zone_mid = (
                    pseudo_extreme_low + pseudo_extreme_high
                ) / 2.0

                final_pseudo_low = (
                    pseudo_zone_mid - atr / 2.0
                )

                final_pseudo_high = (
                    pseudo_zone_mid + atr / 2.0
                )

            # -----------------------------------------------------------
            # Store pseudo-zone.
            # -----------------------------------------------------------

            result.below_pseudo_low.append(final_pseudo_low)
            result.below_pseudo_high.append(final_pseudo_high)

            result.below_pseudo_extreme_low.append(
                pseudo_extreme_low
            )
            result.below_pseudo_extreme_high.append(
                pseudo_extreme_high
            )

            result.below_pseudo_anchor.append(
                nearest_point_anchor
            )

            # -----------------------------------------------------------
            # Continue from next nearest unconsumed reference.
            # -----------------------------------------------------------

            continue_search = True


# ---------------------------------------------------------------------------
# MAIN STAGE
# ---------------------------------------------------------------------------

def build_pseudo_zones(
    f: Any,

    # ABOVE POSITION ARRAYS FROM 10.1.3
    opportunity_above_position_anchor: List[int],
    opportunity_anchor_above_valid: List[bool],
    opportunity_anchor_above_layer: List[int],
    opportunity_anchor_above_is_zone: List[bool],
    opportunity_anchor_above_low: List[Optional[float]],

    # BELOW POSITION ARRAYS FROM 10.1.3
    opportunity_below_position_anchor: List[int],
    opportunity_anchor_below_valid: List[bool],
    opportunity_anchor_below_layer: List[int],
    opportunity_anchor_below_is_zone: List[bool],
    opportunity_anchor_below_high: List[Optional[float]],

    # REAL LAYER EXTREMES FROM 10.1.3
    opportunity_above_layer_extreme_low: List[Optional[float]],
    opportunity_below_layer_extreme_high: List[Optional[float]],
) -> PseudoZoneResult:

    result = PseudoZoneResult()

    atr = _get(f, "atr")

    # Pine:
    # opportunityPseudoZoneDistance =
    #     not na(f.atr) and f.atr > 0
    #         ? f.atr * OP_PSEUDO_ZONE_ATR
    #         : na

    if atr is None or atr <= 0:
        return result

    pseudo_zone_distance = atr * OP_PSEUDO_ZONE_ATR

    result.pseudo_zone_distance = pseudo_zone_distance

    # -------------------------------------------------------------------
    # ABOVE
    # -------------------------------------------------------------------

    _build_above_pseudo_zones(
        f=f,
        above_position_anchor=opportunity_above_position_anchor,
        anchor_above_valid=opportunity_anchor_above_valid,
        anchor_above_layer=opportunity_anchor_above_layer,
        anchor_above_is_zone=opportunity_anchor_above_is_zone,
        anchor_above_low=opportunity_anchor_above_low,
        above_layer_extreme_low=opportunity_above_layer_extreme_low,
        pseudo_zone_distance=pseudo_zone_distance,
        result=result,
    )

    # -------------------------------------------------------------------
    # BELOW
    # -------------------------------------------------------------------

    _build_below_pseudo_zones(
        f=f,
        below_position_anchor=opportunity_below_position_anchor,
        anchor_below_valid=opportunity_anchor_below_valid,
        anchor_below_layer=opportunity_anchor_below_layer,
        anchor_below_is_zone=opportunity_anchor_below_is_zone,
        anchor_below_high=opportunity_anchor_below_high,
        below_layer_extreme_high=opportunity_below_layer_extreme_high,
        pseudo_zone_distance=pseudo_zone_distance,
        result=result,
    )

    return result