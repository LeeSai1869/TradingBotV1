"""
10.1.8 FINAL OPPORTUNITY LAYERS

Purpose:
    Convert the unified candidate pool into Final Layer 1/2/3.

Rules:
    - Select nearest three candidates independently above/below.
    - Freeze core geometry.
    - Calculate authority immediately.
    - Layer 1 has priority over Layer 2.
    - Layer 2 has priority over Layer 3.
    - No enrichment occurs here.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FinalLayerSide:
    low: List[float] = field(default_factory=list)
    high: List[float] = field(default_factory=list)
    price: List[float] = field(default_factory=list)
    candidate_type: List[int] = field(default_factory=list)
    source: List[int] = field(default_factory=list)

    authority_low: List[float] = field(default_factory=list)
    authority_high: List[float] = field(default_factory=list)

    consumed_family: List[List[int]] = field(default_factory=list)
    consumed_low: List[List[float]] = field(default_factory=list)
    consumed_high: List[List[float]] = field(default_factory=list)


@dataclass
class FinalOpportunityLayers:
    above: FinalLayerSide = field(default_factory=FinalLayerSide)
    below: FinalLayerSide = field(default_factory=FinalLayerSide)


def _select_three_nearest_above(
    current_price: float,
    candidate_low: List[Optional[float]],
):
    selected = []

    for index, low in enumerate(candidate_low):

        if low is None:
            continue

        distance = low - current_price

        if distance >= 0:
            selected.append((distance, index))

    selected.sort(key=lambda x: x[0])

    return [index for _, index in selected[:3]]


def _select_three_nearest_below(
    current_price: float,
    candidate_high: List[Optional[float]],
):
    selected = []

    for index, high in enumerate(candidate_high):

        if high is None:
            continue

        distance = current_price - high

        if distance >= 0:
            selected.append((distance, index))

    selected.sort(key=lambda x: x[0])

    return [index for _, index in selected[:3]]


def _freeze_side(
    selected_indices: List[int],
    candidate_low: List[float],
    candidate_high: List[float],
    candidate_price: List[float],
    candidate_type: List[int],
    candidate_source: List[int],
    cluster_gap: float,
    above: bool,
) -> FinalLayerSide:

    result = FinalLayerSide()

    # ---------------------------------------------------------------
    # Freeze core geometry.
    # ---------------------------------------------------------------

    for candidate_index in selected_indices:

        result.low.append(candidate_low[candidate_index])
        result.high.append(candidate_high[candidate_index])
        result.price.append(candidate_price[candidate_index])
        result.candidate_type.append(candidate_type[candidate_index])
        result.source.append(candidate_source[candidate_index])

    # ---------------------------------------------------------------
    # Calculate frozen authority.
    # ---------------------------------------------------------------

    for layer_index in range(len(result.low)):

        natural_low = result.low[layer_index] - cluster_gap
        natural_high = result.high[layer_index] + cluster_gap

        if layer_index == 0:

            authority_low = natural_low
            authority_high = natural_high

        elif above:

            # Layer 1 has priority.
            # Layer 2 cannot extend lower through Layer 1.
            # Layer 3 cannot extend lower through Layer 2.

            previous_authority_high = result.authority_high[
                layer_index - 1
            ]

            authority_low = max(
                natural_low,
                previous_authority_high,
            )

            authority_high = natural_high

        else:

            # Layer 1 has priority.
            # Layer 2 cannot extend upper through Layer 1.
            # Layer 3 cannot extend upper through Layer 2.

            previous_authority_low = result.authority_low[
                layer_index - 1
            ]

            authority_low = natural_low

            authority_high = min(
                natural_high,
                previous_authority_low,
            )

        result.authority_low.append(authority_low)
        result.authority_high.append(authority_high)

        result.consumed_family.append([])
        result.consumed_low.append([])
        result.consumed_high.append([])

    return result


def _collect_consumed_real_layer_references(
    final_side: FinalLayerSide,
    position_anchor: List[int],
    position_low: List[Optional[float]],
    position_high: List[Optional[float]],
    family_anchor: List[int],
    anchor_layer: List[int],
) -> None:

    for layer_index in range(len(final_side.low)):

        # Final layers are ordered Layer 1, Layer 2, Layer 3.
        expected_layer = layer_index + 1

        for position_index, anchor_index in enumerate(position_anchor):

            if anchor_index < 0:
                continue

            if anchor_index >= len(anchor_layer):
                continue

            ownership = anchor_layer[anchor_index]

            if ownership != expected_layer:
                continue

            consumed_low = position_low[position_index]
            consumed_high = position_high[position_index]

            family = family_anchor[position_index]

            if family >= 0:
                final_side.consumed_family[
                    layer_index
                ].append(family)

            if consumed_low is not None:
                final_side.consumed_low[
                    layer_index
                ].append(consumed_low)

            if consumed_high is not None:
                final_side.consumed_high[
                    layer_index
                ].append(consumed_high)


def build_final_opportunity_layers(
    f,
    candidate_pool,

    opportunity_cluster_gap: float,

    # ---------------------------------------------------------------
    # ABOVE ORIGINAL POSITION DATA
    # ---------------------------------------------------------------
    above_position_anchor: List[int],
    above_position_low: List[Optional[float]],
    above_position_high: List[Optional[float]],
    above_family_anchor: List[int],
    anchor_above_layer: List[int],

    # ---------------------------------------------------------------
    # BELOW ORIGINAL POSITION DATA
    # ---------------------------------------------------------------
    below_position_anchor: List[int],
    below_position_low: List[Optional[float]],
    below_position_high: List[Optional[float]],
    below_family_anchor: List[int],
    anchor_below_layer: List[int],
) -> FinalOpportunityLayers:

    result = FinalOpportunityLayers()

    current_price = getattr(f, "c", None)

    if current_price is None:
        return result

    # =================================================================
    # ABOVE
    # =================================================================

    above_selected = _select_three_nearest_above(
        current_price,
        candidate_pool.above_low,
    )

    result.above = _freeze_side(
        selected_indices=above_selected,
        candidate_low=candidate_pool.above_low,
        candidate_high=candidate_pool.above_high,
        candidate_price=candidate_pool.above_price,
        candidate_type=candidate_pool.above_type,
        candidate_source=candidate_pool.above_source,
        cluster_gap=opportunity_cluster_gap,
        above=True,
    )

    _collect_consumed_real_layer_references(
        final_side=result.above,
        position_anchor=above_position_anchor,
        position_low=above_position_low,
        position_high=above_position_high,
        family_anchor=above_family_anchor,
        anchor_layer=anchor_above_layer,
    )

    # =================================================================
    # BELOW
    # =================================================================

    below_selected = _select_three_nearest_below(
        current_price,
        candidate_pool.below_high,
    )

    result.below = _freeze_side(
        selected_indices=below_selected,
        candidate_low=candidate_pool.below_low,
        candidate_high=candidate_pool.below_high,
        candidate_price=candidate_pool.below_price,
        candidate_type=candidate_pool.below_type,
        candidate_source=candidate_pool.below_source,
        cluster_gap=opportunity_cluster_gap,
        above=False,
    )

    _collect_consumed_real_layer_references(
        final_side=result.below,
        position_anchor=below_position_anchor,
        position_low=below_position_low,
        position_high=below_position_high,
        family_anchor=below_family_anchor,
        anchor_layer=anchor_below_layer,
    )

    return result