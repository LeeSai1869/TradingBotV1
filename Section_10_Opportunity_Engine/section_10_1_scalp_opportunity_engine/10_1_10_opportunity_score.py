from dataclasses import dataclass
from typing import List, Optional, Any


# ============================================================
# 10.1.11 OPPORTUNITY FAMILY SCORES
# ============================================================

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


# ============================================================
# 10.1.15 OPPORTUNITY OUTPUT
# ============================================================
#
# This intentionally uses the ORIGINAL Pine-style field names.
#
# The downstream ScalpOpportunityScorePacket expects exactly
# these fields.
#
# ============================================================

@dataclass
class ScalpOpportunityOutput:
    opportunityLayer1Score: Optional[float] = None
    opportunityLayer2Score: Optional[float] = None
    opportunityLayer3Score: Optional[float] = None

    opportunityLayer1Price: Optional[float] = None
    opportunityLayer2Price: Optional[float] = None
    opportunityLayer3Price: Optional[float] = None

    opportunityLayer1Pct: Optional[float] = None
    opportunityLayer2Pct: Optional[float] = None
    opportunityLayer3Pct: Optional[float] = None

    opportunityLayerNegativePrice: Optional[float] = None
    opportunityLayerNegativePct: Optional[float] = None


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _price_pct(
    price: Optional[float],
    close: Optional[float]
) -> Optional[float]:

    if price is None or close is None:
        return None

    if close == 0:
        return None

    return (price - close) / close * 100.0


def _layer_center(
    final_low: List[float],
    final_high: List[float],
    index: int
) -> Optional[float]:

    if len(final_low) <= index:
        return None

    if len(final_high) <= index:
        return None

    low = _safe_float(final_low[index])
    high = _safe_float(final_high[index])

    if low is None or high is None:
        return None

    return (low + high) / 2.0


def _get_family_score(
    family: Any,
    opportunity_family_score: List[float]
) -> float:

    try:
        family_index = int(family)
    except (TypeError, ValueError):
        return 0.0

    if family_index < 0:
        return 0.0

    if family_index >= len(opportunity_family_score):
        return 0.0

    return opportunity_family_score[family_index]


# ============================================================
# 10.1.11 OPPORTUNITY FAMILY SCORES
# ============================================================

def build_opportunity_family_scores(
    op_score_liquidity: float,
    op_score_order_block: float,
    op_score_breaker: float,
    op_score_volume_profile: float,
    op_score_swinghl: float,
    op_score_sessionhl: float,
    op_score_ema: float,
    op_score_vwap: float,
    op_score_wma: float,
    op_score_protectedhl: float,
    op_score_fibonacci: float,
    op_score_sr: float,
    op_score_fvg: float,
    op_score_hlvn: float,
) -> List[float]:

    # Exact Pine family ordering.
    return [
        op_score_liquidity,       # 0
        op_score_order_block,     # 1
        op_score_breaker,         # 2
        op_score_volume_profile,  # 3
        op_score_swinghl,         # 4
        op_score_sessionhl,       # 5
        op_score_ema,             # 6
        op_score_vwap,            # 7
        op_score_wma,             # 8
        op_score_protectedhl,     # 9
        op_score_fibonacci,       # 10
        op_score_sr,              # 11
        op_score_fvg,             # 12
        op_score_hlvn,            # 13
    ]


# ============================================================
# 10.1.12 OPPORTUNITY LAYER SCORES
# ============================================================

def calculate_opportunity_layer_scores(
    opportunityAboveCombinedLayer: List[int],
    opportunityAboveCombinedFamily: List[int],

    opportunityBelowCombinedLayer: List[int],
    opportunityBelowCombinedFamily: List[int],

    opportunityFamilyScore: List[float],
):
    """
    One score is attached to each already-combined family.

    The combined family/layer indexes remain synchronized.
    """

    # --------------------------------------------------------
    # ABOVE
    # --------------------------------------------------------

    opportunityAboveLayer1Score = 0.0
    opportunityAboveLayer2Score = 0.0
    opportunityAboveLayer3Score = 0.0

    if len(opportunityAboveCombinedFamily) > 0:

        for i in range(len(opportunityAboveCombinedFamily)):

            family = opportunityAboveCombinedFamily[i]

            if i >= len(opportunityAboveCombinedLayer):
                continue

            layer = opportunityAboveCombinedLayer[i]

            familyScore = _get_family_score(
                family,
                opportunityFamilyScore
            )

            if layer == 1:
                opportunityAboveLayer1Score += familyScore

            elif layer == 2:
                opportunityAboveLayer2Score += familyScore

            elif layer == 3:
                opportunityAboveLayer3Score += familyScore

    # --------------------------------------------------------
    # BELOW
    # --------------------------------------------------------

    opportunityBelowLayer1Score = 0.0
    opportunityBelowLayer2Score = 0.0
    opportunityBelowLayer3Score = 0.0

    if len(opportunityBelowCombinedFamily) > 0:

        for i in range(len(opportunityBelowCombinedFamily)):

            family = opportunityBelowCombinedFamily[i]

            if i >= len(opportunityBelowCombinedLayer):
                continue

            layer = opportunityBelowCombinedLayer[i]

            familyScore = _get_family_score(
                family,
                opportunityFamilyScore
            )

            if layer == 1:
                opportunityBelowLayer1Score += familyScore

            elif layer == 2:
                opportunityBelowLayer2Score += familyScore

            elif layer == 3:
                opportunityBelowLayer3Score += familyScore

    return (
        opportunityAboveLayer1Score,
        opportunityAboveLayer2Score,
        opportunityAboveLayer3Score,

        opportunityBelowLayer1Score,
        opportunityBelowLayer2Score,
        opportunityBelowLayer3Score,
    )


# ============================================================
# 10.1.13 OPPORTUNITY LAYER DISTANCES
# ============================================================

def calculate_opportunity_layer_distances(
    opportunityAboveFinalLow: List[float],
    opportunityAboveFinalHigh: List[float],

    opportunityBelowFinalLow: List[float],
    opportunityBelowFinalHigh: List[float],

    current_close: Optional[float],
):
    """
    Calculates the center price and percentage distance of
    each opportunity layer.

    The original Pine negative-layer behavior is preserved.
    """

    # ========================================================
    # ABOVE
    # ========================================================

    aboveLayer1OpportunityPct = None
    aboveLayer2OpportunityPct = None
    aboveLayer3OpportunityPct = None

    aboveLayer1OpportunityPrice = None
    aboveLayer2OpportunityPrice = None
    aboveLayer3OpportunityPrice = None

    aboveLayerNegativePct = None
    aboveLayerNegativePrice = None

    # --------------------------------------------------------
    # ABOVE LAYER 1
    # --------------------------------------------------------

    if len(opportunityAboveFinalLow) >= 1:

        layerCenter = _layer_center(
            opportunityAboveFinalLow,
            opportunityAboveFinalHigh,
            0
        )

        aboveLayer1OpportunityPrice = layerCenter

        aboveLayer1OpportunityPct = _price_pct(
            layerCenter,
            current_close
        )

    # --------------------------------------------------------
    # ABOVE LAYER 2
    # --------------------------------------------------------

    if len(opportunityAboveFinalLow) >= 2:

        layerCenter = _layer_center(
            opportunityAboveFinalLow,
            opportunityAboveFinalHigh,
            1
        )

        aboveLayer2OpportunityPrice = layerCenter

        aboveLayer2OpportunityPct = _price_pct(
            layerCenter,
            current_close
        )

    # --------------------------------------------------------
    # ABOVE LAYER 3
    # --------------------------------------------------------

    if len(opportunityAboveFinalLow) >= 3:

        layerCenter = _layer_center(
            opportunityAboveFinalLow,
            opportunityAboveFinalHigh,
            2
        )

        aboveLayer3OpportunityPrice = layerCenter

        aboveLayer3OpportunityPct = _price_pct(
            layerCenter,
            current_close
        )

    # --------------------------------------------------------
    # ABOVE NEGATIVE
    #
    # Exact Pine behavior:
    #
    # if array.size(opportunityBelowFinalHigh) >= 1
    #     aboveLayerNegativePrice :=
    #         array.get(opportunityBelowFinalHigh, 0)
    # --------------------------------------------------------

    if len(opportunityBelowFinalHigh) >= 1:

        aboveLayerNegativePrice = _safe_float(
            opportunityBelowFinalHigh[0]
        )

        aboveLayerNegativePct = _price_pct(
            aboveLayerNegativePrice,
            current_close
        )

    # ========================================================
    # BELOW
    # ========================================================

    belowLayer1OpportunityPct = None
    belowLayer2OpportunityPct = None
    belowLayer3OpportunityPct = None

    belowLayer1OpportunityPrice = None
    belowLayer2OpportunityPrice = None
    belowLayer3OpportunityPrice = None

    belowLayerNegativePct = None
    belowLayerNegativePrice = None

    # --------------------------------------------------------
    # BELOW LAYER 1
    # --------------------------------------------------------

    if len(opportunityBelowFinalLow) >= 1:

        layerCenter = _layer_center(
            opportunityBelowFinalLow,
            opportunityBelowFinalHigh,
            0
        )

        belowLayer1OpportunityPrice = layerCenter

        belowLayer1OpportunityPct = _price_pct(
            layerCenter,
            current_close
        )

    # --------------------------------------------------------
    # BELOW LAYER 2
    # --------------------------------------------------------

    if len(opportunityBelowFinalLow) >= 2:

        layerCenter = _layer_center(
            opportunityBelowFinalLow,
            opportunityBelowFinalHigh,
            1
        )

        belowLayer2OpportunityPrice = layerCenter

        belowLayer2OpportunityPct = _price_pct(
            layerCenter,
            current_close
        )

    # --------------------------------------------------------
    # BELOW LAYER 3
    # --------------------------------------------------------

    if len(opportunityBelowFinalLow) >= 3:

        layerCenter = _layer_center(
            opportunityBelowFinalLow,
            opportunityBelowFinalHigh,
            2
        )

        belowLayer3OpportunityPrice = layerCenter

        belowLayer3OpportunityPct = _price_pct(
            layerCenter,
            current_close
        )

    # --------------------------------------------------------
    # BELOW NEGATIVE
    #
    # IMPORTANT:
    # This preserves the supplied Pine condition exactly:
    #
    # if array.size(opportunityAboveFinalLow) >= 3
    #     belowLayerNegativePrice :=
    #         array.get(opportunityAboveFinalLow, 0)
    #
    # --------------------------------------------------------

    if len(opportunityAboveFinalLow) >= 3:

        belowLayerNegativePrice = _safe_float(
            opportunityAboveFinalLow[0]
        )

        belowLayerNegativePct = _price_pct(
            belowLayerNegativePrice,
            current_close
        )

    return (
        aboveLayer1OpportunityPrice,
        aboveLayer2OpportunityPrice,
        aboveLayer3OpportunityPrice,

        aboveLayer1OpportunityPct,
        aboveLayer2OpportunityPct,
        aboveLayer3OpportunityPct,

        aboveLayerNegativePrice,
        aboveLayerNegativePct,

        belowLayer1OpportunityPrice,
        belowLayer2OpportunityPrice,
        belowLayer3OpportunityPrice,

        belowLayer1OpportunityPct,
        belowLayer2OpportunityPct,
        belowLayer3OpportunityPct,

        belowLayerNegativePrice,
        belowLayerNegativePct,
    )


# ============================================================
# 10.1.14 OPPORTUNITY BUY / SELL TRIGGER CONTEXT
# ============================================================

def apply_opportunity_decision_context(
    decision: Any,

    opportunityAboveLayer1Score: float,
    opportunityAboveLayer2Score: float,
    opportunityAboveLayer3Score: float,

    aboveLayer1OpportunityPrice: Optional[float],
    aboveLayer2OpportunityPrice: Optional[float],
    aboveLayer3OpportunityPrice: Optional[float],

    aboveLayer1OpportunityPct: Optional[float],
    aboveLayer2OpportunityPct: Optional[float],
    aboveLayer3OpportunityPct: Optional[float],

    aboveLayerNegativePrice: Optional[float],
    aboveLayerNegativePct: Optional[float],

    opportunityBelowLayer1Score: float,
    opportunityBelowLayer2Score: float,
    opportunityBelowLayer3Score: float,

    belowLayer1OpportunityPrice: Optional[float],
    belowLayer2OpportunityPrice: Optional[float],
    belowLayer3OpportunityPrice: Optional[float],

    belowLayer1OpportunityPct: Optional[float],
    belowLayer2OpportunityPct: Optional[float],
    belowLayer3OpportunityPct: Optional[float],

    belowLayerNegativePrice: Optional[float],
    belowLayerNegativePct: Optional[float],
):
    """
    Decision Engine gate.

    BUY:
        ABOVE = opportunity
        BELOW = negative

    SELL:
        BELOW = opportunity
        ABOVE = negative
    """

    opportunityBuyTrigger = False
    opportunitySellTrigger = False

    opportunityLayer1Score = None
    opportunityLayer2Score = None
    opportunityLayer3Score = None

    opportunityLayer1Price = None
    opportunityLayer2Price = None
    opportunityLayer3Price = None

    opportunityLayer1Pct = None
    opportunityLayer2Pct = None
    opportunityLayer3Pct = None

    opportunityLayerNegativePrice = None
    opportunityLayerNegativePct = None

    decision_text = "" if decision is None else str(decision)

    # ========================================================
    # DECISION ENGINE GATE
    # ========================================================

    if "BUY" in decision_text or "SELL" in decision_text:

        # ====================================================
        # BUY
        # ====================================================

        if "BUY" in decision_text:

            opportunityBuyTrigger = True

            opportunityLayer1Score = opportunityAboveLayer1Score
            opportunityLayer2Score = opportunityAboveLayer2Score
            opportunityLayer3Score = opportunityAboveLayer3Score

            opportunityLayer1Price = aboveLayer1OpportunityPrice
            opportunityLayer2Price = aboveLayer2OpportunityPrice
            opportunityLayer3Price = aboveLayer3OpportunityPrice

            opportunityLayer1Pct = aboveLayer1OpportunityPct
            opportunityLayer2Pct = aboveLayer2OpportunityPct
            opportunityLayer3Pct = aboveLayer3OpportunityPct

            opportunityLayerNegativePrice = (
                aboveLayerNegativePrice
            )

            opportunityLayerNegativePct = (
                aboveLayerNegativePct
            )

        # ====================================================
        # SELL
        # ====================================================

        if "SELL" in decision_text:

            opportunitySellTrigger = True

            opportunityLayer1Score = opportunityBelowLayer1Score
            opportunityLayer2Score = opportunityBelowLayer2Score
            opportunityLayer3Score = opportunityBelowLayer3Score

            opportunityLayer1Price = belowLayer1OpportunityPrice
            opportunityLayer2Price = belowLayer2OpportunityPrice
            opportunityLayer3Price = belowLayer3OpportunityPrice

            opportunityLayer1Pct = belowLayer1OpportunityPct
            opportunityLayer2Pct = belowLayer2OpportunityPct
            opportunityLayer3Pct = belowLayer3OpportunityPct

            opportunityLayerNegativePrice = (
                belowLayerNegativePrice
            )

            opportunityLayerNegativePct = (
                belowLayerNegativePct
            )

    return (
        opportunityBuyTrigger,
        opportunitySellTrigger,

        opportunityLayer1Score,
        opportunityLayer2Score,
        opportunityLayer3Score,

        opportunityLayer1Price,
        opportunityLayer2Price,
        opportunityLayer3Price,

        opportunityLayer1Pct,
        opportunityLayer2Pct,
        opportunityLayer3Pct,

        opportunityLayerNegativePrice,
        opportunityLayerNegativePct,
    )


# ============================================================
# 10.1.10 OPPORTUNITY SCORE ENGINE
# ============================================================

def calculate_opportunity_score(
    *,
    decision: Any,
    current_close: Optional[float],

    opportunityAboveCombinedLayer: List[int],
    opportunityAboveCombinedFamily: List[int],

    opportunityBelowCombinedLayer: List[int],
    opportunityBelowCombinedFamily: List[int],

    opportunityAboveFinalLow: List[float],
    opportunityAboveFinalHigh: List[float],

    opportunityBelowFinalLow: List[float],
    opportunityBelowFinalHigh: List[float],

    op_score_liquidity: float,
    op_score_order_block: float,
    op_score_breaker: float,
    op_score_volume_profile: float,
    op_score_swinghl: float,
    op_score_sessionhl: float,
    op_score_ema: float,
    op_score_vwap: float,
    op_score_wma: float,
    op_score_protectedhl: float,
    op_score_fibonacci: float,
    op_score_sr: float,
    op_score_fvg: float,
    op_score_hlvn: float,
) -> ScalpOpportunityOutput:
    """
    Complete 10.1.11 → 10.1.15 Opportunity Score stage.

    Input:
        10.1.9 Final Layers
        10.1.10 Combine output / combined arrays

    Output:
        ScalpOpportunityOutput

    The returned object is deliberately compatible with:

        create_scalp_opportunity_score_packet(...)
    """

    # ========================================================
    # 10.1.11
    # ========================================================

    opportunityFamilyScore = build_opportunity_family_scores(
        op_score_liquidity,
        op_score_order_block,
        op_score_breaker,
        op_score_volume_profile,
        op_score_swinghl,
        op_score_sessionhl,
        op_score_ema,
        op_score_vwap,
        op_score_wma,
        op_score_protectedhl,
        op_score_fibonacci,
        op_score_sr,
        op_score_fvg,
        op_score_hlvn,
    )

    # ========================================================
    # 10.1.12
    # ========================================================

    (
        opportunityAboveLayer1Score,
        opportunityAboveLayer2Score,
        opportunityAboveLayer3Score,

        opportunityBelowLayer1Score,
        opportunityBelowLayer2Score,
        opportunityBelowLayer3Score,

    ) = calculate_opportunity_layer_scores(
        opportunityAboveCombinedLayer,
        opportunityAboveCombinedFamily,

        opportunityBelowCombinedLayer,
        opportunityBelowCombinedFamily,

        opportunityFamilyScore,
    )

    # ========================================================
    # 10.1.13
    # ========================================================

    (
        aboveLayer1OpportunityPrice,
        aboveLayer2OpportunityPrice,
        aboveLayer3OpportunityPrice,

        aboveLayer1OpportunityPct,
        aboveLayer2OpportunityPct,
        aboveLayer3OpportunityPct,

        aboveLayerNegativePrice,
        aboveLayerNegativePct,

        belowLayer1OpportunityPrice,
        belowLayer2OpportunityPrice,
        belowLayer3OpportunityPrice,

        belowLayer1OpportunityPct,
        belowLayer2OpportunityPct,
        belowLayer3OpportunityPct,

        belowLayerNegativePrice,
        belowLayerNegativePct,

    ) = calculate_opportunity_layer_distances(
        opportunityAboveFinalLow,
        opportunityAboveFinalHigh,

        opportunityBelowFinalLow,
        opportunityBelowFinalHigh,

        current_close,
    )

    # ========================================================
    # 10.1.14
    # ========================================================

    (
        opportunityBuyTrigger,
        opportunitySellTrigger,

        opportunityLayer1Score,
        opportunityLayer2Score,
        opportunityLayer3Score,

        opportunityLayer1Price,
        opportunityLayer2Price,
        opportunityLayer3Price,

        opportunityLayer1Pct,
        opportunityLayer2Pct,
        opportunityLayer3Pct,

        opportunityLayerNegativePrice,
        opportunityLayerNegativePct,

    ) = apply_opportunity_decision_context(

        decision,

        opportunityAboveLayer1Score,
        opportunityAboveLayer2Score,
        opportunityAboveLayer3Score,

        aboveLayer1OpportunityPrice,
        aboveLayer2OpportunityPrice,
        aboveLayer3OpportunityPrice,

        aboveLayer1OpportunityPct,
        aboveLayer2OpportunityPct,
        aboveLayer3OpportunityPct,

        aboveLayerNegativePrice,
        aboveLayerNegativePct,

        opportunityBelowLayer1Score,
        opportunityBelowLayer2Score,
        opportunityBelowLayer3Score,

        belowLayer1OpportunityPrice,
        belowLayer2OpportunityPrice,
        belowLayer3OpportunityPrice,

        belowLayer1OpportunityPct,
        belowLayer2OpportunityPct,
        belowLayer3OpportunityPct,

        belowLayerNegativePrice,
        belowLayerNegativePct,
    )

    # ========================================================
    # 10.1.15 OUTPUT
    # ========================================================
    #
    # IMPORTANT:
    #
    # Return the ORIGINAL Pine output contract.
    #
    # The packet adapter can now consume this directly.
    #
    # ========================================================

    return ScalpOpportunityOutput(
        opportunityLayer1Score=opportunityLayer1Score,
        opportunityLayer2Score=opportunityLayer2Score,
        opportunityLayer3Score=opportunityLayer3Score,

        opportunityLayer1Price=opportunityLayer1Price,
        opportunityLayer2Price=opportunityLayer2Price,
        opportunityLayer3Price=opportunityLayer3Price,

        opportunityLayer1Pct=opportunityLayer1Pct,
        opportunityLayer2Pct=opportunityLayer2Pct,
        opportunityLayer3Pct=opportunityLayer3Pct,

        opportunityLayerNegativePrice=(
            opportunityLayerNegativePrice
        ),

        opportunityLayerNegativePct=(
            opportunityLayerNegativePct
        ),
    )