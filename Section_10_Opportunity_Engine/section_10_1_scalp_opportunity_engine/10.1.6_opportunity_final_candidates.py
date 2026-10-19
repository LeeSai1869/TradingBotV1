"""
10.1.7 FINAL OPPORTUNITY LAYER CANDIDATE COLLECTION

Collects:
    1. Real zone layers
    2. Pseudo-zones
    3. Remaining unconsumed individual references

This stage does NOT:
    - select final layers
    - calculate authority
    - enrich layers
    - expand geometry

It only creates one unified spatial candidate pool.
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# CANDIDATE TYPES
# ---------------------------------------------------------------------------

OP_FINAL_CANDIDATE_ZONE = 0
OP_FINAL_CANDIDATE_PSEUDO = 1
OP_FINAL_CANDIDATE_POINT = 2


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------

@dataclass
class FinalCandidatePool:
    # ABOVE
    above_low: List[float] = field(default_factory=list)
    above_high: List[float] = field(default_factory=list)
    above_price: List[float] = field(default_factory=list)
    above_type: List[int] = field(default_factory=list)
    above_source: List[int] = field(default_factory=list)

    # BELOW
    below_low: List[float] = field(default_factory=list)
    below_high: List[float] = field(default_factory=list)
    below_price: List[float] = field(default_factory=list)
    below_type: List[int] = field(default_factory=list)
    below_source: List[int] = field(default_factory=list)


def collect_final_candidates(
    # ------------------------------------------------------------------
    # REAL ABOVE LAYERS
    # ------------------------------------------------------------------
    above_layer_anchor_low: List[Optional[float]],
    above_layer_anchor_high: List[Optional[float]],
    above_layer_anchor: List[int],

    # ------------------------------------------------------------------
    # ABOVE PSEUDO-ZONES
    # ------------------------------------------------------------------
    above_pseudo_low: List[float],
    above_pseudo_high: List[float],
    above_pseudo_anchor: List[int],

    # ------------------------------------------------------------------
    # REMAINING ABOVE POINTS
    # ------------------------------------------------------------------
    above_position_anchor: List[int],
    anchor_above_valid: List[bool],
    anchor_above_layer: List[int],
    anchor_above_is_zone: List[bool],
    anchor_above_low: List[Optional[float]],

    # ------------------------------------------------------------------
    # REAL BELOW LAYERS
    # ------------------------------------------------------------------
    below_layer_anchor_low: List[Optional[float]],
    below_layer_anchor_high: List[Optional[float]],
    below_layer_anchor: List[int],

    # ------------------------------------------------------------------
    # BELOW PSEUDO-ZONES
    # ------------------------------------------------------------------
    below_pseudo_low: List[float],
    below_pseudo_high: List[float],
    below_pseudo_anchor: List[int],

    # ------------------------------------------------------------------
    # REMAINING BELOW POINTS
    # ------------------------------------------------------------------
    below_position_anchor: List[int],
    anchor_below_valid: List[bool],
    anchor_below_layer: List[int],
    anchor_below_is_zone: List[bool],
    anchor_below_high: List[Optional[float]],
) -> FinalCandidatePool:

    result = FinalCandidatePool()

    # ==================================================================
    # ABOVE
    # ==================================================================

    # ------------------------------------------------------------------
    # REAL ZONE LAYERS
    # ------------------------------------------------------------------

    for layer_index in range(len(above_layer_anchor)):

        candidate_low = above_layer_anchor_low[layer_index]
        candidate_high = above_layer_anchor_high[layer_index]
        candidate_source = above_layer_anchor[layer_index]

        if candidate_low is not None and candidate_high is not None:

            result.above_low.append(candidate_low)
            result.above_high.append(candidate_high)
            result.above_price.append(
                (candidate_low + candidate_high) / 2.0
            )
            result.above_type.append(
                OP_FINAL_CANDIDATE_ZONE
            )
            result.above_source.append(candidate_source)

    # ------------------------------------------------------------------
    # PSEUDO-ZONES
    # ------------------------------------------------------------------

    for pseudo_index in range(len(above_pseudo_low)):

        candidate_low = above_pseudo_low[pseudo_index]
        candidate_high = above_pseudo_high[pseudo_index]
        candidate_source = above_pseudo_anchor[pseudo_index]

        if candidate_low is not None and candidate_high is not None:

            result.above_low.append(candidate_low)
            result.above_high.append(candidate_high)
            result.above_price.append(
                (candidate_low + candidate_high) / 2.0
            )
            result.above_type.append(
                OP_FINAL_CANDIDATE_PSEUDO
            )
            result.above_source.append(candidate_source)

    # ------------------------------------------------------------------
    # REMAINING UNCONSUMED POINTS
    # ------------------------------------------------------------------

    for position_index in range(len(above_position_anchor)):

        candidate_anchor = above_position_anchor[position_index]

        candidate_valid = anchor_above_valid[candidate_anchor]
        candidate_ownership = anchor_above_layer[candidate_anchor]
        candidate_is_zone = anchor_above_is_zone[candidate_anchor]
        candidate_price = anchor_above_low[candidate_anchor]

        if (
            candidate_valid
            and candidate_ownership == -1
            and not candidate_is_zone
            and candidate_price is not None
        ):
            result.above_low.append(candidate_price)
            result.above_high.append(candidate_price)
            result.above_price.append(candidate_price)
            result.above_type.append(
                OP_FINAL_CANDIDATE_POINT
            )
            result.above_source.append(candidate_anchor)

    # ==================================================================
    # BELOW
    # ==================================================================

    # ------------------------------------------------------------------
    # REAL ZONE LAYERS
    # ------------------------------------------------------------------

    for layer_index in range(len(below_layer_anchor)):

        candidate_low = below_layer_anchor_low[layer_index]
        candidate_high = below_layer_anchor_high[layer_index]
        candidate_source = below_layer_anchor[layer_index]

        if candidate_low is not None and candidate_high is not None:

            result.below_low.append(candidate_low)
            result.below_high.append(candidate_high)
            result.below_price.append(
                (candidate_low + candidate_high) / 2.0
            )
            result.below_type.append(
                OP_FINAL_CANDIDATE_ZONE
            )
            result.below_source.append(candidate_source)

    # ------------------------------------------------------------------
    # PSEUDO-ZONES
    # ------------------------------------------------------------------

    for pseudo_index in range(len(below_pseudo_low)):

        candidate_low = below_pseudo_low[pseudo_index]
        candidate_high = below_pseudo_high[pseudo_index]
        candidate_source = below_pseudo_anchor[pseudo_index]

        if candidate_low is not None and candidate_high is not None:

            result.below_low.append(candidate_low)
            result.below_high.append(candidate_high)
            result.below_price.append(
                (candidate_low + candidate_high) / 2.0
            )
            result.below_type.append(
                OP_FINAL_CANDIDATE_PSEUDO
            )
            result.below_source.append(candidate_source)

    # ------------------------------------------------------------------
    # REMAINING UNCONSUMED POINTS
    # ------------------------------------------------------------------

    for position_index in range(len(below_position_anchor)):

        candidate_anchor = below_position_anchor[position_index]

        candidate_valid = anchor_below_valid[candidate_anchor]
        candidate_ownership = anchor_below_layer[candidate_anchor]
        candidate_is_zone = anchor_below_is_zone[candidate_anchor]
        candidate_price = anchor_below_high[candidate_anchor]

        if (
            candidate_valid
            and candidate_ownership == -1
            and not candidate_is_zone
            and candidate_price is not None
        ):
            result.below_low.append(candidate_price)
            result.below_high.append(candidate_price)
            result.below_price.append(candidate_price)
            result.below_type.append(
                OP_FINAL_CANDIDATE_POINT
            )
            result.below_source.append(candidate_anchor)

    return result