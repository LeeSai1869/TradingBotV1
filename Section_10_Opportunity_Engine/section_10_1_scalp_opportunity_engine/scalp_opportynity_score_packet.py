from dataclasses import dataclass
from typing import Optional


@dataclass
class ScalpOpportunityScorePacket:
    tf: str = ""
    valid: bool = False

    opportunity_layer1_score: Optional[float] = None
    opportunity_layer2_score: Optional[float] = None
    opportunity_layer3_score: Optional[float] = None

    opportunity_layer1_price: Optional[float] = None
    opportunity_layer2_price: Optional[float] = None
    opportunity_layer3_price: Optional[float] = None

    opportunity_layer1_pct: Optional[float] = None
    opportunity_layer2_pct: Optional[float] = None
    opportunity_layer3_pct: Optional[float] = None

    opportunity_layer_negative_price: Optional[float] = None
    opportunity_layer_negative_pct: Optional[float] = None


def create_scalp_opportunity_score_packet(
    tf: str,
    opportunity_output
) -> ScalpOpportunityScorePacket:

    if opportunity_output is None:
        return ScalpOpportunityScorePacket(
            tf=tf,
            valid=False
        )

    return ScalpOpportunityScorePacket(
        tf=tf,
        valid=True,

        opportunity_layer1_score=(
            opportunity_output.opportunityLayer1Score
        ),
        opportunity_layer2_score=(
            opportunity_output.opportunityLayer2Score
        ),
        opportunity_layer3_score=(
            opportunity_output.opportunityLayer3Score
        ),

        opportunity_layer1_price=(
            opportunity_output.opportunityLayer1Price
        ),
        opportunity_layer2_price=(
            opportunity_output.opportunityLayer2Price
        ),
        opportunity_layer3_price=(
            opportunity_output.opportunityLayer3Price
        ),

        opportunity_layer1_pct=(
            opportunity_output.opportunityLayer1Pct
        ),
        opportunity_layer2_pct=(
            opportunity_output.opportunityLayer2Pct
        ),
        opportunity_layer3_pct=(
            opportunity_output.opportunityLayer3Pct
        ),

        opportunity_layer_negative_price=(
            opportunity_output.opportunityLayerNegativePrice
        ),
        opportunity_layer_negative_pct=(
            opportunity_output.opportunityLayerNegativePct
        )
    )