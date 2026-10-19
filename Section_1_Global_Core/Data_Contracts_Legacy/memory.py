# ============================================================
# 04_memory.py
# Persistent market lifecycle memory
# ============================================================

from dataclasses import dataclass, field


# ------------------------------------------------------------
# FVG memory
# ------------------------------------------------------------

@dataclass
class FVGMemory:

    bull_low: list = field(default_factory=list)
    bull_high: list = field(default_factory=list)
    bear_low: list = field(default_factory=list)
    bear_high: list = field(default_factory=list)

    bull_strength: list = field(default_factory=list)
    bear_strength: list = field(default_factory=list)

    bull_reaction: list = field(default_factory=list)
    bear_reaction: list = field(default_factory=list)

    bull_status: list = field(default_factory=list)
    bear_status: list = field(default_factory=list)

    bull_age: list = field(default_factory=list)
    bear_age: list = field(default_factory=list)

    bull_created_bar: list = field(default_factory=list)
    bear_created_bar: list = field(default_factory=list)

    bull_reaction_count: list = field(default_factory=list)
    bear_reaction_count: list = field(default_factory=list)

    bull_last_reaction_bar: list = field(default_factory=list)
    bear_last_reaction_bar: list = field(default_factory=list)

    bull_reaction_active: list = field(default_factory=list)
    bear_reaction_active: list = field(default_factory=list)

    bull_last_reaction_type: list = field(default_factory=list)
    bear_last_reaction_type: list = field(default_factory=list)

    bull_reaction_score: list = field(default_factory=list)
    bear_reaction_score: list = field(default_factory=list)


# ------------------------------------------------------------
# Support / resistance memory
# ------------------------------------------------------------

@dataclass
class SRMemory:

    support_low: list = field(default_factory=list)
    support_high: list = field(default_factory=list)
    support_origin: list = field(default_factory=list)
    support_bar: list = field(default_factory=list)
    support_touch: list = field(default_factory=list)
    support_zone_atr: list = field(default_factory=list)

    prev_candle_inside_support_zone: list = field(default_factory=list)
    support_last_test_bar: list = field(default_factory=list)
    support_last_test_type: list = field(default_factory=list)
    support_strength: list = field(default_factory=list)
    support_strong_reject: list = field(default_factory=list)
    support_max_penetration: list = field(default_factory=list)
    support_max_wick_ratio: list = field(default_factory=list)
    support_max_reaction: list = field(default_factory=list)
    support_approach_direction: list = field(default_factory=list)
    support_origin_time: list = field(default_factory=list)
    support_score: list = field(default_factory=list)
    support_es: list = field(default_factory=list)

    resistance_low: list = field(default_factory=list)
    resistance_high: list = field(default_factory=list)
    resistance_origin: list = field(default_factory=list)
    resistance_bar: list = field(default_factory=list)
    resistance_touch: list = field(default_factory=list)
    resistance_zone_atr: list = field(default_factory=list)

    prev_candle_inside_resistance_zone: list = field(default_factory=list)
    resistance_last_test_bar: list = field(default_factory=list)
    resistance_last_test_type: list = field(default_factory=list)
    resistance_strength: list = field(default_factory=list)
    resistance_strong_reject: list = field(default_factory=list)
    resistance_max_penetration: list = field(default_factory=list)
    resistance_max_wick_ratio: list = field(default_factory=list)
    resistance_max_reaction: list = field(default_factory=list)
    resistance_approach_direction: list = field(default_factory=list)
    resistance_origin_time: list = field(default_factory=list)
    resistance_score: list = field(default_factory=list)
    resistance_es: list = field(default_factory=list)


# ------------------------------------------------------------
# Institutional S/R memory
# ------------------------------------------------------------

@dataclass
class InstitutionalSRMemory:

    support_zone_id: list = field(default_factory=list)
    support_score: list = field(default_factory=list)
    support_strength: list = field(default_factory=list)
    qualified_support_tf_list: list = field(default_factory=list)
    support_failure_count: list = field(default_factory=list)
    support_break_bar: list = field(default_factory=list)

    resistance_zone_id: list = field(default_factory=list)
    resistance_score: list = field(default_factory=list)
    resistance_strength: list = field(default_factory=list)
    qualified_resistance_tf_list: list = field(default_factory=list)
    resistance_failure_count: list = field(default_factory=list)
    resistance_break_bar: list = field(default_factory=list)


# ------------------------------------------------------------
# Swing memory
# ------------------------------------------------------------

@dataclass
class SwingMemory:

    high_price = None
    high_bar = None
    high_time = None

    low_price = None
    low_bar = None
    low_time = None

    current_active_pivot_type = ""
    previous_active_pivot_type = ""


# ------------------------------------------------------------
# Market structure memory
# ------------------------------------------------------------

@dataclass
class MarketStructureMemory:

    pivot_high = None
    pivot_high_bar = None

    pivot_low = None
    pivot_low_bar = None

    high_type = ""
    low_type = ""

    state = ""
    highs_count = 0
    lows_count = 0

    transition = ""
    bos = ""
    choch = ""


# ------------------------------------------------------------
# Execution memory
# ------------------------------------------------------------

@dataclass
class ExecutionMemory:

    execution_tf = ""
    execution_bar = None
    execution_time = None
    execution_type = ""

    execution_type_count = 0

    previous_execution_type = ""
    previous_execution_bar = None


# ------------------------------------------------------------
# ADCN decision execution memory
# ------------------------------------------------------------

@dataclass
class ADCNExecutionMemory:

    execution_version: int = 1

    features_packet_version: int = 1
    decision_packet_version: int = 1
    opportunity_packet_version: int = 1
    confidence_packet_version: int = 1

    flag_id: list = field(default_factory=list)

    symbol: list = field(default_factory=list)
    timeframe: list = field(default_factory=list)

    bar_index: list = field(default_factory=list)
    bar_time: list = field(default_factory=list)

    open_price: list = field(default_factory=list)
    high_price: list = field(default_factory=list)
    low_price: list = field(default_factory=list)
    close_price: list = field(default_factory=list)

    decision: list = field(default_factory=list)
    decision_score: list = field(default_factory=list)

    confidence_percentage: list = field(default_factory=list)

    opportunity_layer1_price: list = field(default_factory=list)
    opportunity_layer2_price: list = field(default_factory=list)
    opportunity_layer3_price: list = field(default_factory=list)

    opportunity_layer1_pct: list = field(default_factory=list)
    opportunity_layer2_pct: list = field(default_factory=list)
    opportunity_layer3_pct: list = field(default_factory=list)

    opportunity_negative_price: list = field(default_factory=list)
    opportunity_negative_pct: list = field(default_factory=list)

# ------------------------------------------------------------
# Global lifecycle memory
# ------------------------------------------------------------

@dataclass
class GlobalLifecycleMemory:

    fvg: FVGMemory = field(default_factory=FVGMemory)
    sr: SRMemory = field(default_factory=SRMemory)
    institutional_sr: InstitutionalSRMemory = field(
        default_factory=InstitutionalSRMemory
    )
    swing: SwingMemory = field(default_factory=SwingMemory)
    market_structure: MarketStructureMemory = field(
        default_factory=MarketStructureMemory
    )
    execution: ExecutionMemory = field(
        default_factory=ExecutionMemory
    )

    adcn_execution: ADCNExecutionMemory = field(
        default_factory=ADCNExecutionMemory
    )