# ======================================================
# SCALP DCN SCORE PACKET
# ======================================================
# Stable output contract produced by Section 8.1.
#
# This file contains NO scoring logic, NO thresholds,
# NO boundary loading. Only the packet and its factory.
# ======================================================

from dataclasses import dataclass


@dataclass
class ScalpDCNScorePacket:

    tf: str = ""
    valid: bool = False

    signal_type: str = "WAIT"

    final_score: float = 0.0

    scalp_score: float = 0.0
    confluence_score: float = 0.0

    decision_state: str = "NONE"


def create_scalp_dcn_score_packet(
    tf: str,
    dcn_output,
) -> ScalpDCNScorePacket:

    if dcn_output is None:
        return ScalpDCNScorePacket(
            tf=tf,
            valid=False,
        )

    return ScalpDCNScorePacket(
        tf=tf,
        valid=True,

        signal_type=dcn_output.signal_type,

        final_score=dcn_output.final_score,

        scalp_score=dcn_output.scalp_score,

        confluence_score=dcn_output.confluence_score,

        decision_state=dcn_output.decision_state,
    )


__all__ = [
    "ScalpDCNScorePacket",
    "create_scalp_dcn_score_packet",
]