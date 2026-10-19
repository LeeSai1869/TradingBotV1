# ======================================================
# FEATURE PACKET
# Stable contract produced by Section 4
# ======================================================

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class FeaturePacket:
    """
    Stable output contract produced by Section 4 Features.

    This packet carries the calculated feature state downstream
    to Section 5 Regime and other consumers.

    The packet does NOT calculate features.
    The Feature Engine calculates them and places the results here.
    """

    tf: str = ""
    valid: bool = False

    # --------------------------------------------------
    # Feature values
    # --------------------------------------------------

    features: Dict[str, Any] = None

    # --------------------------------------------------
    # Packet creation
    # --------------------------------------------------

    def __post_init__(self):
        if self.features is None:
            self.features = {}


def create_feature_packet(
    tf: str,
    features: Dict[str, Any],
    *,
    valid: bool = True,
) -> FeaturePacket:

    if features is None:
        return FeaturePacket(
            tf=tf,
            valid=False,
            features={},
        )

    return FeaturePacket(
        tf=tf,
        valid=valid,
        features=features,
    )


__all__ = [
    "FeaturePacket",
    "create_feature_packet",
]