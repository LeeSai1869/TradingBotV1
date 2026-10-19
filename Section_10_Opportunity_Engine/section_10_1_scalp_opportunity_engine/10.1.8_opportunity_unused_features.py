from dataclasses import dataclass
from typing import Any, List


# ============================================================
# 10.1.9 UNUSED FEATURES
# ============================================================
#
# Purpose:
#   Enrich each finalized ABOVE / BELOW opportunity layer with
#   unused feature references that fall inside the layer's
#   frozen authority range.
#
# Important:
#   - This is an INTERNAL stage result, not a packet.
#   - Feature values come from the Market Features Packet.
#   - Persistent SR/FVG arrays come from Global Core memory.
#   - Final layer arrays come from 10.1.8.
#   - Ordering follows the original Pine implementation.
#   - No deduplication is performed.
#   - No scoring is performed here.
# ============================================================


# ------------------------------------------------------------
# FAMILY IDS
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# INTERNAL RESULT
# ------------------------------------------------------------

@dataclass
class OpportunityUnusedFeaturesResult:
    above_layer: List[int]
    above_family: List[int]
    above_price: List[float]

    below_layer: List[int]
    below_family: List[int]
    below_price: List[float]


# ------------------------------------------------------------
# BASIC HELPERS
# ------------------------------------------------------------

def _is_valid(value: Any) -> bool:
    """
    Pine equivalent of:

        not na(value)

    Also treats Python NaN as unavailable.
    """
    if value is None:
        return False

    try:
        return value == value
    except Exception:
        return True


def _in_range(value: Any, low: float, high: float) -> bool:
    """
    Pine equivalent of:

        not na(value) and
        value >= layerExtremeLow and
        value <= layerExtremeHigh
    """
    return (
        _is_valid(value)
        and value >= low
        and value <= high
    )


def _overlaps(
    zone_low: Any,
    zone_high: Any,
    layer_low: float,
    layer_high: float,
) -> bool:
    """
    Pine equivalent of:

        not na(zone_low)
        and not na(zone_high)
        and zone_low <= layerExtremeHigh
        and zone_high >= layerExtremeLow
    """
    return (
        _is_valid(zone_low)
        and _is_valid(zone_high)
        and zone_low <= layer_high
        and zone_high >= layer_low
    )


def _push(
    layer_array: List[int],
    family_array: List[int],
    price_array: List[float],
    layer_index: int,
    family: int,
    price: float,
) -> None:
    """
    Equivalent to the three Pine array.push() calls.

    Kept as one helper only to avoid repeating the same three
    Python operations hundreds of times.
    """
    layer_array.append(layer_index)
    family_array.append(family)
    price_array.append(price)


# ------------------------------------------------------------
# MAIN STAGE
# ------------------------------------------------------------

def collect_unused_features(
    f,
    global_core_packet,
    opportunity_above_final_low,
    opportunity_above_final_high,
    opportunity_above_final_authority_low,
    opportunity_above_final_authority_high,
    opportunity_below_final_low,
    opportunity_below_final_high,
    opportunity_below_final_authority_low,
    opportunity_below_final_authority_high,
) -> OpportunityUnusedFeaturesResult:
    """
    10.1.9 UNUSED FEATURES

    Inputs
    ------
    f:
        Market Features Packet.

    global_core_packet:
        Global Core Packet. It must expose the redesigned
        persistent global memory through:

            global_core_packet.global_memory

    Final layer arrays:
        Produced by 10.1.8 Final Layers.

    Returns
    -------
    OpportunityUnusedFeaturesResult

    Contains the exact three ABOVE and three BELOW enrichment
    arrays corresponding to the original Pine implementation.
    """

    # ========================================================
    # OUTPUT ARRAYS
    # ========================================================

    opportunityAboveEnrichmentLayer: List[int] = []
    opportunityAboveEnrichmentFamily: List[int] = []
    opportunityAboveEnrichmentPrice: List[float] = []

    opportunityBelowEnrichmentLayer: List[int] = []
    opportunityBelowEnrichmentFamily: List[int] = []
    opportunityBelowEnrichmentPrice: List[float] = []

    # ========================================================
    # GLOBAL MEMORY
    # ========================================================

    global_memory = global_core_packet.global_memory

    # Redesigned GlobalLifecycleMemory
    fvg_memory = global_memory.fvg
    sr_memory = global_memory.sr

    # ========================================================
    # CONSTANT FIBONACCI RATIOS
    # ========================================================

    fib_enrichment_ratios = (
        0.236,
        0.382,
        0.500,
        0.618,
        0.786,
    )

    fib_extension_ratios = (
        1.000,
        1.272,
        1.414,
        1.618,
        2.000,
        2.618,
    )

    # ========================================================
    # ABOVE PRICE
    # ========================================================

    above_final_layer_count = len(opportunity_above_final_low)

    if above_final_layer_count > 0:

        for layer_index in range(above_final_layer_count):

            # ------------------------------------------------
            # FINAL LAYER / AUTHORITY RANGE
            # ------------------------------------------------

            layerFinalLow = opportunity_above_final_low[layer_index]
            layerFinalHigh = opportunity_above_final_high[layer_index]

            layerExtremeLow = (
                opportunity_above_final_authority_low[layer_index]
            )

            layerExtremeHigh = (
                opportunity_above_final_authority_high[layer_index]
            )

            # Preserve the original Pine reads.
            # layerFinalLow / layerFinalHigh are intentionally
            # not used below because the source code uses the
            # frozen authority range for all tests.
            _ = layerFinalLow
            _ = layerFinalHigh

            # =================================================
            # LIQUIDITY
            # =================================================

            recentHighLiquidityInLayer = _in_range(
                f.recentHighLiquidity,
                layerExtremeLow,
                layerExtremeHigh,
            )

            prevHighLiquidityInLayer = _in_range(
                f.prevHighLiquidity,
                layerExtremeLow,
                layerExtremeHigh,
            )

            externalHighLiquidityInLayer = _in_range(
                f.externalHighLiquidity,
                layerExtremeLow,
                layerExtremeHigh,
            )

            internalHighLiquidityInLayer = _in_range(
                f.internalHighLiquidity,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if recentHighLiquidityInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_LIQUIDITY,
                    f.recentHighLiquidity,
                )

            if prevHighLiquidityInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_LIQUIDITY,
                    f.prevHighLiquidity,
                )

            if externalHighLiquidityInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_LIQUIDITY,
                    f.externalHighLiquidity,
                )

            if internalHighLiquidityInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_LIQUIDITY,
                    f.internalHighLiquidity,
                )

            # =================================================
            # ORDER BLOCKS
            # =================================================

            bearOBOverlapsLayer = _overlaps(
                f.activeBearOBLow,
                f.activeBearOBHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            strictBearOBOverlapsLayer = _overlaps(
                f.activeStrictBearOBLow,
                f.activeStrictBearOBHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if bearOBOverlapsLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_ORDER_BLOCK,
                    (
                        f.activeBearOBLow
                        + f.activeBearOBHigh
                    ) / 2.0,
                )

            if strictBearOBOverlapsLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_ORDER_BLOCK,
                    (
                        f.activeStrictBearOBLow
                        + f.activeStrictBearOBHigh
                    ) / 2.0,
                )

            # =================================================
            # BREAKERS
            # =================================================

            bullBreakerOverlapsLayer = (
                bool(f.bullBreakerActive)
                and _overlaps(
                    f.activeBullBreakerLow,
                    f.activeBullBreakerHigh,
                    layerExtremeLow,
                    layerExtremeHigh,
                )
            )

            strictBullBreakerOverlapsLayer = (
                bool(f.strictBullBreakerActive)
                and _overlaps(
                    f.activeStrictBullBreakerLow,
                    f.activeStrictBullBreakerHigh,
                    layerExtremeLow,
                    layerExtremeHigh,
                )
            )

            if bullBreakerOverlapsLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_BREAKER,
                    (
                        f.activeBullBreakerLow
                        + f.activeBullBreakerHigh
                    ) / 2.0,
                )

            if strictBullBreakerOverlapsLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_BREAKER,
                    f.activeStrictBullBreakerLow,
                )

            # =================================================
            # VOLUME PROFILE
            # =================================================

            pocInLayer = _in_range(
                f.vpPOC,
                layerExtremeLow,
                layerExtremeHigh,
            )

            vahInLayer = _in_range(
                f.vpVAHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if pocInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_VOLUME_PROFILE,
                    f.vpPOC,
                )

            if vahInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_VOLUME_PROFILE,
                    f.vpVAHigh,
                )

            # =================================================
            # HVN / LVN
            # =================================================

            hvnOverlapsLayer = _overlaps(
                f.vpHVNLow,
                f.vpHVNHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            lvnOverlapsLayer = _overlaps(
                f.vpLVNLow,
                f.vpLVNHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if hvnOverlapsLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_HLVN,
                    (
                        f.vpHVNLow
                        + f.vpHVNHigh
                    ) / 2.0,
                )

            if lvnOverlapsLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_HLVN,
                    (
                        f.vpLVNLow
                        + f.vpLVNHigh
                    ) / 2.0,
                )

            # =================================================
            # SWING LOCATION
            # =================================================

            swingHighInLayer = _in_range(
                f.latestSwingHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if swingHighInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_SWINGHL,
                    f.latestSwingHigh,
                )

            # =================================================
            # SESSION HIGHS
            # =================================================

            asiaHighInLayer = _in_range(
                f.asiaHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            londonHighInLayer = _in_range(
                f.londonHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            newYorkHighInLayer = _in_range(
                f.newYorkHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if asiaHighInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_SESSIONHL,
                    f.asiaHigh,
                )

            if londonHighInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_SESSIONHL,
                    f.londonHigh,
                )

            if newYorkHighInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_SESSIONHL,
                    f.newYorkHigh,
                )

            # =================================================
            # EMA
            # =================================================

            ema_values = (
                f.ema7,
                f.ema25,
                f.ema50,
                f.ema100,
                f.ema200,
                f.ema300,
            )

            for ema_value in ema_values:
                if _in_range(
                    ema_value,
                    layerExtremeLow,
                    layerExtremeHigh,
                ):
                    _push(
                        opportunityAboveEnrichmentLayer,
                        opportunityAboveEnrichmentFamily,
                        opportunityAboveEnrichmentPrice,
                        layer_index,
                        FAMILY_EMA,
                        ema_value,
                    )

            # =================================================
            # VWAP
            # =================================================

            vwap_values = (
                f.vwapLower2,
                f.vwapLower1,
                f.vwapValue,
                f.vwapUpper1,
                f.vwapUpper2,
            )

            for vwap_value in vwap_values:
                if _in_range(
                    vwap_value,
                    layerExtremeLow,
                    layerExtremeHigh,
                ):
                    _push(
                        opportunityAboveEnrichmentLayer,
                        opportunityAboveEnrichmentFamily,
                        opportunityAboveEnrichmentPrice,
                        layer_index,
                        FAMILY_VWAP,
                        vwap_value,
                    )

            # =================================================
            # WMA 50
            # =================================================

            wma50InLayer = _in_range(
                f.wma50,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if wma50InLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_WMA,
                    f.wma50,
                )

            # =================================================
            # PROTECTED HIGH
            # =================================================

            protectedHighInLayer = _in_range(
                f.protectedHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if protectedHighInLayer:
                _push(
                    opportunityAboveEnrichmentLayer,
                    opportunityAboveEnrichmentFamily,
                    opportunityAboveEnrichmentPrice,
                    layer_index,
                    FAMILY_PROTECTEDHL,
                    f.protectedHigh,
                )

            # =================================================
            # FIBONACCI RETRACEMENTS
            # =================================================

            if _is_valid(f.fibRange) and f.fibRange > 0:

                for fibRatio in fib_enrichment_ratios:

                    fibPrice = None

                    if f.fibDirection == "BULLISH_LEG":
                        fibPrice = (
                            f.activeFibHigh
                            - f.fibRange * fibRatio
                        )

                    if f.fibDirection == "BEARISH_LEG":
                        fibPrice = (
                            f.activeFibLow
                            + f.fibRange * fibRatio
                        )

                    if _in_range(
                        fibPrice,
                        layerExtremeLow,
                        layerExtremeHigh,
                    ):
                        _push(
                            opportunityAboveEnrichmentLayer,
                            opportunityAboveEnrichmentFamily,
                            opportunityAboveEnrichmentPrice,
                            layer_index,
                            FAMILY_FIBONACCI,
                            fibPrice,
                        )

            # =================================================
            # FIBONACCI EXTENSIONS
            # =================================================

            if _is_valid(f.fibRange) and f.fibRange > 0:

                for fibExtensionRatio in fib_extension_ratios:

                    fibExtensionPrice = None

                    if f.fibDirection == "BULLISH_LEG":
                        fibExtensionPrice = (
                            f.activeFibHigh
                            + f.fibRange
                            * (fibExtensionRatio - 1.0)
                        )

                    if f.fibDirection == "BEARISH_LEG":
                        fibExtensionPrice = (
                            f.activeFibLow
                            - f.fibRange
                            * (fibExtensionRatio - 1.0)
                        )

                    if _in_range(
                        fibExtensionPrice,
                        layerExtremeLow,
                        layerExtremeHigh,
                    ):
                        _push(
                            opportunityAboveEnrichmentLayer,
                            opportunityAboveEnrichmentFamily,
                            opportunityAboveEnrichmentPrice,
                            layer_index,
                            FAMILY_FIBONACCI,
                            fibExtensionPrice,
                        )

            # =================================================
            # RESISTANCE
            # =================================================

            resistance_low_array = sr_memory.resistance_low
            resistance_high_array = sr_memory.resistance_high

            if len(resistance_low_array) > 0:

                for resistanceIndex in range(
                    len(resistance_low_array)
                ):

                    resistanceZoneLow = (
                        resistance_low_array[resistanceIndex]
                    )

                    resistanceZoneHigh = (
                        resistance_high_array[resistanceIndex]
                    )

                    resistanceOverlapsLayer = _overlaps(
                        resistanceZoneLow,
                        resistanceZoneHigh,
                        layerExtremeLow,
                        layerExtremeHigh,
                    )

                    if resistanceOverlapsLayer:
                        _push(
                            opportunityAboveEnrichmentLayer,
                            opportunityAboveEnrichmentFamily,
                            opportunityAboveEnrichmentPrice,
                            layer_index,
                            FAMILY_SR,
                            (
                                resistanceZoneLow
                                + resistanceZoneHigh
                            ) / 2.0,
                        )

            # =================================================
            # BEAR FVG
            # =================================================

            fvg_bear_low = fvg_memory.bear_low
            fvg_bear_high = fvg_memory.bear_high

            if len(fvg_bear_low) > 0:

                for fvgIndex in range(len(fvg_bear_low)):

                    bearFVGLow = fvg_bear_low[fvgIndex]
                    bearFVGHigh = fvg_bear_high[fvgIndex]

                    bearFVGOverlapsLayer = _overlaps(
                        bearFVGLow,
                        bearFVGHigh,
                        layerExtremeLow,
                        layerExtremeHigh,
                    )

                    if bearFVGOverlapsLayer:
                        _push(
                            opportunityAboveEnrichmentLayer,
                            opportunityAboveEnrichmentFamily,
                            opportunityAboveEnrichmentPrice,
                            layer_index,
                            FAMILY_FVG,
                            (
                                bearFVGLow
                                + bearFVGHigh
                            ) / 2.0,
                        )

    # ========================================================
    # BELOW PRICE
    # ========================================================

    below_final_layer_count = len(opportunity_below_final_low)

    if below_final_layer_count > 0:

        for layer_index in range(below_final_layer_count):

            # ------------------------------------------------
            # FINAL LAYER / AUTHORITY RANGE
            # ------------------------------------------------

            layerFinalLow = opportunity_below_final_low[layer_index]
            layerFinalHigh = opportunity_below_final_high[layer_index]

            layerExtremeLow = (
                opportunity_below_final_authority_low[layer_index]
            )

            layerExtremeHigh = (
                opportunity_below_final_authority_high[layer_index]
            )

            # Preserve original Pine reads.
            _ = layerFinalLow
            _ = layerFinalHigh

            # =================================================
            # LIQUIDITY
            # =================================================

            recentLowLiquidityInLayer = _in_range(
                f.recentLowLiquidity,
                layerExtremeLow,
                layerExtremeHigh,
            )

            prevLowLiquidityInLayer = _in_range(
                f.prevLowLiquidity,
                layerExtremeLow,
                layerExtremeHigh,
            )

            externalLowLiquidityInLayer = _in_range(
                f.externalLowLiquidity,
                layerExtremeLow,
                layerExtremeHigh,
            )

            internalLowLiquidityInLayer = _in_range(
                f.internalLowLiquidity,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if recentLowLiquidityInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_LIQUIDITY,
                    f.recentLowLiquidity,
                )

            if prevLowLiquidityInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_LIQUIDITY,
                    f.prevLowLiquidity,
                )

            if externalLowLiquidityInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_LIQUIDITY,
                    f.externalLowLiquidity,
                )

            if internalLowLiquidityInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_LIQUIDITY,
                    f.internalLowLiquidity,
                )

            # =================================================
            # ORDER BLOCKS
            # =================================================

            bullOBOverlapsLayer = _overlaps(
                f.activeBullOBLow,
                f.activeBullOBHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            strictBullOBOverlapsLayer = _overlaps(
                f.activeStrictBullOBLow,
                f.activeStrictBullOBHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if bullOBOverlapsLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_ORDER_BLOCK,
                    (
                        f.activeBullOBLow
                        + f.activeBullOBHigh
                    ) / 2.0,
                )

            if strictBullOBOverlapsLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_ORDER_BLOCK,
                    (
                        f.activeStrictBullOBLow
                        + f.activeStrictBullOBHigh
                    ) / 2.0,
                )

            # =================================================
            # BREAKERS
            # =================================================

            bearBreakerOverlapsLayer = (
                bool(f.bearBreakerActive)
                and _overlaps(
                    f.activeBearBreakerLow,
                    f.activeBearBreakerHigh,
                    layerExtremeLow,
                    layerExtremeHigh,
                )
            )

            strictBearBreakerOverlapsLayer = (
                bool(f.strictBearBreakerActive)
                and _overlaps(
                    f.activeStrictBearBreakerLow,
                    f.activeStrictBearBreakerHigh,
                    layerExtremeLow,
                    layerExtremeHigh,
                )
            )

            if bearBreakerOverlapsLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_BREAKER,
                    (
                        f.activeBearBreakerLow
                        + f.activeBearBreakerHigh
                    ) / 2.0,
                )

            if strictBearBreakerOverlapsLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_BREAKER,
                    f.activeStrictBearBreakerHigh,
                )

            # =================================================
            # VOLUME PROFILE
            # =================================================

            pocInLayer = _in_range(
                f.vpPOC,
                layerExtremeLow,
                layerExtremeHigh,
            )

            valInLayer = _in_range(
                f.vpVALow,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if pocInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_VOLUME_PROFILE,
                    f.vpPOC,
                )

            if valInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_VOLUME_PROFILE,
                    f.vpVALow,
                )

            # =================================================
            # HVN / LVN
            # =================================================

            hvnOverlapsLayer = _overlaps(
                f.vpHVNLow,
                f.vpHVNHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            lvnOverlapsLayer = _overlaps(
                f.vpLVNLow,
                f.vpLVNHigh,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if hvnOverlapsLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_HLVN,
                    (
                        f.vpHVNLow
                        + f.vpHVNHigh
                    ) / 2.0,
                )

            if lvnOverlapsLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_HLVN,
                    (
                        f.vpLVNLow
                        + f.vpLVNHigh
                    ) / 2.0,
                )

            # =================================================
            # SWING LOCATION
            # =================================================

            swingLowInLayer = _in_range(
                f.latestSwingLow,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if swingLowInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_SWINGHL,
                    f.latestSwingLow,
                )

            # =================================================
            # SESSION LOWS
            # =================================================

            asiaLowInLayer = _in_range(
                f.asiaLow,
                layerExtremeLow,
                layerExtremeHigh,
            )

            londonLowInLayer = _in_range(
                f.londonLow,
                layerExtremeLow,
                layerExtremeHigh,
            )

            newYorkLowInLayer = _in_range(
                f.newYorkLow,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if asiaLowInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_SESSIONHL,
                    f.asiaLow,
                )

            if londonLowInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_SESSIONHL,
                    f.londonLow,
                )

            if newYorkLowInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_SESSIONHL,
                    f.newYorkLow,
                )

            # =================================================
            # EMA
            # =================================================

            ema_values = (
                f.ema7,
                f.ema25,
                f.ema50,
                f.ema100,
                f.ema200,
                f.ema300,
            )

            for ema_value in ema_values:
                if _in_range(
                    ema_value,
                    layerExtremeLow,
                    layerExtremeHigh,
                ):
                    _push(
                        opportunityBelowEnrichmentLayer,
                        opportunityBelowEnrichmentFamily,
                        opportunityBelowEnrichmentPrice,
                        layer_index,
                        FAMILY_EMA,
                        ema_value,
                    )

            # =================================================
            # VWAP
            # =================================================

            vwap_values = (
                f.vwapLower2,
                f.vwapLower1,
                f.vwapValue,
                f.vwapUpper1,
                f.vwapUpper2,
            )

            for vwap_value in vwap_values:
                if _in_range(
                    vwap_value,
                    layerExtremeLow,
                    layerExtremeHigh,
                ):
                    _push(
                        opportunityBelowEnrichmentLayer,
                        opportunityBelowEnrichmentFamily,
                        opportunityBelowEnrichmentPrice,
                        layer_index,
                        FAMILY_VWAP,
                        vwap_value,
                    )

            # =================================================
            # WMA 50
            # =================================================

            wma50InLayer = _in_range(
                f.wma50,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if wma50InLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_WMA,
                    f.wma50,
                )

            # =================================================
            # PROTECTED LOW
            # =================================================

            protectedLowInLayer = _in_range(
                f.protectedLow,
                layerExtremeLow,
                layerExtremeHigh,
            )

            if protectedLowInLayer:
                _push(
                    opportunityBelowEnrichmentLayer,
                    opportunityBelowEnrichmentFamily,
                    opportunityBelowEnrichmentPrice,
                    layer_index,
                    FAMILY_PROTECTEDHL,
                    f.protectedLow,
                )

            # =================================================
            # FIBONACCI RETRACEMENTS
            # =================================================

            if _is_valid(f.fibRange) and f.fibRange > 0:

                for fibRatio in fib_enrichment_ratios:

                    fibPrice = None

                    if f.fibDirection == "BULLISH_LEG":
                        fibPrice = (
                            f.activeFibHigh
                            - f.fibRange * fibRatio
                        )

                    if f.fibDirection == "BEARISH_LEG":
                        fibPrice = (
                            f.activeFibLow
                            + f.fibRange * fibRatio
                        )

                    if _in_range(
                        fibPrice,
                        layerExtremeLow,
                        layerExtremeHigh,
                    ):
                        _push(
                            opportunityBelowEnrichmentLayer,
                            opportunityBelowEnrichmentFamily,
                            opportunityBelowEnrichmentPrice,
                            layer_index,
                            FAMILY_FIBONACCI,
                            fibPrice,
                        )

            # =================================================
            # FIBONACCI EXTENSIONS
            # =================================================

            if _is_valid(f.fibRange) and f.fibRange > 0:

                for fibExtensionRatio in fib_extension_ratios:

                    fibExtensionPrice = None

                    if f.fibDirection == "BULLISH_LEG":
                        fibExtensionPrice = (
                            f.activeFibHigh
                            + f.fibRange
                            * (fibExtensionRatio - 1.0)
                        )

                    if f.fibDirection == "BEARISH_LEG":
                        fibExtensionPrice = (
                            f.activeFibLow
                            - f.fibRange
                            * (fibExtensionRatio - 1.0)
                        )

                    if _in_range(
                        fibExtensionPrice,
                        layerExtremeLow,
                        layerExtremeHigh,
                    ):
                        _push(
                            opportunityBelowEnrichmentLayer,
                            opportunityBelowEnrichmentFamily,
                            opportunityBelowEnrichmentPrice,
                            layer_index,
                            FAMILY_FIBONACCI,
                            fibExtensionPrice,
                        )

            # =================================================
            # SUPPORT
            # =================================================

            support_low_array = sr_memory.support_low
            support_high_array = sr_memory.support_high

            if len(support_low_array) > 0:

                for supportIndex in range(
                    len(support_low_array)
                ):

                    supportZoneLow = (
                        support_low_array[supportIndex]
                    )

                    supportZoneHigh = (
                        support_high_array[supportIndex]
                    )

                    supportOverlapsLayer = _overlaps(
                        supportZoneLow,
                        supportZoneHigh,
                        layerExtremeLow,
                        layerExtremeHigh,
                    )

                    if supportOverlapsLayer:
                        _push(
                            opportunityBelowEnrichmentLayer,
                            opportunityBelowEnrichmentFamily,
                            opportunityBelowEnrichmentPrice,
                            layer_index,
                            FAMILY_SR,
                            (
                                supportZoneLow
                                + supportZoneHigh
                            ) / 2.0,
                        )

            # =================================================
            # BULL FVG
            # =================================================

            fvg_bull_low = fvg_memory.bull_low
            fvg_bull_high = fvg_memory.bull_high

            if len(fvg_bull_low) > 0:

                for fvgIndex in range(len(fvg_bull_low)):

                    bullFVGLow = fvg_bull_low[fvgIndex]
                    bullFVGHigh = fvg_bull_high[fvgIndex]

                    bullFVGOverlapsLayer = _overlaps(
                        bullFVGLow,
                        bullFVGHigh,
                        layerExtremeLow,
                        layerExtremeHigh,
                    )

                    if bullFVGOverlapsLayer:
                        _push(
                            opportunityBelowEnrichmentLayer,
                            opportunityBelowEnrichmentFamily,
                            opportunityBelowEnrichmentPrice,
                            layer_index,
                            FAMILY_FVG,
                            (
                                bullFVGLow
                                + bullFVGHigh
                            ) / 2.0,
                        )

    # ========================================================
    # RETURN
    # ========================================================

    return OpportunityUnusedFeaturesResult(
        above_layer=opportunityAboveEnrichmentLayer,
        above_family=opportunityAboveEnrichmentFamily,
        above_price=opportunityAboveEnrichmentPrice,
        below_layer=opportunityBelowEnrichmentLayer,
        below_family=opportunityBelowEnrichmentFamily,
        below_price=opportunityBelowEnrichmentPrice,
    )