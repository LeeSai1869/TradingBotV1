# ======================================================
# SECTION 8.1 — SCALP DCN (DECISION ENGINE)
# ======================================================
#
# This engine owns the FINAL DECISION for the Scalp path.
#
# ======================================================
# OWNERSHIP CONTRACT
# ======================================================
#
# Section 1 owns:
#     - persistent trend_direction memory (per TF)
#
# Section 4 owns:
#     - structural flip events (flip_direction, flips)
#
# Section 6.1 owns:
#     - market evidence (movement score, pivot score,
#       raw scalp score, DI/ADX diagnostics)
#     - pivot eligibility observations
#
# Section 8.1 owns:
#     - looking_for determination
#     - directional gate
#     - scalp contribution
#     - confluence contribution alignment
#     - final signal decision
#     - alternation RULE (suppression policy)
#
# Section 8.1 does NOT own:
#     - trend_state memory (owned by Section 1)
#     - last_signal memory (owned by ADCN memory)
#     - pivot eligibility computation (owned by Section 6.1)
#
# ======================================================
# INPUTS
# ======================================================
#
#     scalp_score_packet        (Section 6.1)
#     confluence_score_packet   (Section 7.1, optional)
#     inputs_packet             (Section 2 — presence check)
#     trend_state               (Section 1 memory)
#     last_signal               (ADCN memory)
#
# ======================================================
# UPSTREAM CONTRACT
# ======================================================
#
# Section 6.1 guarantees:
#     at most one of pivot_high_eligible / pivot_low_eligible
#     can be True on any bar.
#
# Section 8.1 relies on that guarantee and does not re-check.
#
# ======================================================
# DECISION CONTRACT
# ======================================================
#
# looking_for is determined by last_signal (PRIMARY)
# and trend_state (SECONDARY):
#
#   (None or BUY)  + UP   -> looking_for = "SELL"
#   (None or SELL) + DOWN -> looking_for = "BUY"
#
# All other state combinations are not part of this stage
# and yield looking_for = None.
#
# DIRECTIONAL GATE:
#   looking_for == "SELL":
#       pivot_high_eligible AND sell_di_score
#   looking_for == "BUY":
#       pivot_low_eligible AND buy_di_score
#
#   On fire, the scalp score is aligned to the direction.
#   On no fire, contribution is 0.0.
#
# CONFLUENCE:
#   Forced to the same sign as the scalp contribution.
#   When the scalp contribution is 0.0, confluence is
#   discarded (no direction to align to).
#
# FINAL DECISION:
#   combined = scalp_contribution + confluence_contribution
#   clamped to [-100, +100]
#   BUY  when combined >= BUY_THRESHOLD
#   SELL when combined <= SELL_THRESHOLD
#   else WAIT
#
# ALTERNATION
# -----------
# No BUY fires after a BUY, and no SELL fires after a
# SELL, until the opposite fires.
#
# The mechanism is upstream:
#     last_signal  ->  looking_for  ->  opposite trigger only
#
# _final_decision contains a defensive re-check for this
# invariant, but it is not the mechanism.
#
# SCALP EVIDENCE IS MANDATORY
# ---------------------------
# Confluence alone cannot trigger a signal.
# ======================================================

from typing import Optional

import importlib.util
from pathlib import Path


# ======================================================
# LOCAL ENGINE PATHS
# ======================================================

ENGINE_ROOT = Path(__file__).resolve().parent
DECISION_ROOT = ENGINE_ROOT.parent


# ======================================================
# IMPORT SCALP SCORE PACKET
# ======================================================

_spec = importlib.util.spec_from_file_location(
    "dcn_scalp_score_import",
    ENGINE_ROOT / "import_scalp_score_packet.py",
)
if _spec is None or _spec.loader is None:
    raise ImportError("Could not load import_scalp_score_packet.py")
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
ScalpScorePacket = _m.ScalpScorePacket


# ======================================================
# IMPORT CONFLUENCE PACKET
# ======================================================

_spec = importlib.util.spec_from_file_location(
    "dcn_confluence_import",
    ENGINE_ROOT / "import_scalp_confluence_score_packet.py",
)
if _spec is None or _spec.loader is None:
    raise ImportError("Could not load import_scalp_confluence_score_packet.py")
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
ScalpConfluenceScorePacket = _m.ScalpConfluenceScorePacket


# ======================================================
# IMPORT INPUTS PACKET
# ======================================================

_spec = importlib.util.spec_from_file_location(
    "dcn_inputs_import",
    DECISION_ROOT / "import_config_packet.py",
)
if _spec is None or _spec.loader is None:
    raise ImportError("Could not load import_config_packet.py")
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
InputsPacket = _m.InputsPacket


# ======================================================
# VALIDATORS
# ======================================================

_VALID_TREND_STATES = {"UP", "DOWN", "UNKNOWN"}
_VALID_LAST_SIGNALS = {"BUY", "SELL"}


def _classify_trend_state(trend_state) -> str:
    if trend_state is None:
        return "UNKNOWN"
    if trend_state in _VALID_TREND_STATES:
        return trend_state
    raise ValueError(
        f"Invalid trend_state: {trend_state!r}. "
        f"Expected one of {_VALID_TREND_STATES}."
    )


def _classify_last_signal(last_signal) -> Optional[str]:
    if last_signal is None:
        return None
    if last_signal in _VALID_LAST_SIGNALS:
        return last_signal
    raise ValueError(
        f"Invalid last_signal: {last_signal!r}. "
        f"Expected one of {_VALID_LAST_SIGNALS} or None."
    )


# ======================================================
# DECISION THRESHOLDS
# ======================================================
# Signal firing thresholds (single tier).
BUY_THRESHOLD  =40.0
SELL_THRESHOLD = -40.0


# ======================================================
# DCN OUTPUT
# ======================================================

class ScalpDCNOutput:
    def __init__(
        self,
        signal_type: str = "WAIT",
        final_score: float = 0.0,
        scalp_score: float = 0.0,
        confluence_score: float = 0.0,
        decision_state: str = "NONE",
        trend_state: str = "UNKNOWN",
        looking_for: Optional[str] = None,
        scalp_contribution: float = 0.0,
        trigger: str = "NO_TRIGGER"
    ):
        self.signal_type = signal_type
        self.final_score = final_score
        self.scalp_score = scalp_score
        self.confluence_score = confluence_score
        self.decision_state = decision_state
        self.trend_state = trend_state
        self.looking_for = looking_for
        self.scalp_contribution = scalp_contribution
        self.trigger = trigger

# ======================================================
# SECTION 8.1a — LOOKING_FOR DETERMINATION
# ======================================================
#
# last_signal is the PRIMARY axis.
# trend_state is SECONDARY.
#
#   (None or BUY)  + UP   -> looking_for = "SELL"
#   (None or SELL) + DOWN -> looking_for = "BUY"
#
# Anything else is not part of this stage and yields None.
# ======================================================

def _determine_looking_for(trend_state_class, last_signal_class):
    looking_for = None

    if last_signal_class is None:
        if trend_state_class == "UP":
            looking_for = "SELL"
        elif trend_state_class == "DOWN":
            looking_for = "BUY"

    elif last_signal_class == "BUY":
        if trend_state_class == "UP":
            looking_for = "SELL"

    elif last_signal_class == "SELL":
        if trend_state_class == "DOWN":
            looking_for = "BUY"

    # All other combinations (including UNKNOWN trend) are
    # out of this stage and remain looking_for = None.
    return looking_for

# ======================================================
# SECTION 8.1b — TRIGGER + SCALP CONTRIBUTION
# ======================================================
#
# Given looking_for and the current scalp packet, produce
# two pieces of information:
#
#   trigger            — did the required reversal condition occur?
#   scalp_contribution — how much scalp evidence, signed
#
# These are two separate questions, answered together
# because they share the same inputs and are always
# consumed together.
#
# Trigger conditions:
#
#   looking_for == "SELL":
#       pivot_high_eligible AND sell_di_score
#         -> SELL_TRIGGER
#
#   looking_for == "BUY":
#       pivot_low_eligible AND buy_di_score
#         -> BUY_TRIGGER
#
#   anything else -> NO_TRIGGER
#
# Scalp contribution:
#
#   NO_TRIGGER     -> 0.0
#
#   SELL_TRIGGER   -> if scalp_score > 0, flip to -abs(scalp_score)
#                     else keep scalp_score as-is (<= 0)
#
#   BUY_TRIGGER    -> if scalp_score < 0, flip to +abs(scalp_score)
#                     else keep scalp_score as-is (>= 0)
#
# Returns:
#   (trigger, scalp_contribution)
# ======================================================

def _trigger_and_contribution(scalp_score_packet, looking_for):

    if looking_for is None:
        return ("NO_TRIGGER", 0.0)

    pivot_high = bool(getattr(scalp_score_packet, "pivot_high_eligible", False))
    pivot_low  = bool(getattr(scalp_score_packet, "pivot_low_eligible",  False))

    diplus  = float(getattr(scalp_score_packet, "scalp_diplus_score",  0.0))
    diminus = float(getattr(scalp_score_packet, "scalp_diminus_score", 0.0))

    DISCORE_MIN = 35.0 * 0.15   # 5.25
    DISCORE_MAX = 35.0 * 0.25   # 8.75

    sell_di_score = (diplus <= DISCORE_MIN and diminus >= DISCORE_MAX)
    buy_di_score  = (diminus <= DISCORE_MIN and diplus >= DISCORE_MAX)

    scalp_score = float(getattr(scalp_score_packet, "scalp_score", 0.0))

    # ---------------- SELL side ----------------
    if looking_for == "SELL" and sell_di_score:

        if scalp_score > 0.0:
            return ("SELL_TRIGGER", -abs(scalp_score))
        return ("SELL_TRIGGER", scalp_score)

    # ---------------- BUY side ----------------
    if looking_for == "BUY" and buy_di_score:

        if scalp_score < 0.0:
            return ("BUY_TRIGGER", abs(scalp_score))
        return ("BUY_TRIGGER", scalp_score)

    # ---------------- no trigger ----------------
    return ("NO_TRIGGER", scalp_score)

# ======================================================
# SECTION 8.1c — CONFLUENCE SIGN ALIGNMENT
# ======================================================
#
# The scalp contribution carries a direction (its sign).
# For now, the confluence contribution is forced to the
# same sign, so that confluence cannot contradict the
# scalp direction.
#
# When Section 7.1 is redesigned, this alignment may be
# replaced by whatever the confluence engine produces on
# its own.
#
# Returns:
#   float — signed confluence contribution (0.0 if none)
# ======================================================

def _align_confluence_score(confluence_score_packet, scalp_contribution):

    if confluence_score_packet is None:
        return 0.0

    if not getattr(confluence_score_packet, "valid", False):
        return 0.0

    confluence_raw = float(
        getattr(confluence_score_packet, "confluence_net_score", 0.0)
    )

    if confluence_raw == 0.0:
        return 0.0

    # Match the sign of the scalp contribution.
    if scalp_contribution < 0.0:
        return -abs(confluence_raw)
    elif scalp_contribution > 0.0:
        return abs(confluence_raw)
    else:
        # Scalp contribution is zero — no direction to align to.
        return 0.0

# ======================================================
# SECTION 8.1d — FINAL DECISION
# ======================================================
#
# Combined score = scalp contribution + aligned confluence.
# Clamped to [-100, +100].
#
# Fires:
#   BUY  when combined >= BUY_THRESHOLD
#   SELL when combined <= SELL_THRESHOLD
#   else WAIT
#
# Under correct upstream behavior this block is
# unreachable: looking_for is always the opposite of
# last_signal, so signal_type can never equal last_signal.
#
# The real alternation mechanism is upstream:
#     last_signal -> looking_for -> opposite trigger only
#
# This check exists only to catch a future upstream
# regression. It is not the decision mechanism.
#
# Returns:
#   (signal_type, final_score, decision_state)
# ======================================================

def _final_decision(trigger, scalp_contribution, confluence_contribution, last_signal_class):

    final_score = scalp_contribution + confluence_contribution
    final_score = max(-100.0, min(100.0, final_score))

    signal_type = "WAIT"
    if trigger == "BUY_TRIGGER":
        if final_score >= BUY_THRESHOLD:
            signal_type = "BUY"

    elif trigger == "SELL_TRIGGER":
        if final_score <= SELL_THRESHOLD:
            signal_type = "SELL"

    suppressed = False

    if signal_type != "WAIT":

        if last_signal_class == "BUY" and signal_type == "BUY":
            signal_type = "WAIT"
            suppressed = True

        elif last_signal_class == "SELL" and signal_type == "SELL":
            signal_type = "WAIT"
            suppressed = True

    if suppressed:
        decision_state = "SUPPRESSED"
    elif signal_type != "WAIT":
        decision_state = "TRIGGERED"
    else:
        decision_state = "NONE"

    return signal_type, final_score, decision_state

def scalp_dcn_engine(
    scalp_score_packet,
    confluence_score_packet,
    inputs_packet,
    trend_state: str = "UNKNOWN",
    last_signal: Optional[str] = None,
):
    # validation guards
    if scalp_score_packet is None:
        return ScalpDCNOutput()
    if not getattr(scalp_score_packet, "valid", False):
        return ScalpDCNOutput()
    if inputs_packet is None:
        return ScalpDCNOutput()

    trend_state_class = _classify_trend_state(trend_state)
    last_signal_class = _classify_last_signal(last_signal)

    looking_for = _determine_looking_for(
        trend_state_class, last_signal_class
    )

    trigger, scalp_contribution = _trigger_and_contribution(
        scalp_score_packet, looking_for
    )

    confluence_contribution = _align_confluence_score(
        confluence_score_packet, scalp_contribution
    )

    signal_type, final_score, decision_state = _final_decision(
        trigger, scalp_contribution, confluence_contribution, last_signal_class
    )

    return ScalpDCNOutput(
        signal_type=signal_type,
        final_score=final_score,
        scalp_score=float(getattr(scalp_score_packet, "scalp_score", 0.0)),
        confluence_score=confluence_contribution,
        decision_state=decision_state,
        trend_state=trend_state_class,
        looking_for=looking_for,
        scalp_contribution=scalp_contribution,
        trigger=trigger,
    )

__all__ = [
    "ScalpDCNOutput",
    "scalp_dcn_engine",
]