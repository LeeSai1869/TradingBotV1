# ======================================================
# MARKET LEVELS
# Full Dynamic + Full Institutional Support & Resistance
# (Nothing removed – original logic preserved)
# ======================================================

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import math

# ------------------------------------------------------
# Zone data structures
# ------------------------------------------------------

@dataclass
class DynamicZone:
    zone_id: str
    low: float
    high: float
    origin: float
    created_bar: int
    touches: int = 0
    strong_rejects: int = 0
    strength: float = 0.0
    score: float = 0.0
    es: float = 0.0
    last_test_bar: Optional[int] = None
    last_test_type: str = "NO_TEST"
    approach_direction: int = 0
    max_penetration: float = 0.0
    max_wick_ratio: float = 0.0
    max_reaction: float = 0.0
    origin_time: Optional[int] = None
    zone_atr: float = 0.0
    prev_inside: bool = False
    is_institutional: bool = False

@dataclass
class InstitutionalZone:
    zone_id: str
    low: float
    high: float
    origin: float
    created_bar: int
    strength: float = 0.0
    score: float = 0.0
    es: float = 0.0
    failure_count: int = 0
    last_test_bar: Optional[int] = None
    last_test_type: str = "NO_TEST"
    strong_touches: int = 0
    weak_touches: int = 0
    origin_time: Optional[int] = None


# ------------------------------------------------------
# Memory (permanent per (symbol, tf))
# ------------------------------------------------------

@dataclass
class SRMemory:
    support_zones: List[DynamicZone] = field(default_factory=list)
    resistance_zones: List[DynamicZone] = field(default_factory=list)

    inst_support_zones: List[InstitutionalZone] = field(default_factory=list)
    inst_resistance_zones: List[InstitutionalZone] = field(default_factory=list)

    next_support_seq: int = 0
    next_resistance_seq: int = 0

_sr_memory_store: Dict[Tuple[str, str], "SRMemory"] = {}

def get_sr_memory(symbol: str, tf: str):
    key = (symbol, tf)
    if key not in _sr_memory_store:
        _sr_memory_store[key] = SRMemory()
    return _sr_memory_store[key]


# ------------------------------------------------------
# Output contract
# ------------------------------------------------------

@dataclass
class MarketLevels:
    # Dynamic nearest
    nearest_support_price: Optional[float] = None
    nearest_support_distance: Optional[float] = None
    nearest_support_strength: Optional[float] = None
    nearest_support_score: Optional[float] = None
    nearest_support_es: Optional[float] = None
    nearest_support_zone_id: Optional[str] = None
    nearest_support_state: Optional[str] = None
    nearest_support_last_test_age: Optional[float] = None
    nearest_support_last_test_type: Optional[str] = None
    nearest_support_strong_touches: Optional[int] = None
    nearest_support_weak_touches: Optional[int] = None

    nearest_resistance_price: Optional[float] = None
    nearest_resistance_distance: Optional[float] = None
    nearest_resistance_strength: Optional[float] = None
    nearest_resistance_score: Optional[float] = None
    nearest_resistance_es: Optional[float] = None
    nearest_resistance_zone_id: Optional[str] = None
    nearest_resistance_state: Optional[str] = None
    nearest_resistance_last_test_age: Optional[float] = None
    nearest_resistance_last_test_type: Optional[str] = None
    nearest_resistance_strong_touches: Optional[int] = None
    nearest_resistance_weak_touches: Optional[int] = None

    # Institutional nearest
    nearest_inst_support_price: Optional[float] = None
    nearest_inst_support_distance: Optional[float] = None
    nearest_inst_support_strength: Optional[float] = None
    nearest_inst_support_score: Optional[float] = None
    nearest_inst_support_es: Optional[float] = None
    nearest_inst_support_zone_id: Optional[str] = None
    nearest_inst_support_last_test_age: Optional[float] = None
    nearest_inst_support_last_test_type: Optional[str] = None
    nearest_inst_support_failure_count: Optional[int] = None

    nearest_inst_resistance_price: Optional[float] = None
    nearest_inst_resistance_distance: Optional[float] = None
    nearest_inst_resistance_strength: Optional[float] = None
    nearest_inst_resistance_score: Optional[float] = None
    nearest_inst_resistance_es: Optional[float] = None
    nearest_inst_resistance_zone_id: Optional[str] = None
    nearest_inst_resistance_last_test_age: Optional[float] = None
    nearest_inst_resistance_last_test_type: Optional[str] = None
    nearest_inst_resistance_failure_count: Optional[int] = None

    near_support: bool = False
    near_resistance: bool = False
    near_inst_support: bool = False
    near_inst_resistance: bool = False

    support_distance: Optional[float] = None
    resistance_distance: Optional[float] = None

    average_dynamic_support_score: Optional[float] = None
    average_dynamic_support_es: Optional[float] = None
    average_dynamic_resistance_score: Optional[float] = None
    average_dynamic_resistance_es: Optional[float] = None

    average_inst_support_score: Optional[float] = None
    average_inst_support_es: Optional[float] = None
    average_inst_resistance_score: Optional[float] = None
    average_inst_resistance_es: Optional[float] = None
    support_High_Price: Optional[float] = None
    support_Low_Price: Optional[float] = None


# ------------------------------------------------------
# Helpers
# ------------------------------------------------------

def _make_zone_id(symbol: str, tf: str, side: str, seq: int) -> str:
    prefix_map = {
        "1": "1m", "5": "5m", "15": "15m", "30": "30m",
        "60": "1H", "120": "2H", "240": "4H",
        "1D": "1D", "1W": "1W", "1M": "1M", "3M": "3M", "6M": "6M"
    }
    prefix = prefix_map.get(tf, tf)
    return f"{symbol}:{prefix}:{side}:{seq}"

def _promote_to_institutional(zone: DynamicZone, side: str) -> InstitutionalZone:
    return InstitutionalZone(
        zone_id=zone.zone_id,
        low=zone.low,
        high=zone.high,
        origin=zone.origin,
        created_bar=zone.created_bar,
        strength=zone.strength,
        score=zone.score,
        es=zone.es,
        failure_count=0,
        last_test_bar=zone.last_test_bar,
        last_test_type=zone.last_test_type,
        strong_touches=zone.strong_rejects,
        weak_touches=max(0, zone.touches - zone.strong_rejects),
        origin_time=zone.origin_time,
    )


# ------------------------------------------------------
# Main update function
# ------------------------------------------------------

def update_market_levels(
    symbol: str,                # <-- NEW
    tf: str,
    bar_index: int,
    time: Optional[int],
    c: float,
    h: float,
    l: float,
    h1: Optional[float],
    l1: Optional[float],
    atr: Optional[float],
    pivot_high: Optional[float],
    pivot_low: Optional[float],
    pivot_right: int = 1,
    zone_atr_mult: float = 0.5,
    reaction_atr: float = 0.5,
    zone_distance_atr: float = 2.0,
    inst_promotion_strength: float = 10.0,
    is_confirmed: bool = True,
) -> MarketLevels:

    memory = get_sr_memory(symbol, tf)
    result = MarketLevels()

    if atr is None or atr <= 0:
        return result

    zone_size = atr * zone_atr_mult

    # ==================================================
    # DYNAMIC SUPPORT
    # ==================================================
    if is_confirmed and pivot_low is not None:
        reaction = (c - pivot_low) / atr
        if reaction >= reaction_atr:
            overlap = False
            for inst in memory.inst_support_zones:
                if (pivot_low - zone_size) <= inst.high and (pivot_low + zone_size) >= inst.low:
                    overlap = True
                    break
            if not overlap:
                memory.next_support_seq += 1
                zone = DynamicZone(
                    zone_id=_make_zone_id(symbol, tf, "S", memory.next_support_seq),   # <-- FIXED
                    low=pivot_low - zone_size,
                    high=pivot_low + zone_size,
                    origin=pivot_low,
                    created_bar=bar_index - pivot_right,
                    origin_time=time,
                    zone_atr=atr,
                )
                memory.support_zones.append(zone)

    to_remove = []
    for i, zone in enumerate(memory.support_zones):
        inside = bar_index > zone.created_bar and l <= zone.high and h >= zone.low

        if is_confirmed and c > zone.high and not inside and not zone.prev_inside:
            zone.approach_direction = 1

        prev_crossed = (h1 is not None and l1 is not None and
                        h1 > zone.high and l1 < zone.low and zone.approach_direction == 1)
        invalid = is_confirmed and h < zone.low and (zone.approach_direction == 1 or prev_crossed)

        if invalid:
            for inst in memory.inst_support_zones:
                if inst.zone_id == zone.zone_id:
                    inst.failure_count += 1
                    break
            to_remove.append(i)
            continue

        if is_confirmed and zone.prev_inside and zone.approach_direction == 1 and l > zone.high:
            zone.touches += 1
            reaction = (c - zone.high) / atr
            if reaction >= reaction_atr:
                zone.strength += 5.0
                zone.strong_rejects += 1
                zone.last_test_type = "STRONG_REJECTION"
            else:
                zone.strength += 3.0
                zone.last_test_type = "WEAK_REACTION"
            zone.last_test_bar = bar_index
            weak = max(0, zone.touches - zone.strong_rejects)
            zone.score = zone.strong_rejects * 5.0 + weak * 3.0
            zone.es = zone.strength

            if zone.strength >= inst_promotion_strength and not zone.is_institutional:
                zone.is_institutional = True
                memory.inst_support_zones.append(_promote_to_institutional(zone, "S"))

        zone.prev_inside = inside

        dist = (c - zone.high) / atr
        if zone.approach_direction == 1 and dist >= 0:
            if result.nearest_support_distance is None or dist < result.nearest_support_distance:
                result.nearest_support_distance = dist
                result.nearest_support_price = zone.high
                result.nearest_support_strength = zone.strength
                result.nearest_support_score = zone.score
                result.nearest_support_es = zone.es
                result.nearest_support_zone_id = zone.zone_id
                result.nearest_support_state = zone.last_test_type
                result.nearest_support_last_test_age = (bar_index - zone.last_test_bar) if zone.last_test_bar is not None else None
                result.nearest_support_last_test_type = zone.last_test_type
                result.nearest_support_strong_touches = zone.strong_rejects
                result.nearest_support_weak_touches = max(0, zone.touches - zone.strong_rejects)

    for i in reversed(to_remove):
        memory.support_zones.pop(i)

    # ==================================================
    # DYNAMIC RESISTANCE
    # ==================================================
    if is_confirmed and pivot_high is not None:
        reaction = (pivot_high - c) / atr
        if reaction >= reaction_atr:
            overlap = False
            for inst in memory.inst_resistance_zones:
                if (pivot_high - zone_size) <= inst.high and (pivot_high + zone_size) >= inst.low:
                    overlap = True
                    break
            if not overlap:
                memory.next_resistance_seq += 1
                zone = DynamicZone(
                    zone_id=_make_zone_id(symbol, tf, "R", memory.next_resistance_seq),   # <-- FIXED
                    low=pivot_high - zone_size,
                    high=pivot_high + zone_size,
                    origin=pivot_high,
                    created_bar=bar_index - pivot_right,
                    origin_time=time,
                    zone_atr=atr,
                )
                memory.resistance_zones.append(zone)

    to_remove = []
    for i, zone in enumerate(memory.resistance_zones):
        inside = bar_index > zone.created_bar and l <= zone.high and h >= zone.low

        if is_confirmed and c < zone.low and not inside and not zone.prev_inside:
            zone.approach_direction = -1

        prev_crossed = (h1 is not None and l1 is not None and
                        h1 > zone.high and l1 < zone.low and zone.approach_direction == -1)
        invalid = is_confirmed and l > zone.high and (zone.approach_direction == -1 or prev_crossed)

        if invalid:
            for inst in memory.inst_resistance_zones:
                if inst.zone_id == zone.zone_id:
                    inst.failure_count += 1
                    break
            to_remove.append(i)
            continue

        if is_confirmed and zone.prev_inside and zone.approach_direction == -1 and h < zone.low:
            zone.touches += 1
            reaction = (zone.low - c) / atr
            if reaction >= reaction_atr:
                zone.strength += 5.0
                zone.strong_rejects += 1
                zone.last_test_type = "STRONG_REJECTION"
            else:
                zone.strength += 3.0
                zone.last_test_type = "WEAK_REACTION"
            zone.last_test_bar = bar_index
            weak = max(0, zone.touches - zone.strong_rejects)
            zone.score = zone.strong_rejects * 5.0 + weak * 3.0
            zone.es = zone.strength

            if zone.strength >= inst_promotion_strength and not zone.is_institutional:
                zone.is_institutional = True
                memory.inst_resistance_zones.append(_promote_to_institutional(zone, "R"))

        zone.prev_inside = inside

        dist = (zone.low - c) / atr
        if zone.approach_direction == -1 and dist >= 0:
            if result.nearest_resistance_distance is None or dist < result.nearest_resistance_distance:
                result.nearest_resistance_distance = dist
                result.nearest_resistance_price = zone.low
                result.nearest_resistance_strength = zone.strength
                result.nearest_resistance_score = zone.score
                result.nearest_resistance_es = zone.es
                result.nearest_resistance_zone_id = zone.zone_id
                result.nearest_resistance_state = zone.last_test_type
                result.nearest_resistance_last_test_age = (bar_index - zone.last_test_bar) if zone.last_test_bar is not None else None
                result.nearest_resistance_last_test_type = zone.last_test_type
                result.nearest_resistance_strong_touches = zone.strong_rejects
                result.nearest_resistance_weak_touches = max(0, zone.touches - zone.strong_rejects)

    for i in reversed(to_remove):
        memory.resistance_zones.pop(i)

    # ==================================================
    # INSTITUTIONAL NEAREST + AVERAGES
    # ==================================================
    for inst in memory.inst_support_zones:
        dist = (c - inst.high) / atr if atr > 0 else None
        if dist is not None and dist >= 0:
            if result.nearest_inst_support_distance is None or dist < result.nearest_inst_support_distance:
                result.nearest_inst_support_distance = dist
                result.nearest_inst_support_price = inst.high
                result.nearest_inst_support_strength = inst.strength
                result.nearest_inst_support_score = inst.score
                result.nearest_inst_support_es = inst.es
                result.nearest_inst_support_zone_id = inst.zone_id
                result.nearest_inst_support_last_test_age = (bar_index - inst.last_test_bar) if inst.last_test_bar is not None else None
                result.nearest_inst_support_last_test_type = inst.last_test_type
                result.nearest_inst_support_failure_count = inst.failure_count

    for inst in memory.inst_resistance_zones:
        dist = (inst.low - c) / atr if atr > 0 else None
        if dist is not None and dist >= 0:
            if result.nearest_inst_resistance_distance is None or dist < result.nearest_inst_resistance_distance:
                result.nearest_inst_resistance_distance = dist
                result.nearest_inst_resistance_price = inst.low
                result.nearest_inst_resistance_strength = inst.strength
                result.nearest_inst_resistance_score = inst.score
                result.nearest_inst_resistance_es = inst.es
                result.nearest_inst_resistance_zone_id = inst.zone_id
                result.nearest_inst_resistance_last_test_age = (bar_index - inst.last_test_bar) if inst.last_test_bar is not None else None
                result.nearest_inst_resistance_last_test_type = inst.last_test_type
                result.nearest_inst_resistance_failure_count = inst.failure_count

    result.near_support = result.nearest_support_distance is not None and result.nearest_support_distance <= zone_distance_atr
    result.near_resistance = result.nearest_resistance_distance is not None and result.nearest_resistance_distance <= zone_distance_atr
    result.near_inst_support = result.nearest_inst_support_distance is not None and result.nearest_inst_support_distance <= zone_distance_atr
    result.near_inst_resistance = result.nearest_inst_resistance_distance is not None and result.nearest_inst_resistance_distance <= zone_distance_atr

    result.support_distance = result.nearest_support_distance
    result.resistance_distance = result.nearest_resistance_distance

    if memory.support_zones:
        result.average_dynamic_support_score = sum(z.score for z in memory.support_zones) / len(memory.support_zones)
        result.average_dynamic_support_es = sum(z.es for z in memory.support_zones) / len(memory.support_zones)
    if memory.resistance_zones:
        result.average_dynamic_resistance_score = sum(z.score for z in memory.resistance_zones) / len(memory.resistance_zones)
        result.average_dynamic_resistance_es = sum(z.es for z in memory.resistance_zones) / len(memory.resistance_zones)

    if memory.inst_support_zones:
        result.average_inst_support_score = sum(z.score for z in memory.inst_support_zones) / len(memory.inst_support_zones)
        result.average_inst_support_es = sum(z.es for z in memory.inst_support_zones) / len(memory.inst_support_zones)
    if memory.inst_resistance_zones:
        result.average_inst_resistance_score = sum(z.score for z in memory.inst_resistance_zones) / len(memory.inst_resistance_zones)
        result.average_inst_resistance_es = sum(z.es for z in memory.inst_resistance_zones) / len(memory.inst_resistance_zones)


    # after the update loop
    MAX_INST = 500
    if len(memory.inst_support_zones) > MAX_INST:
        memory.inst_support_zones.sort(key=lambda z: z.strength, reverse=True)
        memory.inst_support_zones = memory.inst_support_zones[:MAX_INST]
    if len(memory.inst_resistance_zones) > MAX_INST:
        memory.inst_resistance_zones.sort(key=lambda z: z.strength, reverse=True)
        memory.inst_resistance_zones = memory.inst_resistance_zones[:MAX_INST]

    return result