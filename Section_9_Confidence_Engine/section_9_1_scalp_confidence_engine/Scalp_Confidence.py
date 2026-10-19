# ======================================================
# SECTION 9: CONFIDENCE ENGINE
# ======================================================

from dataclasses import dataclass

from import_config_packet import InputsPacket
from import_features_packet import FeaturePacket
from import_scalp_decision_score_packet import ScalpDCNScorePacket


# ======================================================
# OUTPUT
# ======================================================

@dataclass
class ScalpConfidenceOutput:
    scalp_confidence_score: float = 0.0


# ======================================================
# 9.1 SCALP CONFIDENCE ENGINE
# ======================================================

def scalp_confidence_engine(
    feature_packet: FeaturePacket,
    decision_score: float,
    decision: str,
    htf30: FeaturePacket,
    htf60: FeaturePacket,
    htf120: FeaturePacket,
    htf240: FeaturePacket,
    htf1D: FeaturePacket,
    decision1m: str,
    decision5m: str,
    decision15m: str,
    inputs_packet: InputsPacket,
) -> ScalpConfidenceOutput:

    scalp_confidence_score = 0.0

    f = feature_packet
    cfg = inputs_packet.scalp_config

    # ==================================================
    # 9.1.1 DECISION SCORE CONTRIBUTION — 40 POINTS
    # ==================================================

    decision_score_quality = 0.0

    if "BUY" in decision:
        decision_score_quality = (
            0.4 *
            max(0.0, min(abs(decision_score), 100.0))
        )

    elif "SELL" in decision:
        decision_score_quality = (
            0.4 *
            max(0.0, min(abs(decision_score), 100.0))
        )

    scalp_confidence_score += decision_score_quality

    # ==================================================
    # 9.1.2 HIGHER-TIMEFRAME ALIGNMENT — 10 POINTS
    # ==================================================

    htf_buy_confidence_score = 0.0
    htf_sell_confidence_score = 0.0
    htf_net_confidence_score = 0.0

    # ----------------------------------------------
    # 30M
    # ----------------------------------------------

    if htf30 is not None and htf30.c is not None:

        if "BUY" in decision:

            if htf30.current_swing_direction == "SWING_UP":
                htf_buy_confidence_score += (
                    10 * cfg.scalp_confidence_on_30m
                )

            elif htf30.current_swing_direction == "SWING_DOWN":
                htf_buy_confidence_score -= (
                    10 * cfg.scalp_confidence_on_30m
                )

        elif "SELL" in decision:

            if htf30.current_swing_direction == "SWING_DOWN":
                htf_sell_confidence_score += (
                    10 * cfg.scalp_confidence_on_30m
                )

            elif htf30.current_swing_direction == "SWING_UP":
                htf_sell_confidence_score -= (
                    10 * cfg.scalp_confidence_on_30m
                )

    else:
        htf_net_confidence_score += (
            15.0 * cfg.scalp_confidence_on_30m * 0.50
        )

    # ----------------------------------------------
    # 60M
    # ----------------------------------------------

    if htf60 is not None and htf60.c is not None:

        if "BUY" in decision:

            if htf60.current_swing_direction == "SWING_UP":
                htf_buy_confidence_score += (
                    10 * cfg.scalp_confidence_on_60m
                )

            elif htf60.current_swing_direction == "SWING_DOWN":
                htf_buy_confidence_score -= (
                    10 * cfg.scalp_confidence_on_60m
                )

        elif "SELL" in decision:

            if htf60.current_swing_direction == "SWING_DOWN":
                htf_sell_confidence_score += (
                    10 * cfg.scalp_confidence_on_60m
                )

            elif htf60.current_swing_direction == "SWING_UP":
                htf_sell_confidence_score -= (
                    10 * cfg.scalp_confidence_on_60m
                )

    else:
        htf_net_confidence_score += (
            10 * cfg.scalp_confidence_on_30m * 0.50
        )

    # ----------------------------------------------
    # 120M
    # ----------------------------------------------

    if htf120 is not None and htf120.c is not None:

        if "BUY" in decision:

            if htf120.current_swing_direction == "SWING_UP":
                htf_buy_confidence_score += (
                    10 * cfg.scalp_confidence_on_120m
                )

            elif htf120.current_swing_direction == "SWING_DOWN":
                htf_buy_confidence_score -= (
                    10 * cfg.scalp_confidence_on_120m
                )

        elif "SELL" in decision:

            if htf120.current_swing_direction == "SWING_DOWN":
                htf_sell_confidence_score += (
                    10 * cfg.scalp_confidence_on_120m
                )

            elif htf120.current_swing_direction == "SWING_UP":
                htf_sell_confidence_score -= (
                    10 * cfg.scalp_confidence_on_120m
                )

    else:
        htf_net_confidence_score += (
            10 * cfg.scalp_confidence_on_30m * 0.50
        )

    # ----------------------------------------------
    # 240M
    # ----------------------------------------------

    if htf240 is not None and htf240.c is not None:

        if "BUY" in decision:

            if htf240.current_swing_direction == "SWING_UP":
                htf_buy_confidence_score += (
                    10 * cfg.scalp_confidence_on_240m
                )

            elif htf240.current_swing_direction == "SWING_DOWN":
                htf_buy_confidence_score -= (
                    10 * cfg.scalp_confidence_on_240m
                )

        elif "SELL" in decision:

            if htf240.current_swing_direction == "SWING_DOWN":
                htf_sell_confidence_score += (
                    10 * cfg.scalp_confidence_on_240m
                )

            elif htf240.current_swing_direction == "SWING_UP":
                htf_sell_confidence_score -= (
                    10 * cfg.scalp_confidence_on_240m
                )

    else:
        htf_net_confidence_score += (
            10 * cfg.scalp_confidence_on_30m * 0.50
        )

    # ----------------------------------------------
    # Apply HTF confidence
    # ----------------------------------------------

    if "BUY" in decision:

        scalp_confidence_score += (
            htf_net_confidence_score
            + htf_buy_confidence_score
            - htf_sell_confidence_score
        )

    elif "SELL" in decision:

        scalp_confidence_score += (
            htf_net_confidence_score
            + htf_sell_confidence_score
            - htf_buy_confidence_score
        )

    # ==================================================
    # 9.1.3 LOCATION QUALITY — 40 POINTS
    # ==================================================

    # ----------------------------------------------
    # 3.1 SUPPORT / RESISTANCE
    # ----------------------------------------------

    support_confidence_score = 0.0
    resistance_confidence_score = 0.0

    if (
        f.nearest_support_zone_price is not None
        and f.nearest_support_zone_price_atr is not None
        and f.nearest_support_zone_price_atr > 0
    ):
        support_confidence_score += (
            4
            * max(
                0.0,
                1.0
                - f.nearest_support_zone_price_distance
                / (f.nearest_support_zone_price_atr * 10)
            )
        )

    is_institutional_support = (
        f.nearest_support_zone_id is not None
        and f.nearest_inst_support_zone_id is not None
        and f.nearest_support_zone_id
        == f.nearest_inst_support_zone_id
    )

    if is_institutional_support:

        if f.inst_support_es_normalized is not None:
            support_confidence_score += (
                2.5 * f.inst_support_es_normalized
            )

        if f.inst_support_st_normalized is not None:
            support_confidence_score += (
                2.5 * f.inst_support_st_normalized
            )

        if f.inst_support_wt_normalized is not None:
            support_confidence_score += (
                1.5 * f.inst_support_wt_normalized
            )

        if f.inst_support_failure_normalized is not None:
            support_confidence_score -= (
                4 * f.inst_support_failure_normalized
            )

        if f.inst_support_last_test_age_normalized is not None:
            support_confidence_score += (
                1.5 * f.inst_support_last_test_age_normalized
            )

    else:

        if f.dynamic_support_es_normalized is not None:
            support_confidence_score += (
                1.5 * f.dynamic_support_es_normalized
            )

        if f.dynamic_support_st_normalized is not None:
            support_confidence_score += (
                1.5 * f.dynamic_support_st_normalized
            )

        if f.dynamic_support_wt_normalized is not None:
            support_confidence_score += (
                0.5 * f.dynamic_support_wt_normalized
            )

        if f.dynamic_support_last_test_age_normalized is not None:
            support_confidence_score += (
                1.5 * f.dynamic_support_last_test_age_normalized
            )

    if (
        f.nearest_resistance_zone_price is not None
        and f.nearest_resistance_zone_price_atr is not None
        and f.nearest_resistance_zone_price_atr > 0
    ):
        resistance_confidence_score += (
            4
            * max(
                0.0,
                1.0
                - f.nearest_resistance_zone_price_distance
                / (f.nearest_resistance_zone_price_atr * 10)
            )
        )

    is_institutional_resistance = (
        f.nearest_resistance_zone_id is not None
        and f.nearest_inst_resistance_zone_id is not None
        and f.nearest_resistance_zone_id
        == f.nearest_inst_resistance_zone_id
    )

    if is_institutional_resistance:

        if f.inst_resistance_es_normalized is not None:
            resistance_confidence_score += (
                2.5 * f.inst_resistance_es_normalized
            )

        if f.inst_resistance_st_normalized is not None:
            resistance_confidence_score += (
                2.5 * f.inst_resistance_st_normalized
            )

        if f.inst_resistance_wt_normalized is not None:
            resistance_confidence_score += (
                1.5 * f.inst_resistance_wt_normalized
            )

        if f.inst_resistance_failure_normalized is not None:
            resistance_confidence_score -= (
                4 * f.inst_resistance_failure_normalized
            )

        if f.inst_resistance_last_test_age_normalized is not None:
            resistance_confidence_score += (
                1.5 * f.inst_resistance_last_test_age_normalized
            )

    else:

        if f.dynamic_resistance_es_normalized is not None:
            resistance_confidence_score += (
                1.5 * f.dynamic_resistance_es_normalized
            )

        if f.dynamic_resistance_st_normalized is not None:
            resistance_confidence_score += (
                1.5 * f.dynamic_resistance_st_normalized
            )

        if f.dynamic_resistance_wt_normalized is not None:
            resistance_confidence_score += (
                0.5 * f.dynamic_resistance_wt_normalized
            )

        if f.dynamic_resistance_last_test_age_normalized is not None:
            resistance_confidence_score += (
                1.5 * f.dynamic_resistance_last_test_age_normalized
            )

    if "BUY" in decision:

        scalp_confidence_score += (
            support_confidence_score
            - resistance_confidence_score
        )

    elif "SELL" in decision:

        scalp_confidence_score += (
            resistance_confidence_score
            - support_confidence_score
        )

    # ----------------------------------------------
    # 3.2 FAIR VALUE GAP
    # ----------------------------------------------

    bull_fvg_confidence_score = 0.0
    bear_fvg_confidence_score = 0.0

    if (
        f.nearest_bull_fvg_distance_atr is not None
        and f.nearest_bull_fvg_strength is not None
    ):

        bull_fvg_confidence_score += (
            2
            * max(
                0.0,
                1.0
                - f.nearest_bull_fvg_distance_atr / 10.0
            )
        )

        bull_fvg_confidence_score += (
            0.5
            * min(
                1.0,
                f.nearest_bull_fvg_strength / 3.0
            )
        )

        bull_fvg_confidence_score += (
            1
            * (
                min(1.0, f.nearest_bull_fvg_status / 3.0)
                if f.nearest_bull_fvg_status is not None
                else 0.0
            )
        )

        bull_fvg_confidence_score += (
            1
            * (
                min(
                    1.0,
                    f.nearestbull_fvg_last_reaction_type / 2.0
                )
                if f.nearestbull_fvg_last_reaction_type is not None
                else 0.0
            )
        )

        if f.nearest_bull_fvg_reaction_score_normalized is not None:
            bull_fvg_confidence_score += (
                1.5
                * f.nearest_bull_fvg_reaction_score_normalized
            )

    if (
        f.nearest_bear_fvg_distance_atr is not None
        and f.nearest_bear_fvg_strength is not None
    ):

        bear_fvg_confidence_score += (
            2
            * max(
                0.0,
                1.0
                - f.nearest_bear_fvg_distance_atr / 10.0
            )
        )

        bear_fvg_confidence_score += (
            0.5
            * min(
                1.0,
                f.nearest_bear_fvg_strength / 3.0
            )
        )

        bear_fvg_confidence_score += (
            1
            * (
                min(1.0, f.nearest_bear_fvg_status / 3.0)
                if f.nearest_bear_fvg_status is not None
                else 0.0
            )
        )

        bear_fvg_confidence_score += (
            1
            * (
                min(
                    1.0,
                    f.nearestbear_fvg_last_reaction_type / 2.0
                )
                if f.nearestbear_fvg_last_reaction_type is not None
                else 0.0
            )
        )

        if f.nearest_bear_fvg_reaction_score_normalized is not None:
            bear_fvg_confidence_score += (
                1.5
                * f.nearest_bear_fvg_reaction_score_normalized
            )

    if "BUY" in decision:

        scalp_confidence_score += (
            bull_fvg_confidence_score
            - bear_fvg_confidence_score
        )

    elif "SELL" in decision:

        scalp_confidence_score += (
            bear_fvg_confidence_score
            - bull_fvg_confidence_score
        )

    # ----------------------------------------------
    # 3.3 OB LOCATION
    # ----------------------------------------------

    bull_ob_score = 0.0
    bear_ob_score = 0.0

    # BUY-side OB proximity

    bull_ob_score += (
        3.0
        * max(
            0.0,
            min(
                1.0,
                1.0 - f.bull_ob_distance_atr / 3.0
            )
        )
    )

    if (
        f.active_strict_bull_ob_high is not None
        and f.active_strict_bull_ob_low is not None
    ):
        bull_ob_score += 2.0

    elif (
        f.active_bull_ob_high is not None
        and f.active_bull_ob_low is not None
    ):
        bull_ob_score += 1.0

    if (
        f.active_bull_ob_high is not None
        and f.active_bull_ob_low is not None
    ):

        if not f.active_bull_ob_has_been_mitigated:

            bull_ob_score += (
                1
                * max(
                    0.0,
                    min(
                        1.0,
                        1.0 - f.bull_ob_age / 100.0
                    )
                )
            )

        else:
            bull_ob_score += 0.5

    if f.active_strict_bull_ob_has_fvg:
        bull_ob_score += 0.5

    elif f.active_bull_ob_has_fvg:
        bull_ob_score += 0.25

    if f.bull_breaker_active:
        bull_ob_score += 0.5

    # SELL-side OB proximity

    bear_ob_score += (
        3.0
        * max(
            0.0,
            min(
                1.0,
                1.0 - f.bear_ob_distance_atr / 2.0
            )
        )
    )

    if (
        f.active_strict_bear_ob_high is not None
        and f.active_strict_bear_ob_low is not None
    ):
        bear_ob_score += 2.0

    elif (
        f.active_bear_ob_high is not None
        and f.active_bear_ob_low is not None
    ):
        bear_ob_score += 1.0

    if (
        f.active_bear_ob_high is not None
        and f.active_bear_ob_low is not None
    ):

        if not f.active_bear_ob_has_been_mitigated:

            bear_ob_score += (
                1
                * max(
                    0.0,
                    min(
                        1.0,
                        1.0 - f.bear_ob_age / 100.0
                    )
                )
            )

        else:
            bear_ob_score += 0.5

    if f.active_strict_bear_ob_has_fvg:
        bear_ob_score += 0.5

    elif f.active_bear_ob_has_fvg:
        bear_ob_score += 0.25

    if f.bear_breaker_active:
        bear_ob_score += 0.5

    if "BUY" in decision:

        scalp_confidence_score += (
            bull_ob_score - bear_ob_score
        )

    elif "SELL" in decision:

        scalp_confidence_score += (
            bear_ob_score - bull_ob_score
        )

    # ----------------------------------------------
    # 3.4 LIQUIDITY LOCATION
    # ----------------------------------------------

    scalp_buy_liquidity_confidence_score = 0.0
    scalp_sell_liquidity_confidence_score = 0.0

    # Buy Side

    if f.nearest_buy_liquidity_atr_distance is not None:

        scalp_buy_liquidity_confidence_score += (
            2
            * max(
                0.0,
                min(
                    1.0,
                    1.0
                    - f.nearest_buy_liquidity_atr_distance / 4.0
                )
            )
        )

    if (
        f.internal_high_liquidity is not None
        or f.external_high_liquidity is not None
    ):

        scalp_buy_liquidity_confidence_score += 0.5

        if f.equal_high_liquidity:
            scalp_buy_liquidity_confidence_score += 0.5

        elif f.high_liquidity_cluster:
            scalp_buy_liquidity_confidence_score += 0.5

        if (
            f.external_high_liquidity is not None
            and f.external_high_liquidity
            == f.internal_high_liquidity
        ):
            scalp_buy_liquidity_confidence_score += 0.25

        if f.bear_sweep_detected:
            scalp_buy_liquidity_confidence_score += 0.10

        if f.bear_sweep_reject:
            scalp_buy_liquidity_confidence_score += 0.15

        if f.external_high_liquidity is not None:
            scalp_buy_liquidity_confidence_score += 0.5

        if (
            f.external_high_liquidity is not None
            and f.internal_high_liquidity is not None
            and f.external_high_liquidity
            != f.internal_high_liquidity
        ):
            scalp_buy_liquidity_confidence_score += 0.5

    # Sell Side

    if f.nearest_sell_liquidity_atr_distance is not None:

        scalp_sell_liquidity_confidence_score += (
            1.5
            * max(
                0.0,
                min(
                    1.0,
                    1.0
                    - f.nearest_sell_liquidity_atr_distance / 4.0
                )
            )
        )

    if (
        f.internal_low_liquidity is not None
        or f.external_low_liquidity is not None
    ):

        scalp_sell_liquidity_confidence_score += 0.5

        if f.equal_low_liquidity:
            scalp_sell_liquidity_confidence_score += 0.5

        elif f.low_liquidity_cluster:
            scalp_sell_liquidity_confidence_score += 0.5

        if (
            f.external_low_liquidity is not None
            and f.external_low_liquidity
            == f.internal_low_liquidity
        ):
            scalp_sell_liquidity_confidence_score += 0.25

        if f.bull_sweep_detected:
            scalp_sell_liquidity_confidence_score += 0.10

        if f.bull_sweep_reclaim:
            scalp_sell_liquidity_confidence_score += 0.15

        if f.external_low_liquidity is not None:
            scalp_sell_liquidity_confidence_score += 0.4

        if (
            f.external_low_liquidity is not None
            and f.internal_low_liquidity is not None
            and f.external_low_liquidity
            != f.internal_low_liquidity
        ):
            scalp_sell_liquidity_confidence_score += 0.3

        if f.equal_low_liquidity:
            scalp_sell_liquidity_confidence_score += 0.3

    if "BUY" in decision:

        scalp_confidence_score += (
            scalp_buy_liquidity_confidence_score
            - scalp_sell_liquidity_confidence_score
        )

    elif "SELL" in decision:

        scalp_confidence_score += (
            scalp_sell_liquidity_confidence_score
            - scalp_buy_liquidity_confidence_score
        )

    # ----------------------------------------------
    # 3.5 RANGE LOCATION
    # ----------------------------------------------

    scalp_buy_range_confidence_score = 0.0
    scalp_sell_range_confidence_score = 0.0

    if f.range_position is not None:

        scalp_buy_range_confidence_score += (
            3
            * max(
                0.0,
                min(
                    1.0,
                    1.0 - f.range_position
                )
            )
        )

        scalp_sell_range_confidence_score += (
            3
            * max(
                0.0,
                min(
                    1.0,
                    f.range_position
                )
            )
        )

    if "BUY" in decision:

        scalp_confidence_score += (
            scalp_buy_range_confidence_score
            - scalp_sell_range_confidence_score
        )

    elif "SELL" in decision:

        scalp_confidence_score += (
            scalp_sell_range_confidence_score
            - scalp_buy_range_confidence_score
        )

    # ----------------------------------------------
    # 3.6 VALUE AREA LOCATION
    # ----------------------------------------------

    scalp_buy_vp_confidence_score = 0.0
    scalp_sell_vp_confidence_score = 0.0
    scalp_net_vp_confidence_score = 0.0

    if (
        f.vp_va_low is not None
        and f.vp_va_high is not None
        and f.vp_va_high > f.vp_va_low
        and f.atr is not None
        and f.atr > 0
    ):

        buy_value_area_boundary_distance_atr = (
            abs(f.c - f.vp_va_low) / f.atr
        )

        scalp_buy_vp_confidence_score += (
            2.0
            * max(
                0.0,
                min(
                    1.0,
                    1.0
                    - buy_value_area_boundary_distance_atr / 3
                )
            )
        )

        sell_value_area_boundary_distance_atr = (
            abs(f.c - f.vp_va_high) / f.atr
        )

        scalp_sell_vp_confidence_score += (
            2.0
            * max(
                0.0,
                min(
                    1.0,
                    1.0
                    - sell_value_area_boundary_distance_atr / 3
                )
            )
        )

        if f.inside_value_area and f.value_area_position is not None:

            scalp_buy_vp_confidence_score += max(
                0.0,
                min(
                    1.0,
                    1.0 - f.value_area_position
                )
            )

            scalp_sell_vp_confidence_score += max(
                0.0,
                min(
                    1.0,
                    f.value_area_position
                )
            )

    if f.distance_to_poc_atr is not None:

        scalp_net_vp_confidence_score += (
            1.5
            * max(
                0.0,
                min(
                    1.0,
                    1.0
                    - abs(f.distance_to_poc_atr) / 2
                )
            )
        )

        if f.price_above_poc:
            scalp_buy_vp_confidence_score += 0.5

        elif f.price_below_poc:
            scalp_sell_vp_confidence_score += 0.5

        else:
            scalp_buy_vp_confidence_score += 0.25
            scalp_sell_vp_confidence_score += 0.25

    if (
        f.atr is not None
        and f.atr > 0
    ):

        if (
            f.vp_hvn_low is not None
            and f.vp_hvn_high is not None
        ):

            if f.c > f.vp_hvn_high:
                hvn_distance_atr = (
                    f.c - f.vp_hvn_high
                ) / f.atr

            elif f.c < f.vp_hvn_low:
                hvn_distance_atr = (
                    f.vp_hvn_low - f.c
                ) / f.atr

            else:
                hvn_distance_atr = 0.0

            hvn_relevance = max(
                0.0,
                min(
                    1.0,
                    1.0 - hvn_distance_atr / 1.25
                )
            )

            if f.c <= f.vp_hvn_high:
                scalp_buy_vp_confidence_score += (
                    1.25 * hvn_relevance
                )

            if f.c >= f.vp_hvn_low:
                scalp_sell_vp_confidence_score += (
                    1.25 * hvn_relevance
                )

        if (
            f.vp_lvn_low is not None
            and f.vp_lvn_high is not None
        ):

            if f.c > f.vp_lvn_high:
                lvn_distance_atr = (
                    f.c - f.vp_lvn_high
                ) / f.atr

            elif f.c < f.vp_lvn_low:
                lvn_distance_atr = (
                    f.vp_lvn_low - f.c
                ) / f.atr

            else:
                lvn_distance_atr = 0.0

            lvn_relevance = max(
                0.0,
                min(
                    1.0,
                    1.0 - lvn_distance_atr / 1.75
                )
            )

            if lvn_relevance > 0:

                if f.c <= f.vp_lvn_high:
                    scalp_buy_vp_confidence_score += (
                        0.75 * lvn_relevance
                    )

                if f.c >= f.vp_lvn_low:
                    scalp_sell_vp_confidence_score += (
                        0.75 * lvn_relevance
                    )

    if (
        f.vp_poc_change is not None
        and f.atr is not None
        and f.atr > 0
    ):

        poc_movement_atr = (
            abs(f.vp_poc_change) / f.atr
        )

        poc_movement_strength = max(
            0.0,
            min(
                1.0,
                poc_movement_atr / 0.25
            )
        )

        if f.vp_poc_change > 0:
            scalp_buy_vp_confidence_score += (
                poc_movement_strength
            )

        elif f.vp_poc_change < 0:
            scalp_sell_vp_confidence_score += (
                poc_movement_strength
            )

    if "BUY" in decision:

        scalp_confidence_score += (
            scalp_net_vp_confidence_score
            + scalp_buy_vp_confidence_score
            - scalp_sell_vp_confidence_score
        )

    elif "SELL" in decision:

        scalp_confidence_score += (
            scalp_net_vp_confidence_score
            + scalp_sell_vp_confidence_score
            - scalp_buy_vp_confidence_score
        )

    # ==================================================
    # 9.1.4 MARKET ENVIRONMENT — 6 POINTS
    # ==================================================

    valid_volatility_atr = 2.0
    volatility_score = 2.0

    if "BUY" in decision or "SELL" in decision:

        if f.atr_ma_ratio is not None:

            scalp_confidence_score += max(
                0.0,
                min(
                    volatility_score,
                    volatility_score
                    * f.atr_ma_ratio
                    / valid_volatility_atr
                )
                - max(
                    0.0,
                    volatility_score
                    * (
                        f.atr_ma_ratio
                        - valid_volatility_atr
                    )
                )
            )

        scalp_confidence_score += (
            1
            * (
                min(
                    1.0,
                    f.candle_range_atr / valid_volatility_atr
                )
                if f.candle_range_atr is not None
                else 0.0
            )
        )

        scalp_confidence_score += (
            1
            * (
                min(
                    1.0,
                    f.candle_efficiency
                )
                if f.candle_efficiency is not None
                else 0.0
            )
        )

        displacement_magnitude = abs(
            f.directional_displacement
        )

        if (
            f.directional_displacement is not None
            and displacement_magnitude > 0
        ):

            scalp_confidence_score += max(
                0.0,
                min(
                    1.0,
                    2.0
                    * displacement_magnitude
                    / 2
                )
                - max(
                    0.0,
                    2
                    * (
                        displacement_magnitude - 2
                    )
                    / 2
                )
            )

    # ==================================================
    # 9.1.5 SESSION / TIME CONTEXT — 5 POINTS
    # ==================================================

    if f.london_session and f.new_york_session:

        scalp_confidence_score += 4.0

    elif f.london_session or f.new_york_session:

        scalp_confidence_score += 2.75

    elif f.asia_session:

        scalp_confidence_score += 1.5

    # ==================================================
    # FINAL SCORE
    # ==================================================

    scalp_confidence_score = max(
        0.0,
        min(
            scalp_confidence_score,
            100.0
        )
    )

    # ==================================================
    # OUTPUT
    # ==================================================

    return ScalpConfidenceOutput(
        scalp_confidence_score=scalp_confidence_score
    )