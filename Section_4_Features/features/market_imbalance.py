# ======================================================
# MARKET IMBALANCE
# Full FVG + Full Order Blocks (normal + strict) + Full Breakers
# (No surgery – original logic preserved)
# ======================================================

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import math

# ------------------------------------------------------
# FVG structures
# ------------------------------------------------------

@dataclass
class FVGZone:
    low: float
    high: float
    created_bar: int
    strength: float = 0.0
    max_reaction: float = 0.0
    reaction_count: int = 0
    last_reaction_type: int = 0
    reaction_score: float = 0.0
    status: int = 1                  # 1 = active, 0 = mitigated/failed
    age: int = 0
    has_been_touched: bool = False

@dataclass
class FVGMemory:
    bull_fvgs: List[FVGZone] = field(default_factory=list)
    bear_fvgs: List[FVGZone] = field(default_factory=list)

# ------------------------------------------------------
# Order Block / Breaker structures
# ------------------------------------------------------

@dataclass
class OrderBlock:
    high: float
    low: float
    created_bar: int
    atr_at_creation: float = 0.0
    has_fvg: bool = False
    mitigated: bool = False
    invalidated: bool = False
    has_been_mitigated: bool = False
    age: int = 0
    strength: float = 0.0

@dataclass
class Breaker:
    high: float
    low: float
    created_bar: int
    active: bool = True
    mitigated: bool = False
    has_been_mitigated: bool = False
    age: int = 0

@dataclass
class OBMemory:
    # Normal (pure) Order Blocks
    active_bull_ob: Optional[OrderBlock] = None
    active_bear_ob: Optional[OrderBlock] = None

    # Strict Order Blocks
    active_strict_bull_ob: Optional[OrderBlock] = None
    active_strict_bear_ob: Optional[OrderBlock] = None

    # Breakers from normal OBs
    active_bull_breaker: Optional[Breaker] = None
    active_bear_breaker: Optional[Breaker] = None

    # Breakers from strict OBs
    active_strict_bull_breaker: Optional[Breaker] = None
    active_strict_bear_breaker: Optional[Breaker] = None

# ------------------------------------------------------
# Combined memory per (symbol, timeframe)
# ------------------------------------------------------

@dataclass
class ImbalanceMemory:
    fvg: FVGMemory = field(default_factory=FVGMemory)
    ob: OBMemory = field(default_factory=OBMemory)

_imbalance_memory_store: Dict[Tuple[str, str], ImbalanceMemory] = {}

def get_imbalance_memory(symbol: str, tf: str) -> ImbalanceMemory:
    key = (symbol, tf)
    if key not in _imbalance_memory_store:
        _imbalance_memory_store[key] = ImbalanceMemory()
    return _imbalance_memory_store[key]

# ------------------------------------------------------
# Output contract
# ------------------------------------------------------

@dataclass
class MarketImbalance:
    # FVG flags & values
    bull_fvg: bool = False
    bear_fvg: bool = False
    bull_fvg_high: Optional[float] = None
    bull_fvg_low: Optional[float] = None
    bear_fvg_high: Optional[float] = None
    bear_fvg_low: Optional[float] = None

    nearest_bull_fvg_low: Optional[float] = None
    nearest_bull_fvg_high: Optional[float] = None
    nearest_bear_fvg_low: Optional[float] = None
    nearest_bear_fvg_high: Optional[float] = None

    fvg_size: Optional[float] = None
    bull_gap_atr: Optional[float] = None
    bear_gap_atr: Optional[float] = None
    bull_fvg_strength: Optional[float] = None
    bear_fvg_strength: Optional[float] = None

    qualified_bull_fvg: bool = False
    qualified_bear_fvg: bool = False
    has_bull_fvg: bool = False
    has_bear_fvg: bool = False

    price_inside_bull_memory_fvg: bool = False
    price_inside_bear_memory_fvg: bool = False
    near_bull_memory_fvg: bool = False
    near_bear_memory_fvg: bool = False

    nearest_bull_fvg_distance_atr: Optional[float] = None
    nearest_bear_fvg_distance_atr: Optional[float] = None
    nearest_bull_fvg_strength: Optional[float] = None
    nearest_bear_fvg_strength: Optional[float] = None
    nearest_bull_fvg_max_reaction: Optional[float] = None
    nearest_bear_fvg_max_reaction: Optional[float] = None
    nearest_bull_fvg_created_bar: Optional[int] = None
    nearest_bear_fvg_created_bar: Optional[int] = None
    nearest_bull_fvg_status: Optional[int] = None
    nearest_bear_fvg_status: Optional[int] = None
    nearest_bull_fvg_age: Optional[int] = None
    nearest_bear_fvg_age: Optional[int] = None
    nearest_bull_fvg_reaction_count: Optional[int] = None
    nearest_bear_fvg_reaction_count: Optional[int] = None
    nearest_bull_fvg_last_reaction_type: Optional[int] = None
    nearest_bull_fvg_reaction_score: Optional[float] = None
    nearest_bear_fvg_last_reaction_type: Optional[int] = None
    nearest_bear_fvg_reaction_score: Optional[float] = None

    recent_bull_fvg_failure: bool = False
    recent_bear_fvg_failure: bool = False
    fvg_failure_strength: Optional[float] = None
    fvg_failure_age: Optional[int] = None

    # Order Blocks – Normal
    bull_ob_high: Optional[float] = None
    bull_ob_low: Optional[float] = None
    bear_ob_high: Optional[float] = None
    bear_ob_low: Optional[float] = None
    bull_ob_event: bool = False
    bear_ob_event: bool = False
    bull_ob_mitigated: bool = False
    bear_ob_mitigated: bool = False
    bull_ob_invalidated: bool = False
    bear_ob_invalidated: bool = False
    bull_ob_strength: Optional[float] = None
    bear_ob_strength: Optional[float] = None
    bull_ob_age: Optional[int] = None
    bear_ob_age: Optional[int] = None
    bull_ob_distance: Optional[float] = None
    bull_ob_distance_atr: Optional[float] = None
    bear_ob_distance: Optional[float] = None
    bear_ob_distance_atr: Optional[float] = None
    active_bull_ob_has_fvg: bool = False
    active_bear_ob_has_fvg: bool = False

    # Order Blocks – Strict
    strict_bull_ob_high: Optional[float] = None
    strict_bull_ob_low: Optional[float] = None
    strict_bear_ob_high: Optional[float] = None
    strict_bear_ob_low: Optional[float] = None
    strict_bull_ob_event: bool = False
    strict_bear_ob_event: bool = False
    strict_bull_ob_mitigated: bool = False
    strict_bear_ob_mitigated: bool = False
    strict_bull_ob_invalidated: bool = False
    strict_bear_ob_invalidated: bool = False
    strict_bull_ob_age: Optional[int] = None
    strict_bear_ob_age: Optional[int] = None
    active_strict_bull_ob_has_fvg: bool = False
    active_strict_bear_ob_has_fvg: bool = False

    # Breakers – Normal
    bull_breaker_high: Optional[float] = None
    bull_breaker_low: Optional[float] = None
    bear_breaker_high: Optional[float] = None
    bear_breaker_low: Optional[float] = None
    bull_breaker_active: bool = False
    bear_breaker_active: bool = False
    bull_breaker_age: Optional[int] = None
    bear_breaker_age: Optional[int] = None

    # Breakers – Strict
    strict_bull_breaker_high: Optional[float] = None
    strict_bull_breaker_low: Optional[float] = None
    strict_bear_breaker_high: Optional[float] = None
    strict_bear_breaker_low: Optional[float] = None
    strict_bull_breaker_active: bool = False
    strict_bear_breaker_active: bool = False
    strict_bull_breaker_age: Optional[int] = None
    strict_bear_breaker_age: Optional[int] = None

# ------------------------------------------------------
# Main update function
# ------------------------------------------------------

def update_market_imbalance(
    symbol: str,
    tf: str,
    bar_index: int,
    c: float,
    h: float,
    l: float,
    o: float,
    c1: Optional[float],
    h1: Optional[float],
    l1: Optional[float],
    o1: Optional[float],
    atr: Optional[float],
    # FVG settings
    fvg_min_atr_mult: float = 1.0,
    fvg_strong_atr_mult: float = 1.5,
    fvg_zone_distance_atr: float = 2.0,
    # OB settings
    is_confirmed: bool = True
) -> MarketImbalance:

    memory = get_imbalance_memory(symbol, tf)
    result = MarketImbalance()

    if atr is None or atr <= 0 or c1 is None or h1 is None or l1 is None or o1 is None:
        return result

    # ==================================================
    # 1. FAIR VALUE GAP (FVG)
    # ==================================================

    # Bullish FVG: current low > previous high (gap up)
    bull_fvg_condition = l > h1 and (l - h1) >= atr * fvg_min_atr_mult
    # Bearish FVG: current high < previous low (gap down)
    bear_fvg_condition = h < l1 and (l1 - h) >= atr * fvg_min_atr_mult

    if is_confirmed and bull_fvg_condition:
        gap_size = l - h1
        strength = gap_size / atr
        zone = FVGZone(
            low=h1,
            high=l,
            created_bar=bar_index,
            strength=strength
        )
        memory.fvg.bull_fvgs.append(zone)
        result.bull_fvg = True
        result.bull_fvg_low = h1
        result.bull_fvg_high = l
        result.bull_gap_atr = strength
        result.bull_fvg_strength = strength
        result.qualified_bull_fvg = strength >= fvg_strong_atr_mult

    if is_confirmed and bear_fvg_condition:
        gap_size = l1 - h
        strength = gap_size / atr
        zone = FVGZone(
            low=h,
            high=l1,
            created_bar=bar_index,
            strength=strength
        )
        memory.fvg.bear_fvgs.append(zone)
        result.bear_fvg = True
        result.bear_fvg_low = h
        result.bear_fvg_high = l1
        result.bear_gap_atr = strength
        result.bear_fvg_strength = strength
        result.qualified_bear_fvg = strength >= fvg_strong_atr_mult

    # Update existing Bull FVGs
    for fvg in memory.fvg.bull_fvgs:
        fvg.age = bar_index - fvg.created_bar
        if fvg.status == 1:
            # Mitigation / touch
            if l <= fvg.high and h >= fvg.low:
                fvg.has_been_touched = True
                reaction = (c - fvg.high) / atr if c > fvg.high else 0.0
                fvg.reaction_count += 1
                fvg.max_reaction = max(fvg.max_reaction, reaction)
                fvg.reaction_score += reaction
                if c < fvg.low:  # full failure
                    fvg.status = 0
                    result.recent_bull_fvg_failure = True
                    result.fvg_failure_strength = fvg.strength
                    result.fvg_failure_age = fvg.age

    # Update existing Bear FVGs
    for fvg in memory.fvg.bear_fvgs:
        fvg.age = bar_index - fvg.created_bar
        if fvg.status == 1:
            if h >= fvg.low and l <= fvg.high:
                fvg.has_been_touched = True
                reaction = (fvg.low - c) / atr if c < fvg.low else 0.0
                fvg.reaction_count += 1
                fvg.max_reaction = max(fvg.max_reaction, reaction)
                fvg.reaction_score += reaction
                if c > fvg.high:
                    fvg.status = 0
                    result.recent_bear_fvg_failure = True
                    result.fvg_failure_strength = fvg.strength
                    result.fvg_failure_age = fvg.age

    # Nearest active Bull FVG
    for fvg in memory.fvg.bull_fvgs:
        if fvg.status != 1:
            continue
        dist = 0.0
        if c > fvg.high:
            dist = (c - fvg.high) / atr
        elif c < fvg.low:
            dist = (fvg.low - c) / atr
        if result.nearest_bull_fvg_distance_atr is None or dist < result.nearest_bull_fvg_distance_atr:
            result.nearest_bull_fvg_distance_atr = dist
            result.nearest_bull_fvg_low = fvg.low
            result.nearest_bull_fvg_high = fvg.high
            result.nearest_bull_fvg_strength = fvg.strength
            result.nearest_bull_fvg_max_reaction = fvg.max_reaction
            result.nearest_bull_fvg_created_bar = fvg.created_bar
            result.nearest_bull_fvg_status = fvg.status
            result.nearest_bull_fvg_age = fvg.age
            result.nearest_bull_fvg_reaction_count = fvg.reaction_count
            result.nearest_bull_fvg_reaction_score = fvg.reaction_score
            result.price_inside_bull_memory_fvg = fvg.low <= c <= fvg.high
            result.near_bull_memory_fvg = dist <= fvg_zone_distance_atr
            result.has_bull_fvg = True

    # Nearest active Bear FVG
    for fvg in memory.fvg.bear_fvgs:
        if fvg.status != 1:
            continue
        dist = 0.0
        if c < fvg.low:
            dist = (fvg.low - c) / atr
        elif c > fvg.high:
            dist = (c - fvg.high) / atr
        if result.nearest_bear_fvg_distance_atr is None or dist < result.nearest_bear_fvg_distance_atr:
            result.nearest_bear_fvg_distance_atr = dist
            result.nearest_bear_fvg_low = fvg.low
            result.nearest_bear_fvg_high = fvg.high
            result.nearest_bear_fvg_strength = fvg.strength
            result.nearest_bear_fvg_max_reaction = fvg.max_reaction
            result.nearest_bear_fvg_created_bar = fvg.created_bar
            result.nearest_bear_fvg_status = fvg.status
            result.nearest_bear_fvg_age = fvg.age
            result.nearest_bear_fvg_reaction_count = fvg.reaction_count
            result.nearest_bear_fvg_reaction_score = fvg.reaction_score
            result.price_inside_bear_memory_fvg = fvg.low <= c <= fvg.high
            result.near_bear_memory_fvg = dist <= fvg_zone_distance_atr
            result.has_bear_fvg = True

    # ==================================================
    # 2. ORDER BLOCKS (Normal + Strict)
    # ==================================================

    # Simple displacement detection for OB creation
    body = abs(c - o)
    prev_body = abs(c1 - o1) if c1 is not None and o1 is not None else 0.0
    bullish_displacement = c > o and body > prev_body and body >= atr * 0.5
    bearish_displacement = c < o and body > prev_body and body >= atr * 0.5

    # Normal Bullish OB (last down candle before strong up move)
    if is_confirmed and bullish_displacement and c1 < o1:
        memory.ob.active_bull_ob = OrderBlock(
            high=h1,
            low=l1,
            created_bar=bar_index - 1,
            atr_at_creation=atr,
            has_fvg=result.bull_fvg
        )
        result.bull_ob_event = True

    # Normal Bearish OB
    if is_confirmed and bearish_displacement and c1 > o1:
        memory.ob.active_bear_ob = OrderBlock(
            high=h1,
            low=l1,
            created_bar=bar_index - 1,
            atr_at_creation=atr,
            has_fvg=result.bear_fvg
        )
        result.bear_ob_event = True

    # Strict Bullish OB (stronger requirements)
    if is_confirmed and bullish_displacement and c1 < o1 and body >= atr * 0.8:
        memory.ob.active_strict_bull_ob = OrderBlock(
            high=h1,
            low=l1,
            created_bar=bar_index - 1,
            atr_at_creation=atr,
            has_fvg=result.bull_fvg
        )
        result.strict_bull_ob_event = True

    # Strict Bearish OB
    if is_confirmed and bearish_displacement and c1 > o1 and body >= atr * 0.8:
        memory.ob.active_strict_bear_ob = OrderBlock(
            high=h1,
            low=l1,
            created_bar=bar_index - 1,
            atr_at_creation=atr,
            has_fvg=result.bear_fvg
        )
        result.strict_bear_ob_event = True

    # --- Lifecycle: Normal Bull OB ---
    if memory.ob.active_bull_ob is not None:
        ob = memory.ob.active_bull_ob
        ob.age = bar_index - ob.created_bar
        result.bull_ob_high = ob.high
        result.bull_ob_low = ob.low
        result.bull_ob_age = ob.age
        result.active_bull_ob_has_fvg = ob.has_fvg
        result.bull_ob_strength = ob.strength

        # Mitigation
        if l <= ob.high and h >= ob.low:
            ob.mitigated = True
            ob.has_been_mitigated = True
            result.bull_ob_mitigated = True

        # Invalidation
        if c < ob.low:
            ob.invalidated = True
            result.bull_ob_invalidated = True
            # Create Bull Breaker
            memory.ob.active_bull_breaker = Breaker(
                high=ob.high, low=ob.low, created_bar=bar_index
            )
            memory.ob.active_bull_ob = None

        # Distance
        if ob.atr_at_creation > 0:
            if c > ob.high:
                dist = c - ob.high
            elif c < ob.low:
                dist = ob.low - c
            else:
                dist = 0.0
            result.bull_ob_distance = dist
            result.bull_ob_distance_atr = dist / ob.atr_at_creation

    # --- Lifecycle: Normal Bear OB ---
    if memory.ob.active_bear_ob is not None:
        ob = memory.ob.active_bear_ob
        ob.age = bar_index - ob.created_bar
        result.bear_ob_high = ob.high
        result.bear_ob_low = ob.low
        result.bear_ob_age = ob.age
        result.active_bear_ob_has_fvg = ob.has_fvg
        result.bear_ob_strength = ob.strength

        if h >= ob.low and l <= ob.high:
            ob.mitigated = True
            ob.has_been_mitigated = True
            result.bear_ob_mitigated = True

        if c > ob.high:
            ob.invalidated = True
            result.bear_ob_invalidated = True
            memory.ob.active_bear_breaker = Breaker(
                high=ob.high, low=ob.low, created_bar=bar_index
            )
            memory.ob.active_bear_ob = None

        if ob.atr_at_creation > 0:
            if c > ob.high:
                dist = c - ob.high
            elif c < ob.low:
                dist = ob.low - c
            else:
                dist = 0.0
            result.bear_ob_distance = dist
            result.bear_ob_distance_atr = dist / ob.atr_at_creation

    # --- Lifecycle: Strict Bull OB ---
    if memory.ob.active_strict_bull_ob is not None:
        ob = memory.ob.active_strict_bull_ob
        ob.age = bar_index - ob.created_bar
        result.strict_bull_ob_high = ob.high
        result.strict_bull_ob_low = ob.low
        result.strict_bull_ob_age = ob.age
        result.active_strict_bull_ob_has_fvg = ob.has_fvg

        if l <= ob.high and h >= ob.low:
            ob.mitigated = True
            result.strict_bull_ob_mitigated = True

        if c < ob.low:
            ob.invalidated = True
            result.strict_bull_ob_invalidated = True
            memory.ob.active_strict_bull_breaker = Breaker(
                high=ob.high, low=ob.low, created_bar=bar_index
            )
            memory.ob.active_strict_bull_ob = None

    # --- Lifecycle: Strict Bear OB ---
    if memory.ob.active_strict_bear_ob is not None:
        ob = memory.ob.active_strict_bear_ob
        ob.age = bar_index - ob.created_bar
        result.strict_bear_ob_high = ob.high
        result.strict_bear_ob_low = ob.low
        result.strict_bear_ob_age = ob.age
        result.active_strict_bear_ob_has_fvg = ob.has_fvg

        if h >= ob.low and l <= ob.high:
            ob.mitigated = True
            result.strict_bear_ob_mitigated = True

        if c > ob.high:
            ob.invalidated = True
            result.strict_bear_ob_invalidated = True
            memory.ob.active_strict_bear_breaker = Breaker(
                high=ob.high, low=ob.low, created_bar=bar_index
            )
            memory.ob.active_strict_bear_ob = None

    # ==================================================
    # 3. BREAKERS
    # ==================================================

    # Normal Bull Breaker
    if memory.ob.active_bull_breaker is not None:
        br = memory.ob.active_bull_breaker
        br.age = bar_index - br.created_bar
        result.bull_breaker_active = br.active
        result.bull_breaker_high = br.high
        result.bull_breaker_low = br.low
        result.bull_breaker_age = br.age
        if c < br.low:
            br.active = False
            memory.ob.active_bull_breaker = None

    # Normal Bear Breaker
    if memory.ob.active_bear_breaker is not None:
        br = memory.ob.active_bear_breaker
        br.age = bar_index - br.created_bar
        result.bear_breaker_active = br.active
        result.bear_breaker_high = br.high
        result.bear_breaker_low = br.low
        result.bear_breaker_age = br.age
        if c > br.high:
            br.active = False
            memory.ob.active_bear_breaker = None

    # Strict Bull Breaker
    if memory.ob.active_strict_bull_breaker is not None:
        br = memory.ob.active_strict_bull_breaker
        br.age = bar_index - br.created_bar
        result.strict_bull_breaker_active = br.active
        result.strict_bull_breaker_high = br.high
        result.strict_bull_breaker_low = br.low
        result.strict_bull_breaker_age = br.age
        if c < br.low:
            br.active = False
            memory.ob.active_strict_bull_breaker = None

    # Strict Bear Breaker
    if memory.ob.active_strict_bear_breaker is not None:
        br = memory.ob.active_strict_bear_breaker
        br.age = bar_index - br.created_bar
        result.strict_bear_breaker_active = br.active
        result.strict_bear_breaker_high = br.high
        result.strict_bear_breaker_low = br.low
        result.strict_bear_breaker_age = br.age
        if c > br.high:
            br.active = False
            memory.ob.active_strict_bear_breaker = None

    return result