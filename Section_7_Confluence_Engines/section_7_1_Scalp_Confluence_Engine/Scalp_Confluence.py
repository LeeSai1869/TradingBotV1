# ======================================================
# SECTION 7.1 — SCALP CONFLUENCE ENGINE
# ======================================================
#
# Three inputs only:
#   1. FeaturePacket
#   2. RegimePacket
#   3. InputsPacket
#
# Architecture:
#   - Consumes stable packet contracts.
#   - Does NOT calculate features.
#   - Does NOT recalculate Section 4 values.
#   - Feature values are extracted once from
#     FeaturePacket.features, following the same pattern
#     established by Section 6.1.
#
# Output:
#   Bull Confluence Score : 0 ... 20
#   Bear Confluence Score : 0 ... 20
#   Net Confluence Score  : -20 ... +20
# ======================================================

from dataclasses import dataclass
from typing import Optional

from Section_7_Confluence_Engines.import_features_packet import FeaturePacket
from Section_7_Confluence_Engines.import_regime_packet import RegimePacket
from Section_7_Confluence_Engines.import_config_packet import InputsPacket


# ======================================================
# SCALP CONFLUENCE OUTPUT
# ======================================================

@dataclass
class ScalpConfluenceOutput:
    scalp_confluence_net_score: float = 0.0
    bull_score: float = 0.0
    bear_score: float = 0.0


@dataclass
class ScalpConfluenceExecutionResult:
    tf: str
    output: Optional[ScalpConfluenceOutput] = None


# ======================================================
# SCALP CONFLUENCE ENGINE
# ======================================================

def scalp_confluence_engine(
    feature_packet: FeaturePacket,
    regime_packet: RegimePacket,
    inputs_packet: InputsPacket
) -> ScalpConfluenceOutput:

    # ==================================================
    # PACKET VALIDATION
    # ==================================================

    if (
        feature_packet is None
        or not feature_packet.valid
        or regime_packet is None
        or not regime_packet.valid
        or inputs_packet is None
    ):
        return ScalpConfluenceOutput()

    # ==================================================
    # PACKET DATA
    # ==================================================
    #
    # Same architecture as Section 6.1:
    #
    # FeaturePacket
    #     ↓
    # feature_packet.features
    #     ↓
    # local feature variables
    #     ↓
    # scoring logic
    #
    # No feature calculations occur here.
    # ==================================================

    features = feature_packet.features

    if features is None:
        return ScalpConfluenceOutput()

    regime = regime_packet.regime

    if regime is None:
        return ScalpConfluenceOutput()

    # ==================================================
    # FEATURE VALUES
    # ==================================================
    #
    # Extract each feature once.
    #
    # IMPORTANT:
    # Existing Section 7.1 defaults and None behavior
    # are preserved exactly.
    #
    # Missing Section 4 features are intentionally NOT
    # replaced with similar-looking fields.
    # ==================================================

    # --------------------------------------------------
    # Candle / price
    # --------------------------------------------------

    c = features.get("c")
    o = features.get("o")
    h = features.get("h")
    l = features.get("l")

    # --------------------------------------------------
    # Momentum
    # --------------------------------------------------

    di_plus = features.get("di_plus")
    di_minus = features.get("di_minus")

    prev_di_plus = features.get("prev_di_plus")
    prev_di_minus = features.get("prev_di_minus")

    adx = features.get("adx")
    prev_adx = features.get("prev_adx")

    rsi = features.get("rsi")
    prev_rsi = features.get("prev_rsi")

    body_percent = features.get("body_percent")
    prev_body_percent = features.get("prev_body_percent")

    # --------------------------------------------------
    # Volume
    # --------------------------------------------------

    volume_ratio = features.get("volume_ratio")
    prev_volume_ratio = features.get("prev_volume_ratio")

    # --------------------------------------------------
    # Candle reaction
    # --------------------------------------------------

    candle_direction = features.get("candle_direction")
    displacement_atr = features.get("displacement_atr")

    # --------------------------------------------------
    # Structure
    # --------------------------------------------------

    last_structure_bos = features.get(
        "last_structure_bos"
    )

    last_structure_choch = features.get(
        "last_structure_choch"
    )

    bull_bos_distance_atr = features.get(
        "bull_bos_distance_atr"
    )

    bear_bos_distance_atr = features.get(
        "bear_bos_distance_atr"
    )

    # --------------------------------------------------
    # FVG / Location
    # --------------------------------------------------

    price_inside_bull_memory_fvg = features.get(
        "price_inside_bull_memory_fvg",
        False
    )

    price_inside_bear_memory_fvg = features.get(
        "price_inside_bear_memory_fvg",
        False
    )

    has_bull_fvg = features.get(
        "has_bull_fvg",
        False
    )

    has_bear_fvg = features.get(
        "has_bear_fvg",
        False
    )

    nearest_bull_fvg_strength = features.get(
        "nearest_bull_fvg_strength"
    )

    nearest_bear_fvg_strength = features.get(
        "nearest_bear_fvg_strength"
    )

    nearest_bull_fvg_status = features.get(
        "nearest_bull_fvg_status"
    )

    nearest_bear_fvg_status = features.get(
        "nearest_bear_fvg_status"
    )

    # --------------------------------------------------
    # Volume Profile
    # --------------------------------------------------

    distance_to_poc_atr = features.get(
        "distance_to_poc_atr"
    )

    value_area_position = features.get(
        "value_area_position"
    )

    distance_to_lvn = features.get(
        "distance_to_lvn"
    )

    # --------------------------------------------------
    # Fibonacci
    # --------------------------------------------------

    nearest_fib_distance_pct = features.get(
        "nearest_fib_distance_pct"
    )

    fib_direction = features.get(
        "fib_direction"
    )

    # ==================================================
    # MISSING / FUTURE SECTION 4 FEATURES
    # ==================================================
    #
    # These are intentionally accessed with their
    # original Section 7.1 defaults.
    #
    # DO NOT map them to similarly named Section 4
    # fields until semantic equivalence is verified.
    # ==================================================

    internal_low_liquidity = features.get(
        "internal_low_liquidity"
    )

    external_low_liquidity = features.get(
        "external_low_liquidity"
    )

    internal_high_liquidity = features.get(
        "internal_high_liquidity"
    )

    external_high_liquidity = features.get(
        "external_high_liquidity"
    )

    bull_sweep_detected = features.get(
        "bull_sweep_detected",
        False
    )

    bear_sweep_detected = features.get(
        "bear_sweep_detected",
        False
    )

    prev_low_liquidity = features.get(
        "prev_low_liquidity"
    )

    prev_high_liquidity = features.get(
        "prev_high_liquidity"
    )

    bull_sweep_reclaim = features.get(
        "bull_sweep_reclaim",
        False
    )

    bear_sweep_reject = features.get(
        "bear_sweep_reject",
        False
    )

    directional_displacement = features.get(
        "directional_displacement",
        0
    )

    interacting_support_zone_id = features.get(
        "interacting_support_zone_id"
    )

    # ==================================================
    # 7.1.1 LIQUIDITY CONTEXT
    # ==================================================

    bull_liquidity_score = 0.0
    bear_liquidity_score = 0.0

    bull_liquidity_pool_reached = (
        (
            internal_low_liquidity is not None
            and l <= internal_low_liquidity
        )
        or
        (
            external_low_liquidity is not None
            and l <= external_low_liquidity
        )
    )

    bear_liquidity_pool_reached = (
        (
            internal_high_liquidity is not None
            and h >= internal_high_liquidity
        )
        or
        (
            external_high_liquidity is not None
            and h >= external_high_liquidity
        )
    )

    if bull_liquidity_pool_reached:
        bull_liquidity_score += 1.0

    if bear_liquidity_pool_reached:
        bear_liquidity_score += 1.0

    if bull_sweep_detected:
        bull_liquidity_score += 1.0

    if bear_sweep_detected:
        bear_liquidity_score += 1.0

    bull_sweep_failed_continuation = (
        bull_sweep_detected
        and prev_low_liquidity is not None
        and c >= prev_low_liquidity
    )

    bear_sweep_failed_continuation = (
        bear_sweep_detected
        and prev_high_liquidity is not None
        and c <= prev_high_liquidity
    )

    if bull_sweep_failed_continuation:
        bull_liquidity_score += 1.0

    if bear_sweep_failed_continuation:
        bear_liquidity_score += 1.0

    bull_liquidity_reaction_confirmed = (
        bull_sweep_reclaim
        and directional_displacement > 0
        and displacement_atr > 0
    )

    bear_liquidity_reaction_confirmed = (
        bear_sweep_reject
        and directional_displacement < 0
        and displacement_atr > 0
    )

    if bull_liquidity_reaction_confirmed:
        bull_liquidity_score += 1.0

    if bear_liquidity_reaction_confirmed:
        bear_liquidity_score += 1.0

    bull_liquidity_score = min(
        bull_liquidity_score,
        4.0
    )

    bear_liquidity_score = min(
        bear_liquidity_score,
        4.0
    )

    # ==================================================
    # 7.1.2 LOCATION CONTEXT
    # ==================================================

    bull_location_score = 0.0
    bear_location_score = 0.0

    if price_inside_bull_memory_fvg:
        bull_location_score = 0.75

    if price_inside_bear_memory_fvg:
        bear_location_score = 0.75

    if has_bull_fvg:
        strength = nearest_bull_fvg_strength

        if strength is not None:
            if strength >= 3:
                bull_location_score = 0.75
            elif strength >= 2:
                bull_location_score = 0.25

    if has_bear_fvg:
        strength = nearest_bear_fvg_strength

        if strength is not None:
            if strength >= 3:
                bear_location_score = 0.75
            elif strength >= 2:
                bear_location_score = 0.25

    if has_bull_fvg:
        status = nearest_bull_fvg_status

        if status == "FVG_STATUS_DEFENDED":
            bull_location_score = 0.75
        elif status == "FVG_STATUS_TESTED":
            bull_location_score = 0.25

    if has_bear_fvg:
        status = nearest_bear_fvg_status

        if status == "FVG_STATUS_DEFENDED":
            bear_location_score = 0.75
        elif status == "FVG_STATUS_TESTED":
            bear_location_score = 0.25

    if has_bull_fvg:
        if feature_packet.tf == "240":
            bull_location_score = 0.25
        elif feature_packet.tf == "1D":
            bull_location_score = 0.75

    if has_bear_fvg:
        if feature_packet.tf == "240":
            bear_location_score = 0.25
        elif feature_packet.tf == "1D":
            bear_location_score = 0.75

    if interacting_support_zone_id is not None:
        raise RuntimeError(
            "SCALP_CONFLUENCE_SR_CONTRACT: "
            "7.1 still expects the old nested SR structure."
        )

    bull_location_score = min(
        bull_location_score,
        6.0
    )

    bear_location_score = min(
        bear_location_score,
        6.0
    )

    # ==================================================
    # 7.1.3 VOLUME PARTICIPATION
    # ==================================================

    weak_participation = (
        volume_ratio is not None
        and volume_ratio <= 0.8
    )

    strong_participation = (
        volume_ratio is not None
        and volume_ratio >= 1.2
    )

    bull_exhaustion_count = 0
    bear_exhaustion_count = 0

    if (
        di_plus is not None
        and di_minus is not None
        and di_plus > di_minus
    ):
        if di_plus < prev_di_plus:
            bull_exhaustion_count += 1

        if adx < prev_adx:
            bull_exhaustion_count += 1

        if rsi < prev_rsi:
            bull_exhaustion_count += 1

        if body_percent < prev_body_percent:
            bull_exhaustion_count += 1

    if (
        di_minus is not None
        and di_plus is not None
        and di_minus > di_plus
    ):
        if di_minus < prev_di_minus:
            bear_exhaustion_count += 1

        if adx < prev_adx:
            bear_exhaustion_count += 1

        if rsi > prev_rsi:
            bear_exhaustion_count += 1

        if body_percent < prev_body_percent:
            bear_exhaustion_count += 1

    bullish_exhaustion = (
        bull_exhaustion_count > 0
    )

    bearish_exhaustion = (
        bear_exhaustion_count > 0
    )

    bull_volume_score = 0.0
    bear_volume_score = 0.0

    if bullish_exhaustion:
        if strong_participation:
            bull_volume_score += 1.5
        elif weak_participation:
            bear_volume_score += 0.75

    if bearish_exhaustion:
        if strong_participation:
            bear_volume_score += 1.5
        elif weak_participation:
            bull_volume_score += 0.75

    bullish_reaction = (
        c > o
        and directional_displacement > 0
    )

    bearish_reaction = (
        c < o
        and directional_displacement < 0
    )

    participation_expanded = (
        volume_ratio is not None
        and prev_volume_ratio is not None
        and volume_ratio > prev_volume_ratio
    )

    if bullish_reaction and participation_expanded:
        bull_volume_score += 1.5

    if bearish_reaction and participation_expanded:
        bear_volume_score += 1.5

    bull_volume_score = min(
        bull_volume_score,
        3.0
    )

    bear_volume_score = min(
        bear_volume_score,
        3.0
    )

    # ==================================================
    # 7.1.4 MARKET STRUCTURE CONTEXT
    # ==================================================

    bull_structure_score = 0.0
    bear_structure_score = 0.0

    if last_structure_bos == "bullishBOS":
        if bull_bos_distance_atr is not None:
            if bull_bos_distance_atr >= 1.0:
                bull_structure_score += 2.0
            elif bull_bos_distance_atr >= 0.5:
                bull_structure_score += 1.0

    if last_structure_bos == "bearishBOS":
        if bear_bos_distance_atr is not None:
            if bear_bos_distance_atr >= 1.0:
                bear_structure_score += 2.0
            elif bear_bos_distance_atr >= 0.5:
                bear_structure_score += 1.0

    if last_structure_choch == "bullishCHoCH":
        bull_structure_score += 1.0

    if last_structure_choch == "bearishCHoCH":
        bear_structure_score += 1.0

    structure_htf = feature_packet.tf in {
        "30",
        "60",
        "120",
        "240",
        "1D",
        "1W",
        "1M",
        "3M",
        "6M",
    }

    if structure_htf:
        if (
            last_structure_bos == "bullishBOS"
            or last_structure_choch == "BullishCHOCH"
        ):
            bull_structure_score += 1.0

        if (
            last_structure_bos == "bearishBOS"
            or last_structure_choch == "bearishCHoCH"
        ):
            bear_structure_score += 1.0

    bull_structure_score = min(
        bull_structure_score,
        4.0
    )

    bear_structure_score = min(
        bear_structure_score,
        4.0
    )

    # ==================================================
    # 7.1.5 VOLUME PROFILE CONTEXT
    # ==================================================

    bull_vp_score = 0.0
    bear_vp_score = 0.0

    vp_below_poc = (
        distance_to_poc_atr is not None
        and distance_to_poc_atr < 0
    )

    vp_above_poc = (
        distance_to_poc_atr is not None
        and distance_to_poc_atr > 0
    )

    vp_near_poc = (
        distance_to_poc_atr is not None
        and abs(distance_to_poc_atr) <= 1.5
    )

    if vp_near_poc:
        if vp_below_poc:
            bull_vp_score += 1.0

        if vp_above_poc:
            bear_vp_score += 1.0

    vp_valid_value_area = (
        value_area_position is not None
        and 0 <= value_area_position <= 1
    )

    if vp_valid_value_area:
        if value_area_position <= 0.25:
            bull_vp_score += 0.5
        elif value_area_position >= 0.75:
            bear_vp_score += 0.5

    near_lvn = (
        distance_to_lvn is not None
        and abs(distance_to_lvn) <= 0.50
    )

    if near_lvn:
        if vp_below_poc:
            bull_vp_score += 0.5
        elif vp_above_poc:
            bear_vp_score += 0.5

    bull_vp_score = min(
        bull_vp_score,
        2.0
    )

    bear_vp_score = min(
        bear_vp_score,
        2.0
    )

    # ==================================================
    # 7.1.6 FIBONACCI CONTEXT
    # ==================================================

    bull_fib_score = 0.0
    bear_fib_score = 0.0

    near_fib_retracement = (
        nearest_fib_distance_pct is not None
        and nearest_fib_distance_pct <= 0.50
    )

    if near_fib_retracement:
        if fib_direction == "BULLISH_LEG":
            bull_fib_score = 1.0
        elif fib_direction == "BEARISH_LEG":
            bear_fib_score = 1.0

    bull_fib_score = min(
        bull_fib_score,
        1.0
    )

    bear_fib_score = min(
        bear_fib_score,
        1.0
    )

    # ==================================================
    # FINAL CONFLUENCE SCORE
    # ==================================================

    bull_confluence_score = (
        bull_liquidity_score
        + bull_location_score
        + bull_volume_score
        + bull_structure_score
        + bull_vp_score
        + bull_fib_score
    )

    bear_confluence_score = (
        bear_liquidity_score
        + bear_location_score
        + bear_volume_score
        + bear_structure_score
        + bear_vp_score
        + bear_fib_score
    )

    bull_confluence_score = min(
        bull_confluence_score,
        20.0
    )

    bear_confluence_score = min(
        bear_confluence_score,
        20.0
    )

    scalp_confluence_net_score = (
        bull_confluence_score
        - bear_confluence_score
    )

    scalp_confluence_net_score = max(
        min(
            scalp_confluence_net_score,
            20.0
        ),
        -20.0
    )

    return ScalpConfluenceOutput(
        scalp_confluence_net_score=scalp_confluence_net_score,
        bull_score=bull_confluence_score,
        bear_score=bear_confluence_score,
    )


# ======================================================
# EXECUTE SCALP CONFLUENCE ENGINE FROM PACKETS
# ======================================================

def execute_scalp_confluence_engine_from_packet(
    feature_packet: FeaturePacket,
    regime_packet: RegimePacket,
    inputs_packet: InputsPacket
) -> ScalpConfluenceExecutionResult:

    tf = (
        feature_packet.tf
        if feature_packet is not None
        else ""
    )

    if (
        feature_packet is None
        or not feature_packet.valid
        or regime_packet is None
        or not regime_packet.valid
        or inputs_packet is None
    ):
        return ScalpConfluenceExecutionResult(
            tf=tf,
            output=ScalpConfluenceOutput()
        )

    output = scalp_confluence_engine(
        feature_packet=feature_packet,
        regime_packet=regime_packet,
        inputs_packet=inputs_packet
    )

    return ScalpConfluenceExecutionResult(
        tf=tf,
        output=output
    )