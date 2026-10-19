# ======================================================
# SECTION 6.2 — SCALP TREND LIFECYCLE ENGINE
# ======================================================
#
# PURPOSE
# -------
# Converts the independent SCALP ENGINE outputs:
#
#     strength    ∈ [0, 100]
#     exhaustion  ∈ [0, 100]
#
# into a relative lifecycle model.
#
# SECTION 6.1 REMAINS THE OWNER OF:
#     - strength
#     - exhaustion
#
# THIS SECTION ONLY DERIVES:
#     - spread
#     - spread slope
#     - spread curvature
#     - lifecycle position
#     - lifecycle state (rising / decelerating / flattening / declining)
#     - peak candidate
#     - confirmed peak
#     - exhaustion transition
#     - convergence / intersection state
#
# ======================================================
#
# CORE MATHEMATICS
# =================
#
# Strength:           S(t)
# Exhaustion:         E(t)
#
# Lifecycle Spread:   D(t) = S(t) - E(t)
#
# Spread slope:       ΔD(t)  = D(t) - D(t-1)
# Spread curvature:   Δ²D(t) = ΔD(t) - ΔD(t-1)
#
# LIFECYCLE STATES
# ----------------
#     rising        : ΔD > tolerance and Δ²D >= 0
#     decelerating  : ΔD > tolerance and Δ²D < 0
#     flattening    : |ΔD| <= tolerance
#     declining     : ΔD < -tolerance
#
# CONFIRMED PEAK
# --------------
# A non-predictive peak is confirmed when:
#     previous ΔD > 0
#     current  ΔD < 0
#
# Therefore:
#     previous bar = confirmed maximum-spread bar
# The current bar confirms the previous bar.
# No future data is used.
#
# ======================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ======================================================
# CONSTANTS
# ======================================================

SCORE_MIN = 0.0
SCORE_MAX = 100.0

SPREAD_MIN = -100.0
SPREAD_MAX = 100.0

# Small tolerance used only for classifying a near-flat slope.
# Does NOT alter the raw scores.
FLAT_SLOPE_TOLERANCE = 0.5

# Difference between strength and exhaustion considered
# "near equilibrium".
EQUILIBRIUM_TOLERANCE = 5.0


# ======================================================
# HELPERS
# ======================================================

def _clamp(value: float, minimum: float, maximum: float) -> float:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


# ======================================================
# OUTPUT
# ======================================================

@dataclass
class ScalpLifecycleOutput:

    # --- Raw Section 6.1 values ---
    strength: float = 0.0
    exhaustion: float = 0.0

    # --- Primary relationship ---
    spread: float = 0.0

    # --- First-order movement ---
    strength_slope: float = 0.0
    exhaustion_slope: float = 0.0
    spread_slope: float = 0.0

    # --- Second-order movement ---
    strength_slope_change: float = 0.0
    exhaustion_slope_change: float = 0.0
    spread_slope_change: float = 0.0

    # --- Relative lifecycle position ---
    lifecycle_position: float = 0.0

    # --- Lifecycle state ---
    rising: bool = False
    decelerating: bool = False
    flattening: bool = False
    declining: bool = False

    # --- Peak state ---
    peak_candidate: bool = False
    peak_confirmed: bool = False
    peak_bar_index: Optional[int] = None
    peak_bar_time: Optional[int] = None
    peak_spread: float = 0.0
    peak_strength: float = 0.0
    peak_exhaustion: float = 0.0

    # --- Exhaustion transition ---
    exhaustion_transition: bool = False

    # --- Curve relationship ---
    converging: bool = False
    diverging: bool = False
    near_equilibrium: bool = False
    crossed_equilibrium: bool = False

    # --- Cycle information ---
    cycle_age: int = 0


# ======================================================
# INTERNAL STATE
# ======================================================

@dataclass
class _LifecycleState:

    initialized: bool = False

    # Previous raw values
    previous_strength: float = 0.0
    previous_exhaustion: float = 0.0
    previous_spread: float = 0.0
    previous_bar_time: Optional[int] = None
    previous_bar_index: Optional[int] = None

    # Previous slopes
    previous_strength_slope: float = 0.0
    previous_exhaustion_slope: float = 0.0
    previous_spread_slope: float = 0.0

    # Historical lifecycle range
    minimum_spread: float = 0.0
    maximum_spread: float = 0.0

    # Maximum-spread observation
    peak_spread: float = 0.0
    peak_strength: float = 0.0
    peak_exhaustion: float = 0.0
    peak_bar_index: Optional[int] = None
    peak_bar_time: Optional[int] = None

    # Peak-fired guard
    #
    # Once peak_confirmed has fired, we do not fire again
    # until the state is reset by the owner (DCN).
    _peak_fired: bool = False

    # Previous sign of spread
    previous_spread_sign: int = 0

    # Bar counter (internal)
    bar_index: int = -1

    # Cycle age
    cycle_age: int = 0


# ======================================================
# TIMEFRAME-SPECIFIC STATE
# ======================================================

_STATES: dict[str, _LifecycleState] = {}


def _get_state(tf: str) -> _LifecycleState:
    state = _STATES.get(tf)
    if state is None:
        state = _LifecycleState()
        _STATES[tf] = state
    return state


# ======================================================
# RESET
# ======================================================

def reset_scalp_lifecycle(tf: str) -> None:
    """
    Reset lifecycle state for a specific timeframe.

    Should only be called by the owner of episode / cycle
    state — typically DCN — when a genuine new cycle has
    been established.
    """
    _STATES[tf] = _LifecycleState()


def reset_all_scalp_lifecycles() -> None:
    """Reset every timeframe lifecycle state."""
    _STATES.clear()


# ======================================================
# MAIN LIFECYCLE ENGINE
# ======================================================

def scalp_lifecycle(
    strength: float,
    exhaustion: float,
    tf: str,
    *,
    bar_time: Optional[int] = None,
    external_bar_index: Optional[int] = None,
) -> ScalpLifecycleOutput:
    """
    Process one closed bar of Section 6.1 output.

    No prediction.
    No future data.
    No modification of raw strength/exhaustion.

    Parameters
    ----------
    strength, exhaustion : float
        Section 6.1 outputs for this bar.
    tf : str
        Timeframe key ("1", "5", "15", ...).
    bar_time : Optional[int]
        Exchange bar open time (ms). Passed through to output
        for peak_bar_time tracking.
    external_bar_index : Optional[int]
        Runner's absolute bar index. If provided, used for
        peak_bar_index output. Otherwise internal counter.
    """

    state = _get_state(tf)

    # --- Sanitize source scores ---
    strength = _clamp(float(strength), SCORE_MIN, SCORE_MAX)
    exhaustion = _clamp(float(exhaustion), SCORE_MIN, SCORE_MAX)

    # ==================================================
    # FIRST BAR
    # ==================================================

    if not state.initialized:

        state.initialized = True
        state.bar_index = 0
        state.cycle_age = 1

        state.previous_strength = strength
        state.previous_exhaustion = exhaustion
        state.previous_bar_time = bar_time
        state.previous_bar_index = external_bar_index

        spread = strength - exhaustion
        state.previous_spread = spread

        state.minimum_spread = spread
        state.maximum_spread = spread

        state.peak_spread = spread
        state.peak_strength = strength
        state.peak_exhaustion = exhaustion
        state.peak_bar_index = external_bar_index
        state.peak_bar_time = bar_time

        if spread > 0.0:
            state.previous_spread_sign = 1
        elif spread < 0.0:
            state.previous_spread_sign = -1
        else:
            state.previous_spread_sign = 0

        return ScalpLifecycleOutput(
            strength=strength,
            exhaustion=exhaustion,
            spread=spread,
            lifecycle_position=0.0,
            cycle_age=1,
            peak_spread=spread,
            peak_strength=strength,
            peak_exhaustion=exhaustion,
            peak_bar_index=external_bar_index,
            peak_bar_time=bar_time,
        )

    # ==================================================
    # ADVANCE BAR
    # ==================================================

    state.bar_index += 1
    state.cycle_age += 1

    # --- Spread ---
    spread = strength - exhaustion

    # --- First-order slopes ---
    strength_slope = strength - state.previous_strength
    exhaustion_slope = exhaustion - state.previous_exhaustion
    spread_slope = spread - state.previous_spread

    # --- Second-order / curvature ---
    strength_slope_change = (
        strength_slope - state.previous_strength_slope
    )
    exhaustion_slope_change = (
        exhaustion_slope - state.previous_exhaustion_slope
    )
    spread_slope_change = (
        spread_slope - state.previous_spread_slope
    )

    # --- Update observed spread range ---
    if spread < state.minimum_spread:
        state.minimum_spread = spread

    if spread > state.maximum_spread:
        state.maximum_spread = spread
        state.peak_spread = spread
        state.peak_strength = strength
        state.peak_exhaustion = exhaustion
        state.peak_bar_index = (
            external_bar_index
            if external_bar_index is not None
            else state.bar_index
        )
        state.peak_bar_time = bar_time

    # --- Lifecycle position ---
    spread_range = state.maximum_spread - state.minimum_spread
    if spread_range > 0.0:
        lifecycle_position = (
            (spread - state.minimum_spread) / spread_range
        ) * 100.0
    else:
        lifecycle_position = 0.0

    lifecycle_position = _clamp(lifecycle_position, 0.0, 100.0)

    # ==================================================
    # PEAK DETECTION
    # ==================================================
    #
    # Peak candidate:
    #     previous slope > 0 and current slope <= 0
    #
    # Peak confirmed:
    #     previous slope > 0 and current slope < 0
    #     AND we have not already fired this peak
    #
    # Once fired, _peak_fired = True prevents repeated
    # signals until the owner resets the state.
    # ==================================================

    peak_candidate = (
        state.previous_spread_slope > 0.0
        and spread_slope <= 0.0
    )

    peak_confirmed = (
        state.previous_spread_slope > 0.0
        and spread_slope < 0.0
        and not state._peak_fired
    )

    confirmed_peak_bar_index = None
    confirmed_peak_bar_time = None

    if peak_confirmed:
        # The peak occurred on the PREVIOUS bar.
        confirmed_peak_bar_index = (
            state.previous_bar_index
            if state.previous_bar_index is not None
            else (state.bar_index - 1)
        )
        confirmed_peak_bar_time = state.previous_bar_time

        # Guard against repeat firing for the same peak.
        state._peak_fired = True

    # ==================================================
    # STATE DIRECTION
    # ==================================================
    #
    #   rising        : ΔD > tolerance and Δ²D >= 0
    #   decelerating  : ΔD > tolerance and Δ²D < 0
    #   flattening    : |ΔD| <= tolerance
    #   declining     : ΔD < -tolerance
    #
    # decelerating does NOT mean reversal.
    # It means the lifecycle is still advancing,
    # but its rate of advancement is decreasing.
    # ==================================================

    rising = spread_slope > FLAT_SLOPE_TOLERANCE

    decelerating = (
        spread_slope > FLAT_SLOPE_TOLERANCE
        and spread_slope_change < 0.0
    )

    flattening = abs(spread_slope) <= FLAT_SLOPE_TOLERANCE

    declining = spread_slope < -FLAT_SLOPE_TOLERANCE

    # --- Exhaustion transition ---
    exhaustion_transition = (
        strength_slope < 0.0
        and exhaustion_slope > 0.0
    )

    # --- Convergence / divergence ---
    converging = spread_slope < 0.0
    diverging = spread_slope > 0.0

    # --- Equilibrium ---
    near_equilibrium = abs(spread) <= EQUILIBRIUM_TOLERANCE

    current_sign = 0
    if spread > 0.0:
        current_sign = 1
    elif spread < 0.0:
        current_sign = -1

    crossed_equilibrium = (
        state.previous_spread_sign != 0
        and current_sign != 0
        and current_sign != state.previous_spread_sign
    )

    # ==================================================
    # OUTPUT
    # ==================================================

    output = ScalpLifecycleOutput(

        strength=strength,
        exhaustion=exhaustion,
        spread=spread,

        strength_slope=strength_slope,
        exhaustion_slope=exhaustion_slope,
        spread_slope=spread_slope,

        strength_slope_change=strength_slope_change,
        exhaustion_slope_change=exhaustion_slope_change,
        spread_slope_change=spread_slope_change,

        lifecycle_position=lifecycle_position,

        rising=rising,
        decelerating=decelerating,
        flattening=flattening,
        declining=declining,

        peak_candidate=peak_candidate,
        peak_confirmed=peak_confirmed,
        peak_bar_index=confirmed_peak_bar_index,
        peak_bar_time=confirmed_peak_bar_time,
        peak_spread=state.peak_spread,
        peak_strength=state.peak_strength,
        peak_exhaustion=state.peak_exhaustion,

        exhaustion_transition=exhaustion_transition,

        converging=converging,
        diverging=diverging,
        near_equilibrium=near_equilibrium,
        crossed_equilibrium=crossed_equilibrium,

        cycle_age=state.cycle_age,
    )

    # ==================================================
    # SAVE CURRENT BAR
    # ==================================================

    state.previous_strength = strength
    state.previous_exhaustion = exhaustion
    state.previous_spread = spread
    state.previous_bar_time = bar_time
    state.previous_bar_index = external_bar_index

    state.previous_strength_slope = strength_slope
    state.previous_exhaustion_slope = exhaustion_slope
    state.previous_spread_slope = spread_slope

    state.previous_spread_sign = current_sign

    return output


# ======================================================
# SECTION 6.1 ADAPTER
# ======================================================

def scalp_lifecycle_from_output(
    scalp_output,
    tf: str,
    *,
    bar_time: Optional[int] = None,
    external_bar_index: Optional[int] = None,
) -> ScalpLifecycleOutput:
    """
    Adapter from Section 6.1 ScalpOutput.

    Section 6.1 remains the source of:
        strength
        exhaustion

    Section 6.2 derives lifecycle information from them.
    """

    if scalp_output is None:
        return ScalpLifecycleOutput()

    return scalp_lifecycle(
        strength=float(getattr(scalp_output, "strength", 0.0)),
        exhaustion=float(getattr(scalp_output, "exhaustion", 0.0)),
        tf=tf,
        bar_time=bar_time,
        external_bar_index=external_bar_index,
    )


# ======================================================
# PUBLIC API
# ======================================================

__all__ = [
    "ScalpLifecycleOutput",
    "scalp_lifecycle",
    "scalp_lifecycle_from_output",
    "reset_scalp_lifecycle",
    "reset_all_scalp_lifecycles",
]