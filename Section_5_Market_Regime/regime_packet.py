# ======================================================
# REGIME PACKET
# Stable contract produced by Section 5
# ======================================================

from dataclasses import dataclass
from typing import Optional

from .import_features_packet import FeaturePacket
from .Market_Regime import MarketRegime, calculate_market_regime


@dataclass
class RegimePacket:
    """
    Stable contract produced by Section 5.

    Consumes:
        FeaturePacket

    Produces:
        MarketRegime
    """

    tf: str
    valid: bool = False
    regime: Optional[MarketRegime] = None

    control_state: Optional[str] = None
    energy_state: Optional[str] = None
    regime_state: Optional[str] = None
    fatigue_state: Optional[str] = None
    trend_state: Optional[str] = None
    transition_state: Optional[str] = None


def create_regime_packet(
    feature_packet: FeaturePacket
) -> RegimePacket:

    if feature_packet is None or not feature_packet.valid:
        return RegimePacket(
            tf=feature_packet.tf if feature_packet else "",
            valid=False
        )

    regime = calculate_market_regime(feature_packet)

    return RegimePacket(
        tf=feature_packet.tf,
        valid=True,
        regime=regime,
        control_state=regime.control_state,
        energy_state=regime.energy_state,
        regime_state=regime.regime_state,
        fatigue_state=regime.fatigue_state,
        trend_state=regime.trend_state,
        transition_state=regime.transition_state
    )