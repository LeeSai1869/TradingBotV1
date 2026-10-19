from dataclasses import dataclass
from typing import List


# ============================================================
# 10.1.10 COMBINE ORIGINAL ZONE + ENRICHMENT FEATURES
# ============================================================
#
# Rules:
#
# 1. Original zone features are always preserved.
# 2. Enrichment can only be consumed by its own stored layer.
# 3. A family may be consumed only once per layer.
# 4. If original layer already contains a family, enrichment
#    from that family is ignored for that layer.
# 5. If original layer is missing a family, the FIRST matching
#    enrichment feature for that layer is consumed.
# 6. Consumption is independent per layer.
# 7. Original zone geometry and authority are NEVER modified.
#
# Important:
#   The combined arrays contain feature records only.
#   They do NOT modify or expand the final opportunity zones.
# ============================================================


@dataclass
class OpportunityCombinedFeaturesResult:
    # ABOVE
    above_layer: List[int]
    above_family: List[int]
    above_low: List[float]
    above_high: List[float]
    above_price: List[float]

    # BELOW
    below_layer: List[int]
    below_family: List[int]
    below_low: List[float]
    below_high: List[float]
    below_price: List[float]


def _combine_layer(
    layer_number: int,
    enrichment_layer_number: int,
    original_families,
    original_lows,
    original_highs,
    enrichment_layer,
    enrichment_family,
    enrichment_price,
    combined_layer,
    combined_family,
    combined_low,
    combined_high,
    combined_price,
):
    """
    Combines one final layer.

    layer_number:
        Human-facing layer number: 1, 2, or 3.

    enrichment_layer_number:
        Zero-based layer identifier used by 10.1.9:
            0 = Layer 1
            1 = Layer 2
            2 = Layer 3

    Original features are copied first.

    Then enrichment is scanned in its original order.
    The first feature from every missing family is consumed.
    """

    # ========================================================
    # ORIGINAL FEATURES
    # ========================================================

    consumed_families = []

    if original_families is not None:

        original_count = len(original_families)

        for i in range(original_count):

            family = original_families[i]
            low = original_lows[i]
            high = original_highs[i]

            # ----------------------------------------------
            # Preserve original family.
            # ----------------------------------------------

            consumed_families.append(family)

            # ----------------------------------------------
            # Preserve original feature.
            # ----------------------------------------------

            combined_layer.append(layer_number)
            combined_family.append(family)
            combined_low.append(low)
            combined_high.append(high)
            combined_price.append(
                (low + high) / 2.0
            )

    # ========================================================
    # ENRICHMENT
    # ========================================================

    if enrichment_layer is not None:

        enrichment_count = len(enrichment_layer)

        for i in range(enrichment_count):

            candidate_layer = enrichment_layer[i]
            candidate_family = enrichment_family[i]
            candidate_price = enrichment_price[i]

            # ------------------------------------------------
            # Enrichment can ONLY belong to this layer.
            # ------------------------------------------------

            if candidate_layer != enrichment_layer_number:
                continue

            # ------------------------------------------------
            # Check whether family already exists in this
            # layer.
            # ------------------------------------------------

            family_already_consumed = False

            for existing_family in consumed_families:

                if existing_family == candidate_family:
                    family_already_consumed = True
                    break

            # ------------------------------------------------
            # Existing family -> ignore enrichment.
            # ------------------------------------------------

            if family_already_consumed:
                continue

            # ------------------------------------------------
            # Missing family -> consume exactly ONE feature.
            # ------------------------------------------------

            combined_layer.append(layer_number)
            combined_family.append(candidate_family)
            combined_low.append(candidate_price)
            combined_high.append(candidate_price)
            combined_price.append(candidate_price)

            # ------------------------------------------------
            # Mark family consumed for THIS layer only.
            # ------------------------------------------------

            consumed_families.append(candidate_family)


def combine_original_and_enrichment(
    opportunity_above_final_low,
    opportunity_above_final_high,

    opportunity_above_layer1_consumed_family,
    opportunity_above_layer1_consumed_low,
    opportunity_above_layer1_consumed_high,

    opportunity_above_layer2_consumed_family,
    opportunity_above_layer2_consumed_low,
    opportunity_above_layer2_consumed_high,

    opportunity_above_layer3_consumed_family,
    opportunity_above_layer3_consumed_low,
    opportunity_above_layer3_consumed_high,

    opportunity_above_enrichment_layer,
    opportunity_above_enrichment_family,
    opportunity_above_enrichment_price,

    opportunity_below_final_low,
    opportunity_below_final_high,

    opportunity_below_layer1_consumed_family,
    opportunity_below_layer1_consumed_low,
    opportunity_below_layer1_consumed_high,

    opportunity_below_layer2_consumed_family,
    opportunity_below_layer2_consumed_low,
    opportunity_below_layer2_consumed_high,

    opportunity_below_layer3_consumed_family,
    opportunity_below_layer3_consumed_low,
    opportunity_below_layer3_consumed_high,

    opportunity_below_enrichment_layer,
    opportunity_below_enrichment_family,
    opportunity_below_enrichment_price,
) -> OpportunityCombinedFeaturesResult:

    # ========================================================
    # OUTPUT ARRAYS
    # ========================================================

    opportunityAboveCombinedLayer: List[int] = []
    opportunityAboveCombinedFamily: List[int] = []
    opportunityAboveCombinedLow: List[float] = []
    opportunityAboveCombinedHigh: List[float] = []
    opportunityAboveCombinedPrice: List[float] = []

    opportunityBelowCombinedLayer: List[int] = []
    opportunityBelowCombinedFamily: List[int] = []
    opportunityBelowCombinedLow: List[float] = []
    opportunityBelowCombinedHigh: List[float] = []
    opportunityBelowCombinedPrice: List[float] = []

    # ========================================================
    # COUNTS
    # ========================================================

    aboveFinalLayerCount = len(opportunity_above_final_low)
    belowFinalLayerCount = len(opportunity_below_final_low)

    # ========================================================
    # ABOVE PRICE
    # ========================================================

    # --------------------------------------------------------
    # LAYER 1
    # --------------------------------------------------------

    if aboveFinalLayerCount >= 1:

        # Original zone geometry is intentionally read but
        # never modified by this stage.
        layer1FinalLow = opportunity_above_final_low[0]
        layer1FinalHigh = opportunity_above_final_high[0]

        layer1ZoneLow = layer1FinalLow
        layer1ZoneHigh = layer1FinalHigh

        _ = layer1ZoneLow
        _ = layer1ZoneHigh

        _combine_layer(
            layer_number=1,
            enrichment_layer_number=0,

            original_families=(
                opportunity_above_layer1_consumed_family
            ),
            original_lows=(
                opportunity_above_layer1_consumed_low
            ),
            original_highs=(
                opportunity_above_layer1_consumed_high
            ),

            enrichment_layer=(
                opportunity_above_enrichment_layer
            ),
            enrichment_family=(
                opportunity_above_enrichment_family
            ),
            enrichment_price=(
                opportunity_above_enrichment_price
            ),

            combined_layer=(
                opportunityAboveCombinedLayer
            ),
            combined_family=(
                opportunityAboveCombinedFamily
            ),
            combined_low=(
                opportunityAboveCombinedLow
            ),
            combined_high=(
                opportunityAboveCombinedHigh
            ),
            combined_price=(
                opportunityAboveCombinedPrice
            ),
        )

    # --------------------------------------------------------
    # LAYER 2
    # --------------------------------------------------------

    if aboveFinalLayerCount >= 2:

        layer2FinalLow = opportunity_above_final_low[1]
        layer2FinalHigh = opportunity_above_final_high[1]

        layer2ZoneLow = layer2FinalLow
        layer2ZoneHigh = layer2FinalHigh

        _ = layer2ZoneLow
        _ = layer2ZoneHigh

        _combine_layer(
            layer_number=2,
            enrichment_layer_number=1,

            original_families=(
                opportunity_above_layer2_consumed_family
            ),
            original_lows=(
                opportunity_above_layer2_consumed_low
            ),
            original_highs=(
                opportunity_above_layer2_consumed_high
            ),

            enrichment_layer=(
                opportunity_above_enrichment_layer
            ),
            enrichment_family=(
                opportunity_above_enrichment_family
            ),
            enrichment_price=(
                opportunity_above_enrichment_price
            ),

            combined_layer=(
                opportunityAboveCombinedLayer
            ),
            combined_family=(
                opportunityAboveCombinedFamily
            ),
            combined_low=(
                opportunityAboveCombinedLow
            ),
            combined_high=(
                opportunityAboveCombinedHigh
            ),
            combined_price=(
                opportunityAboveCombinedPrice
            ),
        )

    # --------------------------------------------------------
    # LAYER 3
    # --------------------------------------------------------

    if aboveFinalLayerCount >= 3:

        layer3FinalLow = opportunity_above_final_low[2]
        layer3FinalHigh = opportunity_above_final_high[2]

        layer3ZoneLow = layer3FinalLow
        layer3ZoneHigh = layer3FinalHigh

        _ = layer3ZoneLow
        _ = layer3ZoneHigh

        _combine_layer(
            layer_number=3,
            enrichment_layer_number=2,

            original_families=(
                opportunity_above_layer3_consumed_family
            ),
            original_lows=(
                opportunity_above_layer3_consumed_low
            ),
            original_highs=(
                opportunity_above_layer3_consumed_high
            ),

            enrichment_layer=(
                opportunity_above_enrichment_layer
            ),
            enrichment_family=(
                opportunity_above_enrichment_family
            ),
            enrichment_price=(
                opportunity_above_enrichment_price
            ),

            combined_layer=(
                opportunityAboveCombinedLayer
            ),
            combined_family=(
                opportunityAboveCombinedFamily
            ),
            combined_low=(
                opportunityAboveCombinedLow
            ),
            combined_high=(
                opportunityAboveCombinedHigh
            ),
            combined_price=(
                opportunityAboveCombinedPrice
            ),
        )

    # ========================================================
    # BELOW PRICE
    # ========================================================

    # --------------------------------------------------------
    # LAYER 1
    # --------------------------------------------------------

    if belowFinalLayerCount >= 1:

        layer1FinalLow = opportunity_below_final_low[0]
        layer1FinalHigh = opportunity_below_final_high[0]

        layer1ZoneLow = layer1FinalLow
        layer1ZoneHigh = layer1FinalHigh

        _ = layer1ZoneLow
        _ = layer1ZoneHigh

        _combine_layer(
            layer_number=1,
            enrichment_layer_number=0,

            original_families=(
                opportunity_below_layer1_consumed_family
            ),
            original_lows=(
                opportunity_below_layer1_consumed_low
            ),
            original_highs=(
                opportunity_below_layer1_consumed_high
            ),

            enrichment_layer=(
                opportunity_below_enrichment_layer
            ),
            enrichment_family=(
                opportunity_below_enrichment_family
            ),
            enrichment_price=(
                opportunity_below_enrichment_price
            ),

            combined_layer=(
                opportunityBelowCombinedLayer
            ),
            combined_family=(
                opportunityBelowCombinedFamily
            ),
            combined_low=(
                opportunityBelowCombinedLow
            ),
            combined_high=(
                opportunityBelowCombinedHigh
            ),
            combined_price=(
                opportunityBelowCombinedPrice
            ),
        )

    # --------------------------------------------------------
    # LAYER 2
    # --------------------------------------------------------

    if belowFinalLayerCount >= 2:

        layer2FinalLow = opportunity_below_final_low[1]
        layer2FinalHigh = opportunity_below_final_high[1]

        layer2ZoneLow = layer2FinalLow
        layer2ZoneHigh = layer2FinalHigh

        _ = layer2ZoneLow
        _ = layer2ZoneHigh

        _combine_layer(
            layer_number=2,
            enrichment_layer_number=1,

            original_families=(
                opportunity_below_layer2_consumed_family
            ),
            original_lows=(
                opportunity_below_layer2_consumed_low
            ),
            original_highs=(
                opportunity_below_layer2_consumed_high
            ),

            enrichment_layer=(
                opportunity_below_enrichment_layer
            ),
            enrichment_family=(
                opportunity_below_enrichment_family
            ),
            enrichment_price=(
                opportunity_below_enrichment_price
            ),

            combined_layer=(
                opportunityBelowCombinedLayer
            ),
            combined_family=(
                opportunityBelowCombinedFamily
            ),
            combined_low=(
                opportunityBelowCombinedLow
            ),
            combined_high=(
                opportunityBelowCombinedHigh
            ),
            combined_price=(
                opportunityBelowCombinedPrice
            ),
        )

    # --------------------------------------------------------
    # LAYER 3
    # --------------------------------------------------------

    if belowFinalLayerCount >= 3:

        layer3FinalLow = opportunity_below_final_low[2]
        layer3FinalHigh = opportunity_below_final_high[2]

        layer3ZoneLow = layer3FinalLow
        layer3ZoneHigh = layer3FinalHigh

        _ = layer3ZoneLow
        _ = layer3ZoneHigh

        _combine_layer(
            layer_number=3,
            enrichment_layer_number=2,

            original_families=(
                opportunity_below_layer3_consumed_family
            ),
            original_lows=(
                opportunity_below_layer3_consumed_low
            ),
            original_highs=(
                opportunity_below_layer3_consumed_high
            ),

            enrichment_layer=(
                opportunity_below_enrichment_layer
            ),
            enrichment_family=(
                opportunity_below_enrichment_family
            ),
            enrichment_price=(
                opportunity_below_enrichment_price
            ),

            combined_layer=(
                opportunityBelowCombinedLayer
            ),
            combined_family=(
                opportunityBelowCombinedFamily
            ),
            combined_low=(
                opportunityBelowCombinedLow
            ),
            combined_high=(
                opportunityBelowCombinedHigh
            ),
            combined_price=(
                opportunityBelowCombinedPrice
            ),
        )

    # ========================================================
    # RETURN
    # ========================================================

    return OpportunityCombinedFeaturesResult(
        above_layer=opportunityAboveCombinedLayer,
        above_family=opportunityAboveCombinedFamily,
        above_low=opportunityAboveCombinedLow,
        above_high=opportunityAboveCombinedHigh,
        above_price=opportunityAboveCombinedPrice,

        below_layer=opportunityBelowCombinedLayer,
        below_family=opportunityBelowCombinedFamily,
        below_low=opportunityBelowCombinedLow,
        below_high=opportunityBelowCombinedHigh,
        below_price=opportunityBelowCombinedPrice,
    )