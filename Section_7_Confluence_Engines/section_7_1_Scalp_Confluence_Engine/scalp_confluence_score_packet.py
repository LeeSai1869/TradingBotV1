# ======================================================
# SCALP CONFLUENCE PACKET
# ======================================================

from dataclasses import dataclass


@dataclass
class ScalpConfluenceScorePacket:
    tf: str = ""
    valid: bool = False

    confluence_net_score: float = 0.0
    bull_score: float = 0.0
    bear_score: float = 0.0


def create_scalp_confluence_score_packet(
    tf: str,
    confluence_output
) -> ScalpConfluenceScorePacket:

    if confluence_output is None:
        return ScalpConfluenceScorePacket(
            tf=tf,
            valid=False
        )

    return ScalpConfluenceScorePacket(
        tf=tf,
        valid=True,
        confluence_net_score=confluence_output.scalp_confluence_net_score,
        bull_score=confluence_output.bull_score,
        bear_score=confluence_output.bear_score
    )