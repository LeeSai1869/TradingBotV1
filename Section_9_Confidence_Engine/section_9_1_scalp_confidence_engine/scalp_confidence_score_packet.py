from dataclasses import dataclass


@dataclass
class ScalpConfidenceScorePacket:
    tf: str = ""
    valid: bool = False
    confidence_percentage: float = 0.0


def create_scalp_confidence_score_packet(
    tf: str,
    confidence_output
) -> ScalpConfidenceScorePacket:

    if confidence_output is None:
        return ScalpConfidenceScorePacket(
            tf=tf,
            valid=False
        )

    return ScalpConfidenceScorePacket(
        tf=tf,
        valid=True,
        confidence_percentage=confidence_output.scalp_confidence_score
    )