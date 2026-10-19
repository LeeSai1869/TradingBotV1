# ============================================================
# process_candle_adcn.py
# Processes one historical candle into ADCN execution memory
# ============================================================

from typing import Any, Optional


def process_candle(
    *,
    symbol: str,
    timeframe: str,
    candle: dict,
    memory: Any,
    # Optional real packets (pass when available)
    decision_packet: Optional[Any] = None,
    opportunity_packet: Optional[Any] = None,
    confidence_packet: Optional[Any] = None,
) -> None:
    """
    Stores one bar into ADCN runtime memory.

    When decision / opportunity / confidence packets are provided,
    their values are stored. Otherwise safe placeholders are used
    so the historical runner still works.
    """

    # ------------------------------------------------------------------
    # 1. Identity + OHLC
    # ------------------------------------------------------------------
    memory.symbol.append(symbol)
    memory.timeframe.append(timeframe)

    memory.bar_index.append(candle["bar_index"])
    memory.bar_time.append(candle["bar_time"])

    memory.open_price.append(candle["open_price"])
    memory.high_price.append(candle["high_price"])
    memory.low_price.append(candle["low_price"])
    memory.close_price.append(candle["close_price"])

    memory.flag_id.append(0)

    # ------------------------------------------------------------------
    # 2. Decision
    # ------------------------------------------------------------------
    if decision_packet is not None and getattr(decision_packet, "valid", False):
        memory.decision.append(decision_packet.signal_type)
        memory.decision_score.append(float(decision_packet.final_score))
    else:
        memory.decision.append("NONE")
        memory.decision_score.append(0.0)

    # ------------------------------------------------------------------
    # 3. Confidence
    # ------------------------------------------------------------------
    if confidence_packet is not None and getattr(confidence_packet, "valid", False):
        memory.confidence_percentage.append(
            float(confidence_packet.confidence_percentage)
        )
    else:
        memory.confidence_percentage.append(0.0)

    # ------------------------------------------------------------------
    # 4. Opportunity layers
    # ------------------------------------------------------------------
    if opportunity_packet is not None and getattr(opportunity_packet, "valid", False):
        memory.opportunity_layer1_price.append(
            opportunity_packet.opportunity_layer1_price
        )
        memory.opportunity_layer2_price.append(
            opportunity_packet.opportunity_layer2_price
        )
        memory.opportunity_layer3_price.append(
            opportunity_packet.opportunity_layer3_price
        )

        memory.opportunity_layer1_pct.append(
            opportunity_packet.opportunity_layer1_pct
        )
        memory.opportunity_layer2_pct.append(
            opportunity_packet.opportunity_layer2_pct
        )
        memory.opportunity_layer3_pct.append(
            opportunity_packet.opportunity_layer3_pct
        )

        memory.opportunity_negative_price.append(
            opportunity_packet.opportunity_layer_negative_price
        )
        memory.opportunity_negative_pct.append(
            opportunity_packet.opportunity_layer_negative_pct
        )
    else:
        memory.opportunity_layer1_price.append(None)
        memory.opportunity_layer2_price.append(None)
        memory.opportunity_layer3_price.append(None)

        memory.opportunity_layer1_pct.append(None)
        memory.opportunity_layer2_pct.append(None)
        memory.opportunity_layer3_pct.append(None)

        memory.opportunity_negative_price.append(None)
        memory.opportunity_negative_pct.append(None)