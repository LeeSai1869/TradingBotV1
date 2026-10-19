# ======================================================
# SECTION 6.1 — SCALP SCORE PACKET
# ======================================================
# Stable output contract for Section 6.1 Scalp evidence.
#
# Consumers:
#   - Section 8.1 Decision Engine
#   - Section 11 UI flags
# ======================================================

from dataclasses import dataclass
from typing import Optional


@dataclass
class ScalpScorePacket:
    tf: str = ""
    valid: bool = False

    # --- Raw evidence ---
    scalp_score: float = 0.0
    directional_movement_score: float = 0.0
    pivot_score: float = 0.0
    scalp_diminus_score: float = 0.0
    scalp_diplus_score: float = 0.0

    # --- DI / ADX diagnostics ---
    di_plus: float = 0.0
    di_minus: float = 0.0
    di_dominance: float = 0.0
    adx: float = 0.0
    adx_strength: float = 0.0

    # --- Directional pivot observations ---
    pivot_high_eligible: bool = False
    pivot_low_eligible: bool = False
    pivot_direction: int = 0

    # --- Movement split ---
    bullish_movement_score: float = 0.0
    bearish_movement_score: float = 0.0

    # --- Section 4 pivot context ---
    candidate_pivot: int = 0
    current_swing_direction: str = "NO SWING"


def create_scalp_score_packet(
    tf: str,
    scalp_output,
) -> ScalpScorePacket:
    """Convert Section 6.1 ScalpOutput into the stable packet."""

    if scalp_output is None:
        return ScalpScorePacket(tf=tf, valid=False)

    return ScalpScorePacket(
        tf=tf,
        valid=True,

        scalp_score=float(getattr(scalp_output, "scalp_score", 0.0)),
        directional_movement_score=float(
            getattr(scalp_output, "directional_movement_score", 0.0)
        ),
        pivot_score=float(getattr(scalp_output, "pivot_score", 0.0)),
        scalp_diplus_score=float(getattr(scalp_output, "scalp_diplus_score", 0.0)),
        scalp_diminus_score=float(getattr(scalp_output, "scalp_diminus_score", 0.0)),

        di_plus=float(getattr(scalp_output, "di_plus", 0.0)),
        di_minus=float(getattr(scalp_output, "di_minus", 0.0)),
        di_dominance=float(getattr(scalp_output, "di_dominance", 0.0)),
        adx=float(getattr(scalp_output, "adx", 0.0)),
        adx_strength=float(getattr(scalp_output, "adx_strength", 0.0)),

        pivot_high_eligible=bool(
            getattr(scalp_output, "pivot_high_eligible", False)
        ),
        pivot_low_eligible=bool(
            getattr(scalp_output, "pivot_low_eligible", False)
        ),
        pivot_direction=int(
            getattr(scalp_output, "pivot_direction", 0)
        ),

        bullish_movement_score=float(
            getattr(scalp_output, "bullish_movement_score", 0.0)
        ),
        bearish_movement_score=float(
            getattr(scalp_output, "bearish_movement_score", 0.0)
        ),

        candidate_pivot=int(
            getattr(scalp_output, "candidate_pivot", 0)
        ),
        current_swing_direction=str(
            getattr(scalp_output, "current_swing_direction", "NO SWING")
        ),
    )


__all__ = [
    "ScalpScorePacket",
    "create_scalp_score_packet",
]