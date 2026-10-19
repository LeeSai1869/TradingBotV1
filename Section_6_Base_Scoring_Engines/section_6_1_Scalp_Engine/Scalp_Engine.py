# ======================================================
# SECTION 6.1 — SCALP ENGINE (FINAL v11)
# ======================================================
#
# SCALP EVIDENCE ENGINE (pure analysis)
#
# This engine computes WHAT THE MARKET EVIDENCE SAYS.
# It does NOT decide looking_for. It does NOT apply gates.
# It does NOT apply the pivot override. It does NOT read
# trend state.
#
# OWNERSHIP CONTRACT
# ------------------
#
#   Section 1   : persistent trend_direction memory
#   Section 4   : structural flip events
#   Section 6.1 : market evidence (THIS ENGINE)
#   Section 8.1 : looking_for + gates + final decision
#
# Section 6.1 REPORTS:
#   - movement score (DI + ADX)
#   - pivot score (flip event, ±WEIGHT_PIVOT)
#   - raw scalp score (movement + pivot)
#   - pivot eligibility observations
#   - DI / ADX diagnostics
#
# Section 6.1 NEVER decides direction.
# ======================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import importlib.util
from pathlib import Path


# ======================================================
# SECTION 6 ROOT + ADAPTERS
# ======================================================

ENGINE_ROOT = Path(__file__).resolve().parents[1]

FEATURE_INPUT_FILE = ENGINE_ROOT / "import_features_packet.py"
REGIME_INPUT_FILE  = ENGINE_ROOT / "import_regime_packet.py"
CONFIG_INPUT_FILE  = ENGINE_ROOT / "import_config_packet.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_feature_module = _load_module("scalp_feature_input", FEATURE_INPUT_FILE)
_regime_module  = _load_module("scalp_regime_input", REGIME_INPUT_FILE)
_config_module  = _load_module("scalp_config_input", CONFIG_INPUT_FILE)

FeaturePacket = _feature_module.FeaturePacket
RegimePacket  = _regime_module.RegimePacket
InputsPacket  = _config_module.InputsPacket


# ======================================================
# WEIGHTS
# ======================================================

WEIGHT_ADX   = 35.0
WEIGHT_DI    = 35.0
WEIGHT_PIVOT = 10.0

ADX_CEILING = 70.0


# ======================================================
# HELPERS
# ======================================================

def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _normalize(value: float, ceiling: float) -> float:
    if ceiling <= 0.0:
        return 0.0
    return _clamp01(value / ceiling)


# ======================================================
# SCALP OUTPUT — PURE EVIDENCE
# ======================================================

@dataclass
class ScalpOutput:
    # --- Analytical components ---
    directional_movement_score: float = 0.0
    pivot_score: float = 0.0
    scalp_score: float = 0.0
    scalp_diplus_score: float = 0.0
    scalp_diminus_score: float = 0.0

    # --- DI diagnostics ---
    di_plus: float = 0.0
    di_minus: float = 0.0
    di_dominance: float = 0.0
    di_sign: float = 0.0


    # --- ADX diagnostics ---
    adx: float = 0.0
    adx_strength: float = 0.0
    adx_signed: float = 0.0
    adx_contribution: float = 0.0
    di_contribution: float = 0.0

    # --- Directional pivot observations ---
    pivot_high_eligible: bool = False
    pivot_low_eligible: bool = False
    pivot_direction: int = 0

    # --- Movement split ---
    bullish_movement_score: float = 0.0
    bearish_movement_score: float = 0.0

    # --- Section 4 pivot context (informational) ---
    candidate_pivot: int = 0
    candidate_pivot_high_price: Optional[float] = None
    candidate_pivot_low_price: Optional[float] = None
    current_swing_direction: str = "NO SWING"
    swing_transition: int = 0


# ======================================================
# SCALP ENGINE
# ======================================================

def scalp_engine(
    feature_packet: FeaturePacket,
    regime_packet: RegimePacket,
    inputs_packet: InputsPacket,
    tf: str,
) -> ScalpOutput:
    """
    Compute Section 6.1 Scalp evidence.

    Pure analysis. No directional decision. No gates.
    """

    # ==================================================
    # VALIDATION
    # ==================================================

    if (
        feature_packet is None
        or not feature_packet.valid
        or regime_packet is None
        or not regime_packet.valid
        or inputs_packet is None
    ):
        return ScalpOutput()

    features = feature_packet.features
    if features is None:
        return ScalpOutput()

    # ==================================================
    # EXTRACT DI / ADX
    # ==================================================

    di_plus  = float(features.get("di_plus", 0.0) or 0.0)
    di_minus = float(features.get("di_minus", 0.0) or 0.0)
    adx      = float(features.get("adx", 0.0) or 0.0)

    # ==================================================
    # SECTION 4 — SWING PIVOT STATE
    # ==================================================

    candidate_pivot = int(
        features.get("swing_candidate_pivot", 0) or 0
    )
    swing_direction = str(
        features.get("swing_direction", "NO SWING") or "NO SWING"
    )
    pivot_high_flip = bool(
        features.get("swing_pivot_high_flip", False)
    )
    pivot_low_flip = bool(
        features.get("swing_pivot_low_flip", False)
    )
    candidate_pivot_high_price = features.get(
        "swing_candidate_high_price", None
    )
    candidate_pivot_low_price = features.get(
        "swing_candidate_low_price", None
    )
    swing_transition = int(features.get("swing_transition", 0) or 0)

    # ==================================================
    # UPSTREAM VALIDATION — FLIP MUTUAL EXCLUSIVITY
    # ==================================================

    if pivot_high_flip and pivot_low_flip:
        raise RuntimeError(
            "SCALP_ENGINE_INVALID_STATE: Section 4 reported both "
            "pivot_high_flip and pivot_low_flip on the same bar."
        )

    # ==================================================
    # DI DOMINANCE
    # ==================================================

    di_sum = di_plus + di_minus

    if di_sum > 0.0:
        di_dominance = (di_plus - di_minus) / di_sum
        di_dominance = max(-1.0, min(1.0, di_dominance))
    else:
        di_dominance = 0.0

    # ==================================================
    # ADX STRENGTH
    # ==================================================

    adx_strength = _normalize(max(0.0, adx), ADX_CEILING)

    if di_dominance > 0.0:
        di_sign = 1.0
    elif di_dominance < 0.0:
        di_sign = -1.0
    else:
        di_sign = 0.0

    adx_signed = di_sign * adx_strength

    # ==================================================
    # MOVEMENT SCORE
    # ==================================================

    scalp_diplus_score = di_plus * WEIGHT_DI / 100
    scalp_diminus_score = di_minus * WEIGHT_DI / 100

    adx_contribution = adx_signed * WEIGHT_ADX
    di_contribution  = di_dominance * WEIGHT_DI

    directional_movement_score = adx_contribution + di_contribution
    directional_movement_score = max(
        -(WEIGHT_ADX + WEIGHT_DI),
        min(WEIGHT_ADX + WEIGHT_DI, directional_movement_score),
    )

    bullish_movement_score = max(0.0, directional_movement_score)
    bearish_movement_score = max(0.0, -directional_movement_score)

    # ==================================================
    # PIVOT EVIDENCE
    # ==================================================

    pivot_score = 0.0
    pivot_high_eligible = False
    pivot_low_eligible = False
    pivot_direction = 0

    if pivot_high_flip:
        pivot_high_eligible = True
        pivot_direction = -1
        pivot_score = -WEIGHT_PIVOT

    elif pivot_low_flip:
        pivot_low_eligible = True
        pivot_direction = +1
        pivot_score = +WEIGHT_PIVOT

    # ==================================================
    # RAW SCALP SCORE (unmodified evidence)
    # ==================================================

    raw_score = directional_movement_score + pivot_score
    raw_score = max(-80.0, min(80.0, raw_score))

    # ==================================================
    # RETURN
    # ==================================================

    return ScalpOutput(
        directional_movement_score=directional_movement_score,
        pivot_score=pivot_score,
        scalp_score=raw_score,

        di_plus=di_plus,
        di_minus=di_minus,
        di_dominance=di_dominance,
        di_sign=di_sign,
        scalp_diplus_score=scalp_diplus_score,
        scalp_diminus_score=scalp_diminus_score,

        adx=adx,
        adx_strength=adx_strength,
        adx_signed=adx_signed,
        adx_contribution=adx_contribution,
        di_contribution=di_contribution,

        pivot_high_eligible=pivot_high_eligible,
        pivot_low_eligible=pivot_low_eligible,
        pivot_direction=pivot_direction,

        bullish_movement_score=bullish_movement_score,
        bearish_movement_score=bearish_movement_score,

        candidate_pivot=candidate_pivot,
        candidate_pivot_high_price=candidate_pivot_high_price,
        candidate_pivot_low_price=candidate_pivot_low_price,
        current_swing_direction=swing_direction,
        swing_transition=swing_transition,
    )


# ======================================================
# EXECUTION HELPER
# ======================================================

@dataclass
class ScalpExecutionResult:
    tf: str
    output: Optional[ScalpOutput] = None


def execute_scalp_engine_from_packet(
    feature_packet: FeaturePacket,
    regime_packet: RegimePacket,
    inputs_packet: InputsPacket,
    tf: str,
) -> ScalpExecutionResult:
    output = scalp_engine(feature_packet, regime_packet, inputs_packet, tf)
    return ScalpExecutionResult(tf=tf, output=output)


__all__ = [
    "ScalpOutput",
    "ScalpExecutionResult",
    "scalp_engine",
    "execute_scalp_engine_from_packet",
]