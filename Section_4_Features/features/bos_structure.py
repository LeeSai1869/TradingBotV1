# ======================================================
# SECTION 4 — BOS STRUCTURE
# ======================================================
# Market structure, pivots, BOS, CHOCH, protected levels.
# Plus:
#   - Swing pivot detection (faithful Pine port, 25% confirmation)
#   - Flip candidate engine (fast, per-bar reversal tracking)
#
# Swing engine and flip candidate engine are INDEPENDENT:
#   - Swing engine: slow, waits for 25% retracement.
#   - Flip candidate: fast, flips on first opposite close.
#
# Flip events are consumed by Section 6.1 as reversal triggers.
#
# STATE KEYING:
#   All per-tf state is keyed by (symbol, tf) so that multiple
#   symbols processed in the same process do not leak state.
# ======================================================

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import math


# ======================================================
# PART 1 — CORE STRUCTURES
# ======================================================

@dataclass
class Pivot:
    price: float
    bar: int
    time: Optional[int] = None
    pivot_type: int = 0


@dataclass
class StructureMemory:
    last_confirmed_pivot_type: int = 0
    latest_confirmed_pivot_high: Optional[float] = None
    latest_confirmed_pivot_low: Optional[float] = None

    current_active_pivot_type: int = 0
    current_active_pivot_high: Optional[float] = None
    current_active_pivot_low: Optional[float] = None
    current_active_pivot_bar: Optional[int] = None

    prev_active_pivot_type: int = 0
    prev_active_pivot_high: Optional[float] = None
    prev_active_pivot_low: Optional[float] = None
    prev_active_pivot_bar: Optional[int] = None

    candidate_pivot: int = 0
    candidate_pivot_high_price: Optional[float] = None
    candidate_pivot_high_bar: Optional[int] = None
    candidate_pivot_high_time: Optional[int] = None
    candidate_pivot_low_price: Optional[float] = None
    candidate_pivot_low_bar: Optional[int] = None
    candidate_pivot_low_time: Optional[int] = None

    current_swing_direction: str = "NONE"
    swing_transition: int = 0

    nearest_swing_high: Optional[float] = None
    nearest_swing_high_bar: Optional[int] = None
    nearest_swing_high_time: Optional[int] = None
    distance_to_swing_high_pct: Optional[float] = None

    nearest_swing_low: Optional[float] = None
    nearest_swing_low_bar: Optional[int] = None
    nearest_swing_low_time: Optional[int] = None
    distance_to_swing_low_pct: Optional[float] = None

    new_high_type: str = ""
    new_low_type: str = ""
    high_pivot_count: int = 0
    low_pivot_count: int = 0

    pivot_high_flip_this_bar: bool = False
    pivot_low_flip_this_bar: bool = False

    structure_origin_bar: Optional[int] = None
    structure_origin_age: int = 0
    structure_start_bar: Optional[int] = None
    structure_age: int = 0
    current_structure: str = "NONE"
    new_structure_established: bool = False

    bullish_structure_active: bool = False
    bearish_structure_active: bool = False
    range_structure_active: bool = False

    valid_pivot_high: bool = False
    valid_pivot_low: bool = False
    structure_established: str = ""

    protected_low: Optional[float] = None
    protected_low_bar: Optional[int] = None
    protected_high: Optional[float] = None
    protected_high_bar: Optional[int] = None
    protected_high_type: str = ""
    protected_low_type: str = ""

    active_transition: int = 0
    active_transition_type: str = ""
    latest_transition: str = ""
    previous_transition: str = ""
    candidate_transition_high: Optional[float] = None
    candidate_transition_high_bar: Optional[int] = None
    candidate_transition_low: Optional[float] = None
    candidate_transition_low_bar: Optional[int] = None

    active_bos: int = 0
    active_bos_type: str = ""
    last_structure_bos: str = ""
    bull_bos_count: int = 0
    bear_bos_count: int = 0
    range_bos_count: int = 0
    bull_bos_distance_atr: Optional[float] = None
    bear_bos_distance_atr: Optional[float] = None
    last_structure_choch: str = ""
    bos_candidate_pivot_type: int = 0
    bos_candidate_pivot_bar: Optional[int] = None

    structure_range_high: Optional[float] = None
    structure_range_low: Optional[float] = None
    structure_range_high_bar: Optional[int] = None
    structure_range_low_bar: Optional[int] = None
    established_range_distance: Optional[float] = None
    price_inside_range: bool = False


_structure_memory_store: Dict[Tuple[str, str], StructureMemory] = {}


def get_structure_memory(symbol: str, tf: str) -> StructureMemory:
    key = (symbol, tf)
    if key not in _structure_memory_store:
        _structure_memory_store[key] = StructureMemory()
    return _structure_memory_store[key]


# ======================================================
# PART 2 — OUTPUT CONTRACT
# ======================================================

@dataclass
class MarketStructure:
    last_confirmed_pivot_type: int = 0
    latest_confirmed_pivot_high: Optional[float] = None
    latest_confirmed_pivot_low: Optional[float] = None

    current_active_pivot_type: int = 0
    current_active_pivot_high: Optional[float] = None
    current_active_pivot_low: Optional[float] = None
    current_active_pivot_bar: Optional[int] = None

    prev_active_pivot_type: int = 0
    prev_active_pivot_high: Optional[float] = None
    prev_active_pivot_low: Optional[float] = None
    prev_active_pivot_bar: Optional[int] = None

    candidate_pivot: int = 0
    candidate_pivot_high_price: Optional[float] = None
    candidate_pivot_high_bar: Optional[int] = None
    candidate_pivot_high_time: Optional[int] = None
    candidate_pivot_low_price: Optional[float] = None
    candidate_pivot_low_bar: Optional[int] = None
    candidate_pivot_low_time: Optional[int] = None

    current_swing_direction: str = "NONE"
    swing_transition: int = 0

    nearest_swing_high: Optional[float] = None
    nearest_swing_high_bar: Optional[int] = None
    nearest_swing_high_time: Optional[int] = None
    distance_to_swing_high_pct: Optional[float] = None

    nearest_swing_low: Optional[float] = None
    nearest_swing_low_bar: Optional[int] = None
    nearest_swing_low_time: Optional[int] = None
    distance_to_swing_low_pct: Optional[float] = None

    new_high_type: str = ""
    new_low_type: str = ""
    high_pivot_count: int = 0
    low_pivot_count: int = 0

    structure_origin_bar: Optional[int] = None
    structure_origin_age: int = 0
    structure_start_bar: Optional[int] = None
    structure_age: int = 0
    current_structure: str = "NONE"
    new_structure_established: bool = False

    bullish_structure_active: bool = False
    bearish_structure_active: bool = False
    range_structure_active: bool = False

    valid_pivot_high: bool = False
    valid_pivot_low: bool = False
    structure_established: str = ""

    protected_low: Optional[float] = None
    protected_low_bar: Optional[int] = None
    protected_high: Optional[float] = None
    protected_high_bar: Optional[int] = None
    protected_high_type: str = ""
    protected_low_type: str = ""

    active_transition: int = 0
    active_transition_type: str = ""
    latest_transition: str = ""
    previous_transition: str = ""
    candidate_transition_high: Optional[float] = None
    candidate_transition_high_bar: Optional[int] = None
    candidate_transition_low: Optional[float] = None
    candidate_transition_low_bar: Optional[int] = None

    active_bos: int = 0
    active_bos_type: str = ""
    last_structure_bos: str = ""
    bull_bos_count: int = 0
    bear_bos_count: int = 0
    range_bos_count: int = 0
    bull_bos_distance_atr: Optional[float] = None
    bear_bos_distance_atr: Optional[float] = None
    last_structure_choch: str = ""
    bos_candidate_pivot_type: int = 0
    bos_candidate_pivot_bar: Optional[int] = None

    structure_range_high: Optional[float] = None
    structure_range_low: Optional[float] = None
    structure_range_high_bar: Optional[int] = None
    structure_range_low_bar: Optional[int] = None
    established_range_distance: Optional[float] = None
    price_inside_range: bool = False


# ======================================================
# PART 3 — UPDATE_MARKET_STRUCTURE
# ======================================================

def update_market_structure(
    symbol: str,
    tf: str,
    bar_index: int,
    time: Optional[int],
    c: float,
    h: float,
    l: float,
    atr: Optional[float],
    pivot_high: Optional[float],
    pivot_low: Optional[float],
    pivot_left: int = 3,
    pivot_right: int = 1,
    is_confirmed: bool = True,
) -> MarketStructure:

    mem = get_structure_memory(symbol, tf)
    result = MarketStructure()

    # --- Pivot detection & confirmation ---
    if is_confirmed and pivot_high is not None:
        mem.candidate_pivot = 1
        mem.candidate_pivot_high_price = pivot_high
        mem.candidate_pivot_high_bar = bar_index - pivot_right
        mem.candidate_pivot_high_time = time
        mem.valid_pivot_high = True

        if mem.current_active_pivot_type in (-1, 0):
            mem.prev_active_pivot_type = mem.current_active_pivot_type
            mem.prev_active_pivot_high = mem.current_active_pivot_high
            mem.prev_active_pivot_low = mem.current_active_pivot_low
            mem.prev_active_pivot_bar = mem.current_active_pivot_bar

            mem.current_active_pivot_type = 1
            mem.current_active_pivot_high = pivot_high
            mem.current_active_pivot_bar = bar_index - pivot_right
            mem.latest_confirmed_pivot_high = pivot_high
            mem.last_confirmed_pivot_type = 1
            mem.high_pivot_count += 1

    if is_confirmed and pivot_low is not None:
        mem.candidate_pivot = -1
        mem.candidate_pivot_low_price = pivot_low
        mem.candidate_pivot_low_bar = bar_index - pivot_right
        mem.candidate_pivot_low_time = time
        mem.valid_pivot_low = True

        if mem.current_active_pivot_type in (1, 0):
            mem.prev_active_pivot_type = mem.current_active_pivot_type
            mem.prev_active_pivot_high = mem.current_active_pivot_high
            mem.prev_active_pivot_low = mem.current_active_pivot_low
            mem.prev_active_pivot_bar = mem.current_active_pivot_bar

            mem.current_active_pivot_type = -1
            mem.current_active_pivot_low = pivot_low
            mem.current_active_pivot_bar = bar_index - pivot_right
            mem.latest_confirmed_pivot_low = pivot_low
            mem.last_confirmed_pivot_type = -1
            mem.low_pivot_count += 1

    # --- Swing direction ---
    if mem.current_active_pivot_type == 1 and mem.prev_active_pivot_type == -1:
        mem.current_swing_direction = "BULLISH"
    elif mem.current_active_pivot_type == -1 and mem.prev_active_pivot_type == 1:
        mem.current_swing_direction = "BEARISH"
    else:
        mem.current_swing_direction = "NONE"

    # --- Nearest swings ---
    if mem.latest_confirmed_pivot_high is not None:
        mem.nearest_swing_high = mem.latest_confirmed_pivot_high
        mem.nearest_swing_high_bar = (
            mem.current_active_pivot_bar
            if mem.current_active_pivot_type == 1
            else mem.prev_active_pivot_bar
        )
        if c != 0:
            mem.distance_to_swing_high_pct = (
                (mem.nearest_swing_high - c) / c * 100
            )

    if mem.latest_confirmed_pivot_low is not None:
        mem.nearest_swing_low = mem.latest_confirmed_pivot_low
        mem.nearest_swing_low_bar = (
            mem.current_active_pivot_bar
            if mem.current_active_pivot_type == -1
            else mem.prev_active_pivot_bar
        )
        if c != 0:
            mem.distance_to_swing_low_pct = (
                (c - mem.nearest_swing_low) / c * 100
            )

    # --- Protected High / Low ---
    if (
        mem.current_swing_direction == "BULLISH"
        and mem.latest_confirmed_pivot_low is not None
    ):
        mem.protected_low = mem.latest_confirmed_pivot_low
        mem.protected_low_bar = mem.nearest_swing_low_bar
        mem.protected_low_type = "SWING_LOW"

    if (
        mem.current_swing_direction == "BEARISH"
        and mem.latest_confirmed_pivot_high is not None
    ):
        mem.protected_high = mem.latest_confirmed_pivot_high
        mem.protected_high_bar = mem.nearest_swing_high_bar
        mem.protected_high_type = "SWING_HIGH"

    # --- Reset BOS ---
    mem.active_bos = 0
    mem.active_bos_type = ""

    # --- Bullish BOS ---
    if (
        mem.protected_high is not None
        and c > mem.protected_high
        and mem.current_swing_direction in ("BEARISH", "NONE", "RANGE")
    ):
        mem.active_bos = 1
        mem.active_bos_type = "BULLISH_BOS"
        mem.last_structure_bos = "BULLISH_BOS"
        mem.bull_bos_count += 1

        if atr is not None and atr > 0:
            mem.bull_bos_distance_atr = (c - mem.protected_high) / atr

        mem.previous_transition = mem.latest_transition
        mem.latest_transition = "BULLISH_BOS"
        mem.active_transition = 1
        mem.active_transition_type = "BULLISH_BOS"

        mem.current_structure = "BULLISH"
        mem.bullish_structure_active = True
        mem.bearish_structure_active = False
        mem.range_structure_active = False
        mem.new_structure_established = True
        mem.structure_start_bar = bar_index
        mem.structure_established = "BULLISH"

        if mem.latest_confirmed_pivot_low is not None:
            mem.protected_low = mem.latest_confirmed_pivot_low
            mem.protected_low_bar = mem.nearest_swing_low_bar
            mem.protected_low_type = "STRUCTURE_ORIGIN"

    # --- Bearish BOS ---
    if (
        mem.protected_low is not None
        and c < mem.protected_low
        and mem.current_swing_direction in ("BULLISH", "NONE", "RANGE")
    ):
        mem.active_bos = -1
        mem.active_bos_type = "BEARISH_BOS"
        mem.last_structure_bos = "BEARISH_BOS"
        mem.bear_bos_count += 1

        if atr is not None and atr > 0:
            mem.bear_bos_distance_atr = (mem.protected_low - c) / atr

        mem.previous_transition = mem.latest_transition
        mem.latest_transition = "BEARISH_BOS"
        mem.active_transition = -1
        mem.active_transition_type = "BEARISH_BOS"

        mem.current_structure = "BEARISH"
        mem.bearish_structure_active = True
        mem.bullish_structure_active = False
        mem.range_structure_active = False
        mem.new_structure_established = True
        mem.structure_start_bar = bar_index
        mem.structure_established = "BEARISH"

        if mem.latest_confirmed_pivot_high is not None:
            mem.protected_high = mem.latest_confirmed_pivot_high
            mem.protected_high_bar = mem.nearest_swing_high_bar
            mem.protected_high_type = "STRUCTURE_ORIGIN"

    # --- CHOCH (bullish, in a bearish structure) ---
    if (
        mem.current_structure == "BEARISH"
        and mem.nearest_swing_high is not None
        and c > mem.nearest_swing_high
        and mem.active_bos == 0
    ):
        mem.last_structure_choch = "BULLISH_CHOCH"
        mem.previous_transition = mem.latest_transition
        mem.latest_transition = "BULLISH_CHOCH"
        mem.active_transition = 1
        mem.active_transition_type = "BULLISH_CHOCH"

    # --- CHOCH (bearish, in a bullish structure) ---
    if (
        mem.current_structure == "BULLISH"
        and mem.nearest_swing_low is not None
        and c < mem.nearest_swing_low
        and mem.active_bos == 0
    ):
        mem.last_structure_choch = "BEARISH_CHOCH"
        mem.previous_transition = mem.latest_transition
        mem.latest_transition = "BEARISH_CHOCH"
        mem.active_transition = -1
        mem.active_transition_type = "BEARISH_CHOCH"

    return result


# ======================================================
# PART 4 — SWING PIVOT DETECTION (FAITHFUL PINE PORT)
# ======================================================
#
# The swing engine is SLOW and RULE-BASED:
#   - tracks a candidate high or low during a run
#   - confirms the pivot when price retraces
#     SWING_VALIDATION_RATIO (25%) of the swing
#   - maintains latest_confirmed_pivot_high / low
#
# The swing engine does NOT emit flip events. Flip events
# come from Part 5 (flip candidate engine), which is
# independent of this slower lifecycle.
#
# Wipes (setting confirmed anchors to None after the
# opposite side confirms) are intentionally removed.
# Each side's anchor is only replaced by its own new
# confirmation, never wiped. This keeps the swing's two
# anchors always populated once each side has confirmed.
#
# STATE KEYING:
#   _SWING_PIVOT_STATES is keyed by (symbol, tf).
# ======================================================

SWING_VALIDATION_RATIO = 0.25


@dataclass
class _SwingPivotState:
    candidate_pivot: int = 0
    candidate_pivot_high_price: Optional[float] = None
    candidate_pivot_high_bar: Optional[int] = None
    candidate_pivot_high_time: Optional[int] = None
    candidate_pivot_low_price: Optional[float] = None
    candidate_pivot_low_bar: Optional[int] = None
    candidate_pivot_low_time: Optional[int] = None

    prev_candidate_pivot_high_bar: Optional[int] = None
    prev_candidate_pivot_low_bar: Optional[int] = None

    latest_confirmed_pivot_high: Optional[float] = None
    latest_confirmed_pivot_low: Optional[float] = None

    current_swing_direction: str = "NO SWING"
    swing_transition: int = 0

    pivot_high_confirmation_price: Optional[float] = None
    pivot_low_confirmation_price: Optional[float] = None

    swing_high_price_array: List[float] = field(default_factory=list)
    swing_high_bar_array: List[int] = field(default_factory=list)
    swing_high_time_array: List[int] = field(default_factory=list)

    swing_low_price_array: List[float] = field(default_factory=list)
    swing_low_bar_array: List[int] = field(default_factory=list)
    swing_low_time_array: List[int] = field(default_factory=list)

    current_active_pivot_type_array: List[int] = field(default_factory=list)
    prev_active_pivot_type_array: List[int] = field(default_factory=list)

    last_confirmed_pivot_type: int = 0


_SWING_PIVOT_STATES: Dict[Tuple[str, str], _SwingPivotState] = {}


def _get_swing_state(symbol: str, tf: str) -> _SwingPivotState:
    key = (symbol, tf)
    st = _SWING_PIVOT_STATES.get(key)
    if st is None:
        st = _SwingPivotState()
        _SWING_PIVOT_STATES[key] = st
    return st


def reset_swing_pivot_state(symbol: str, tf: str) -> None:
    _SWING_PIVOT_STATES[(symbol, tf)] = _SwingPivotState()


def reset_all_swing_pivot_states() -> None:
    _SWING_PIVOT_STATES.clear()


@dataclass
class SwingPivotOutput:
    candidate_pivot: int = 0
    candidate_pivot_high_price: Optional[float] = None
    candidate_pivot_high_bar: Optional[int] = None
    candidate_pivot_high_time: Optional[int] = None
    candidate_pivot_low_price: Optional[float] = None
    candidate_pivot_low_bar: Optional[int] = None
    candidate_pivot_low_time: Optional[int] = None

    latest_confirmed_pivot_high: Optional[float] = None
    latest_confirmed_pivot_low: Optional[float] = None

    current_swing_direction: str = "NO SWING"
    swing_transition: int = 0

    pivot_high_confirmation_price: Optional[float] = None
    pivot_low_confirmation_price: Optional[float] = None

    current_active_pivot_type: int = 0
    current_active_pivot_high: Optional[float] = None
    current_active_pivot_low: Optional[float] = None
    current_active_pivot_bar: Optional[int] = None

    prev_active_pivot_type: int = 0
    prev_active_pivot_high: Optional[float] = None
    prev_active_pivot_low: Optional[float] = None
    prev_active_pivot_bar: Optional[int] = None

    nearest_swing_high: Optional[float] = None
    nearest_swing_high_bar: Optional[int] = None
    nearest_swing_high_time: Optional[int] = None
    distance_to_swing_high_pct: Optional[float] = None

    nearest_swing_low: Optional[float] = None
    nearest_swing_low_bar: Optional[int] = None
    nearest_swing_low_time: Optional[int] = None
    distance_to_swing_low_pct: Optional[float] = None

    pivot_high_confirmed_this_bar: bool = False
    pivot_low_confirmed_this_bar: bool = False

    last_confirmed_pivot_type: int = 0
    swing_high_count: int = 0
    swing_low_count: int = 0


def update_swing_pivots(
    *,
    symbol: str,
    tf: str,
    bar_index: int,
    time: Optional[int],
    o: float,
    h: float,
    l: float,
    c: float,
    prev_h: Optional[float],
    prev_l: Optional[float],
    is_confirmed: bool = True,
) -> SwingPivotOutput:

    st = _get_swing_state(symbol, tf)
    out = SwingPivotOutput()

    if not is_confirmed:
        return _swing_snapshot(st, out)

    # --------------------------------------------------
    # INITIALIZE CANDIDATE PIVOT
    # --------------------------------------------------
    if st.candidate_pivot == 0:
        if prev_h is not None and h > prev_h:
            st.candidate_pivot = 1
            st.candidate_pivot_high_price = h
            st.candidate_pivot_high_bar = bar_index
            st.candidate_pivot_high_time = time
            st.current_swing_direction = "SWING_UP"
        elif prev_l is not None and l < prev_l:
            st.candidate_pivot = -1
            st.candidate_pivot_low_price = l
            st.candidate_pivot_low_bar = bar_index
            st.candidate_pivot_low_time = time
            st.current_swing_direction = "SWING_DOWN"

    # --------------------------------------------------
    # UPDATE CANDIDATE PIVOT HIGH
    # --------------------------------------------------
    if st.candidate_pivot == 1:
        if st.candidate_pivot_high_price is None or h > st.candidate_pivot_high_price:
            st.prev_candidate_pivot_high_bar = st.candidate_pivot_high_bar
            st.candidate_pivot_high_price = h
            st.candidate_pivot_high_bar = bar_index
            st.candidate_pivot_high_time = time
            st.current_swing_direction = "SWING_UP"
            st.swing_transition = 0

    if len(st.swing_low_price_array) > 0 and st.candidate_pivot_high_price is not None:
        st.latest_confirmed_pivot_low = st.swing_low_price_array[-1]
        swing_distance = st.candidate_pivot_high_price - st.latest_confirmed_pivot_low
        if swing_distance > 0:
            validation_distance = swing_distance * SWING_VALIDATION_RATIO
            st.pivot_high_confirmation_price = (
                st.candidate_pivot_high_price - validation_distance
            )

    if (
        st.candidate_pivot_high_price is not None
        and h < st.candidate_pivot_high_price
        and st.pivot_high_confirmation_price is not None
        and c > st.pivot_high_confirmation_price
    ):
        st.current_swing_direction = "SWING_UP"
        st.swing_transition = 1

    elif (
        st.pivot_high_confirmation_price is not None
        and c <= st.pivot_high_confirmation_price
        and st.candidate_pivot_high_price is not None
    ):
        st.last_confirmed_pivot_type = 1
        st.swing_high_price_array.append(st.candidate_pivot_high_price)
        st.swing_high_bar_array.append(st.candidate_pivot_high_bar)
        st.swing_high_time_array.append(st.candidate_pivot_high_time)
        out.pivot_high_confirmed_this_bar = True

        if len(st.current_active_pivot_type_array) > 0:
            st.prev_active_pivot_type_array.append(
                st.current_active_pivot_type_array[-1]
            )
        st.current_active_pivot_type_array.append(1)

        st.latest_confirmed_pivot_high = st.candidate_pivot_high_price

        st.pivot_high_confirmation_price = None
        st.prev_candidate_pivot_high_bar = None
        st.current_swing_direction = "SWING_DOWN"
        st.candidate_pivot = -1
        st.swing_transition = 0
        st.candidate_pivot_low_price = l
        st.candidate_pivot_low_bar = bar_index
        st.candidate_pivot_low_time = time

    # --------------------------------------------------
    # UPDATE CANDIDATE PIVOT LOW
    # --------------------------------------------------
    if st.candidate_pivot == -1:
        if st.candidate_pivot_low_price is None or l < st.candidate_pivot_low_price:
            st.prev_candidate_pivot_low_bar = st.candidate_pivot_low_bar
            st.candidate_pivot_low_price = l
            st.candidate_pivot_low_bar = bar_index
            st.candidate_pivot_low_time = time
            st.current_swing_direction = "SWING_DOWN"
            st.swing_transition = 0

    if len(st.swing_high_price_array) > 0 and st.candidate_pivot_low_price is not None:
        st.latest_confirmed_pivot_high = st.swing_high_price_array[-1]
        swing_distance = st.latest_confirmed_pivot_high - st.candidate_pivot_low_price
        if swing_distance > 0:
            validation_distance = swing_distance * SWING_VALIDATION_RATIO
            st.pivot_low_confirmation_price = (
                st.candidate_pivot_low_price + validation_distance
            )

    if (
        st.candidate_pivot_low_price is not None
        and l > st.candidate_pivot_low_price
        and st.pivot_low_confirmation_price is not None
        and c < st.pivot_low_confirmation_price
    ):
        st.current_swing_direction = "SWING_DOWN"
        st.swing_transition = 1

    elif (
        st.pivot_low_confirmation_price is not None
        and c >= st.pivot_low_confirmation_price
        and st.candidate_pivot_low_price is not None
    ):
        st.last_confirmed_pivot_type = -1
        st.swing_low_price_array.append(st.candidate_pivot_low_price)
        st.swing_low_bar_array.append(st.candidate_pivot_low_bar)
        st.swing_low_time_array.append(st.candidate_pivot_low_time)
        out.pivot_low_confirmed_this_bar = True

        if len(st.current_active_pivot_type_array) > 0:
            st.prev_active_pivot_type_array.append(
                st.current_active_pivot_type_array[-1]
            )
        st.current_active_pivot_type_array.append(-1)

        st.latest_confirmed_pivot_low = st.candidate_pivot_low_price

        st.pivot_low_confirmation_price = None
        st.prev_candidate_pivot_low_bar = None
        st.current_swing_direction = "SWING_UP"
        st.candidate_pivot = 1
        st.swing_transition = 0
        st.candidate_pivot_high_price = h
        st.candidate_pivot_high_bar = bar_index
        st.candidate_pivot_high_time = time

    return _swing_snapshot(st, out, current_close=c)


def _swing_snapshot(
    st: _SwingPivotState,
    out: SwingPivotOutput,
    current_close: Optional[float] = None,
) -> SwingPivotOutput:

    out.candidate_pivot = st.candidate_pivot
    out.candidate_pivot_high_price = st.candidate_pivot_high_price
    out.candidate_pivot_high_bar = st.candidate_pivot_high_bar
    out.candidate_pivot_high_time = st.candidate_pivot_high_time
    out.candidate_pivot_low_price = st.candidate_pivot_low_price
    out.candidate_pivot_low_bar = st.candidate_pivot_low_bar
    out.candidate_pivot_low_time = st.candidate_pivot_low_time

    out.latest_confirmed_pivot_high = st.latest_confirmed_pivot_high
    out.latest_confirmed_pivot_low = st.latest_confirmed_pivot_low

    out.current_swing_direction = st.current_swing_direction
    out.swing_transition = st.swing_transition

    out.pivot_high_confirmation_price = st.pivot_high_confirmation_price
    out.pivot_low_confirmation_price = st.pivot_low_confirmation_price

    sh_count = len(st.swing_high_price_array)
    sl_count = len(st.swing_low_price_array)
    out.swing_high_count = sh_count
    out.swing_low_count = sl_count

    out.current_active_pivot_type = (
        st.current_active_pivot_type_array[-1]
        if len(st.current_active_pivot_type_array) > 0 else 0
    )
    out.current_active_pivot_high = (
        st.swing_high_price_array[-1] if sh_count > 0 else None
    )
    out.current_active_pivot_low = (
        st.swing_low_price_array[-1] if sl_count > 0 else None
    )

    if out.current_active_pivot_type == 1:
        out.current_active_pivot_bar = (
            st.swing_high_bar_array[-1]
            if len(st.swing_high_bar_array) > 0 else None
        )
    elif out.current_active_pivot_type == -1:
        out.current_active_pivot_bar = (
            st.swing_low_bar_array[-1]
            if len(st.swing_low_bar_array) > 0 else None
        )

    out.prev_active_pivot_type = (
        st.prev_active_pivot_type_array[-1]
        if len(st.prev_active_pivot_type_array) > 0 else 0
    )
    out.prev_active_pivot_high = (
        st.swing_high_price_array[-2]
        if out.prev_active_pivot_type == 1 and sh_count > 1 else None
    )
    out.prev_active_pivot_low = (
        st.swing_low_price_array[-2]
        if out.prev_active_pivot_type == -1 and sl_count > 1 else None
    )

    if out.prev_active_pivot_type == 1:
        out.prev_active_pivot_bar = (
            st.swing_high_bar_array[-2]
            if len(st.swing_high_bar_array) > 1 else None
        )
    elif out.prev_active_pivot_type == -1:
        out.prev_active_pivot_bar = (
            st.swing_low_bar_array[-2]
            if len(st.swing_low_bar_array) > 1 else None
        )

    out.last_confirmed_pivot_type = st.last_confirmed_pivot_type

    if current_close is not None:
        if (
            out.current_active_pivot_high is not None
            and out.current_active_pivot_high > current_close
        ):
            out.nearest_swing_high = out.current_active_pivot_high
            out.nearest_swing_high_bar = out.current_active_pivot_bar
            out.nearest_swing_high_time = (
                st.swing_high_time_array[-1]
                if len(st.swing_high_time_array) > 0 else None
            )
            if current_close != 0:
                out.distance_to_swing_high_pct = (
                    (out.nearest_swing_high - current_close) / current_close * 100
                )

        if (
            out.current_active_pivot_low is not None
            and out.current_active_pivot_low < current_close
        ):
            out.nearest_swing_low = out.current_active_pivot_low
            out.nearest_swing_low_bar = out.current_active_pivot_bar
            out.nearest_swing_low_time = (
                st.swing_low_time_array[-1]
                if len(st.swing_low_time_array) > 0 else None
            )
            if current_close != 0:
                out.distance_to_swing_low_pct = (
                    (current_close - out.nearest_swing_low) / current_close * 100
                )

    return out


# ======================================================
# PART 5 — FLIP CANDIDATE ENGINE
# ======================================================
#
# Fast, per-bar flip detection.
#
# Distinct from the swing engine (Part 4):
#   - Swing candidate waits for 25% retracement.
#   - Flip candidate flips on the first opposite close.
#
# These flip events are NOT pivot confirmations. They are
# fast reversal triggers. Field names use "flip_*" to
# avoid any confusion with the swing engine's pivots.
#
# Lifecycle:
#   - Track a high candidate while direction == UP.
#     Update on new highs. On first down-close → flip HIGH.
#     The flip candle becomes the new LOW candidate.
#     Direction switches to DOWN.
#
#   - Track a low candidate while direction == DOWN.
#     Update on new lows. On first up-close → flip LOW.
#     The flip candle becomes the new HIGH candidate.
#     Direction switches to UP.
#
# Important:
#   - The candidate update and the flip check are INDEPENDENT.
#     A bar can make a new extreme AND close against the run
#     on the same bar. Both actions happen.
#   - Doji / equal closes (c == prev_c) do not trigger a flip.
#   - The bootstrap bar does not fire a flip. It only
#     establishes the initial tactical direction.
#
# STATE KEYING:
#   _FLIP_CANDIDATE_STATES is keyed by (symbol, tf).
# ======================================================


@dataclass
class _FlipCandidateState:
    flip_direction: str = "NONE"
    flip_high_candidate_price: Optional[float] = None
    flip_high_candidate_bar: Optional[int] = None
    flip_low_candidate_price: Optional[float] = None
    flip_low_candidate_bar: Optional[int] = None
    previous_close: Optional[float] = None


_FLIP_CANDIDATE_STATES: Dict[Tuple[str, str], _FlipCandidateState] = {}


def _get_flip_state(symbol: str, tf: str) -> _FlipCandidateState:
    key = (symbol, tf)
    st = _FLIP_CANDIDATE_STATES.get(key)
    if st is None:
        st = _FlipCandidateState()
        _FLIP_CANDIDATE_STATES[key] = st
    return st


def reset_flip_candidate_state(symbol: str, tf: str) -> None:
    _FLIP_CANDIDATE_STATES[(symbol, tf)] = _FlipCandidateState()


def reset_all_flip_candidate_states() -> None:
    _FLIP_CANDIDATE_STATES.clear()


@dataclass
class FlipCandidateOutput:
    flip_high_this_bar: bool = False
    flip_low_this_bar: bool = False
    flip_direction: str = "NONE"
    flip_high_candidate_price: Optional[float] = None
    flip_high_candidate_bar: Optional[int] = None
    flip_low_candidate_price: Optional[float] = None
    flip_low_candidate_bar: Optional[int] = None


def update_flip_candidate(
    *,
    symbol: str,
    tf: str,
    bar_index: int,
    h: float,
    l: float,
    c: float,
    prev_h: Optional[float],
    prev_l: Optional[float],
    is_confirmed: bool = True,
) -> FlipCandidateOutput:

    st = _get_flip_state(symbol, tf)
    out = FlipCandidateOutput()

    if not is_confirmed:
        return _flip_snapshot(st, out)

    # --------------------------------------------------
    # BOOTSTRAP — no direction yet
    # --------------------------------------------------
    if st.flip_direction == "NONE":
        if prev_h is not None and h > prev_h:
            st.flip_direction = "UP"
            st.flip_high_candidate_price = h
            st.flip_high_candidate_bar = bar_index
        elif prev_l is not None and l < prev_l:
            st.flip_direction = "DOWN"
            st.flip_low_candidate_price = l
            st.flip_low_candidate_bar = bar_index

    # --------------------------------------------------
    # TRACKING A HIGH CANDIDATE
    # --------------------------------------------------
    elif st.flip_direction == "UP":

        if st.flip_high_candidate_price is None or h > st.flip_high_candidate_price:
            st.flip_high_candidate_price = h
            st.flip_high_candidate_bar = bar_index

        if st.previous_close is not None and c < st.previous_close:
            out.flip_high_this_bar = True

            st.flip_low_candidate_price = l
            st.flip_low_candidate_bar = bar_index

            st.flip_direction = "DOWN"

    # --------------------------------------------------
    # TRACKING A LOW CANDIDATE
    # --------------------------------------------------
    elif st.flip_direction == "DOWN":

        if st.flip_low_candidate_price is None or l < st.flip_low_candidate_price:
            st.flip_low_candidate_price = l
            st.flip_low_candidate_bar = bar_index

        if st.previous_close is not None and c > st.previous_close:
            out.flip_low_this_bar = True

            st.flip_high_candidate_price = h
            st.flip_high_candidate_bar = bar_index

            st.flip_direction = "UP"

    # --------------------------------------------------
    # UPDATE PREVIOUS CLOSE
    # --------------------------------------------------
    st.previous_close = c

    return _flip_snapshot(st, out)


def _flip_snapshot(st: _FlipCandidateState, out: FlipCandidateOutput) -> FlipCandidateOutput:
    out.flip_direction = st.flip_direction
    out.flip_high_candidate_price = st.flip_high_candidate_price
    out.flip_high_candidate_bar = st.flip_high_candidate_bar
    out.flip_low_candidate_price = st.flip_low_candidate_price
    out.flip_low_candidate_bar = st.flip_low_candidate_bar
    return out