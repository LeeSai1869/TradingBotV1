# ============================================================
# GLOBAL CORE PACKET
# Canonical public gateway for Section 1 Global Core
# ============================================================
#
# Architecture:
#
#   Section 1.1 Constants
#   Section 1.2 Market Definitions
#   Section 1.3 Market State
#   Section 1.4 Memory
#   Section 1.5 Timeframes
#   Section 1.6 Outputs
#   Section 1.7 Global State
#   Section 1.8 Symbols
#            │
#            ▼
#      global_packet.py
#            │
#            ▼
#      Downstream sections
#
# IMPORTANT:
# This file does NOT reimplement Section 1 logic.
# It exposes the canonical implementations owned by
# the individual Section 1 modules.
# ============================================================

from dataclasses import dataclass
from typing import List

# ------------------------------------------------------------
# Section 1.1 — Constants
# ------------------------------------------------------------

from Section_1_Global_Core.Data_Contracts_Legacy.constants import (
    STRONG_BUY_THRESHOLD,
    BUY_THRESHOLD,
    WEAK_BUY_THRESHOLD,
    WEAK_SELL_THRESHOLD,
    SELL_THRESHOLD,
    STRONG_SELL_THRESHOLD,
    SCORE_MAX,
    SCORE_MIN,

    FVG_MULTIPLIER_NORMAL,
    FVG_MULTIPLIER_STRONG,
    FVG_FAILURE_MEMORY_BARS,

    EMA_7,
    EMA_25,
    EMA_50,
    EMA_100,
    EMA_200,
    EMA_300,

    MARKET_CURRENT,
    MARKET_BTC,

    ENGINE_SCALP,
    ENGINE_SWING_SCALP,
    ENGINE_SWING,
    ENGINE_BREAKOUT,

    ENGINE_SCALP_INDEX,
    ENGINE_SWING_SCALP_INDEX,
    ENGINE_SWING_INDEX,
    ENGINE_BREAKOUT_INDEX,

    ENGINE_COUNT,
    engine_index,
)

# Backward-compatible market reference aliases expected by
# downstream modules.
REF_MARKET_CURRENT = MARKET_CURRENT
REF_MARKET_BTC = MARKET_BTC


# ------------------------------------------------------------
# Section 1.2 — Market Definitions
# ------------------------------------------------------------

from Section_1_Global_Core.Data_Contracts_Legacy.market_definitions import (
    STATE_UNKNOWN,

    REGIME_BULL_EXPANSION,
    REGIME_BEAR_EXPANSION,
    REGIME_BULL_TREND,
    REGIME_BEAR_TREND,
    REGIME_COMPRESSION,
    REGIME_RANGE,

    ENERGY_EXPANDING,
    ENERGY_NORMAL,
    ENERGY_CONTRACTING,
    ENERGY_DEAD,

    FATIGUE_NONE,
    FATIGUE_BULLISH,
    FATIGUE_BEARISH,

    TREND_FRESH,
    TREND_MATURE,
    TREND_WEAK,
    TREND_NONE,

    TRANSITION_NONE,
    TRANSITION_RISK,
    TRANSITION_ACTIVE,

    CONTROL_BULL,
    CONTROL_BEAR,
    CONTROL_BALANCED,
    CONTROL_NONE,

    SIDE_BULL,
    SIDE_BEAR,
    SIDE_NEUTRAL,

    STRENGTH_NONE,
    STRENGTH_WEAK,
    STRENGTH_MODERATE,
    STRENGTH_STRONG,

    FVG_STATUS_NONE,
    FVG_STATUS_FRESH,
    FVG_STATUS_TESTED,
    FVG_STATUS_DEFENDED,

    FVG_REACTION_NONE,
    FVG_REACTION_WEAK_TOUCH,
    FVG_REACTION_STRONG_TOUCH,
    FVG_REACTION_INVALIDATED,

    normalize_relative,
)


# ------------------------------------------------------------
# Section 1.3 — Market State
# ------------------------------------------------------------

from Section_1_Global_Core.Data_Contracts_Legacy.market_state import (
    MarketMemory,
)


# ------------------------------------------------------------
# Section 1.4 — Memory
# ------------------------------------------------------------

from Section_1_Global_Core.Data_Contracts_Legacy.memory import (
    FVGMemory,
    SRMemory,
    InstitutionalSRMemory,
    SwingMemory,
    MarketStructureMemory,
    ExecutionMemory,
    ADCNExecutionMemory,
    GlobalLifecycleMemory,
)


# ------------------------------------------------------------
# Section 1.5 — Timeframes
# ------------------------------------------------------------

from Section_1_Global_Core.Data_Contracts_Legacy.timeframes import (
    SUPPORTED_TIMEFRAMES,
    SUPPORTED_TF_COUNT,

    normalize_tf,
    is_supported_tf,
    get_supported_tf,
    get_engine,
    is_breakout_tf,
)


# ------------------------------------------------------------
# Section 1.6 — Outputs
# ------------------------------------------------------------

from Section_1_Global_Core.Data_Contracts_Legacy.outputs import (
    EngineOutput,
    ConfluenceOutput,
    inactive_engine_output,
    create_engine_output_buffer,
)


# ------------------------------------------------------------
# Section 1.7 — Runtime Global State
# ------------------------------------------------------------

from Section_1_Global_Core.Data_Contracts_Legacy import global_state as _global_state


# ------------------------------------------------------------
# Section 1.8 — Symbols
# ------------------------------------------------------------

from Section_1_Global_Core.Symbols.symbols import (
    CURRENT_SYMBOL,
    BTC_SYMBOL,
    set_current_symbol,
    get_current_symbol,
    get_btc_symbol,
    get_market_symbol,
)


# ============================================================
# GLOBAL CORE PACKET
# ============================================================

@dataclass
class GlobalCorePacket:

    # --------------------------------------------------------
    # Symbol context
    # --------------------------------------------------------

    current_symbol: str
    btc_symbol: str

    # --------------------------------------------------------
    # Core definitions
    # --------------------------------------------------------

    supported_timeframes: List[str]
    engine_count: int

    # --------------------------------------------------------
    # Market state / memory
    # --------------------------------------------------------

    market_profile: str
    market_memory: MarketMemory
    global_memory: GlobalLifecycleMemory

    # --------------------------------------------------------
    # Signal lifecycle
    # --------------------------------------------------------

    previous_signal: str
    previous_net_score: float

    last_signal_processed: str

    signal_attempt_count: int
    signal_rejected_count: int

    # --------------------------------------------------------
    # Diagnostics
    # --------------------------------------------------------

    last_failure_stage: str
    last_failure_reason: str

    diag_flow_signal: str
    diag_flow_decision: str

    # --------------------------------------------------------
    # Timeframe buffers
    # --------------------------------------------------------

    signal_buffer: List[str]
    regime_buffer: List[str]
    action_buffer: List[str]

    # --------------------------------------------------------
    # Score buffers
    # --------------------------------------------------------

    bull_score_buffer: List[float]
    bear_score_buffer: List[float]
    net_score_buffer: List[float]
    final_score_buffer: List[float]
    confidence_buffer: List[float]

    # --------------------------------------------------------
    # Current aggregate state
    # --------------------------------------------------------

    bull_score: float
    bear_score: float
    net_score: float
    final_score: float
    confidence: float
    bias_score: float
    confluence: float

    # --------------------------------------------------------
    # Engine outputs
    # --------------------------------------------------------

    engine_output_buffer: List[EngineOutput]

    # --------------------------------------------------------
    # Confluence output
    # --------------------------------------------------------

    confluence_output: ConfluenceOutput


# ============================================================
# PACKET CREATION
# ============================================================

def create_global_core_packet() -> GlobalCorePacket:
    """
    Build a snapshot of the current Section 1 Global Core state.

    The underlying ownership remains in the individual Section 1
    modules. This function only assembles that state into the
    canonical GlobalCorePacket consumed by downstream sections.
    """

    return GlobalCorePacket(

        # ----------------------------------------------------
        # Symbol context
        # ----------------------------------------------------

        current_symbol=_global_state.CURRENT_SYMBOL,
        btc_symbol=_global_state.BTC_SYMBOL,

        # ----------------------------------------------------
        # Core definitions
        # ----------------------------------------------------

        supported_timeframes=SUPPORTED_TIMEFRAMES.copy(),
        engine_count=ENGINE_COUNT,

        # ----------------------------------------------------
        # Market state / memory
        # ----------------------------------------------------

        market_profile=_global_state.MARKET_PROFILE,
        market_memory=_global_state.market_memory,
        global_memory=_global_state.global_memory,

        # ----------------------------------------------------
        # Signal lifecycle
        # ----------------------------------------------------

        previous_signal=_global_state.previous_signal,
        previous_net_score=_global_state.previous_net_score,

        last_signal_processed=_global_state.last_signal_processed,

        signal_attempt_count=_global_state.signal_attempt_count,
        signal_rejected_count=_global_state.signal_rejected_count,

        # ----------------------------------------------------
        # Diagnostics
        # ----------------------------------------------------

        last_failure_stage=_global_state.last_failure_stage,
        last_failure_reason=_global_state.last_failure_reason,

        diag_flow_signal=_global_state.diag_flow_signal,
        diag_flow_decision=_global_state.diag_flow_decision,

        # ----------------------------------------------------
        # Timeframe buffers
        # ----------------------------------------------------

        signal_buffer=_global_state.signal_buffer.copy(),
        regime_buffer=_global_state.regime_buffer.copy(),
        action_buffer=_global_state.action_buffer.copy(),

        # ----------------------------------------------------
        # Score buffers
        # ----------------------------------------------------

        bull_score_buffer=_global_state.bull_score_buffer.copy(),
        bear_score_buffer=_global_state.bear_score_buffer.copy(),
        net_score_buffer=_global_state.net_score_buffer.copy(),
        final_score_buffer=_global_state.final_score_buffer.copy(),
        confidence_buffer=_global_state.confidence_buffer.copy(),

        # ----------------------------------------------------
        # Current aggregate state
        # ----------------------------------------------------

        bull_score=_global_state.bull_score,
        bear_score=_global_state.bear_score,
        net_score=_global_state.net_score,
        final_score=_global_state.final_score,
        confidence=_global_state.confidence,
        bias_score=_global_state.bias_score,
        confluence=_global_state.confluence,

        # ----------------------------------------------------
        # Engine outputs
        # ----------------------------------------------------

        engine_output_buffer=_global_state.engine_output_buffer.copy(),

        # ----------------------------------------------------
        # Confluence output
        # ----------------------------------------------------

        confluence_output=_global_state.confluence_output,
    )


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [

    # Section 1.1
    "STRONG_BUY_THRESHOLD",
    "BUY_THRESHOLD",
    "WEAK_BUY_THRESHOLD",
    "WEAK_SELL_THRESHOLD",
    "SELL_THRESHOLD",
    "STRONG_SELL_THRESHOLD",
    "SCORE_MAX",
    "SCORE_MIN",

    "FVG_MULTIPLIER_NORMAL",
    "FVG_MULTIPLIER_STRONG",
    "FVG_FAILURE_MEMORY_BARS",

    "EMA_7",
    "EMA_25",
    "EMA_50",
    "EMA_100",
    "EMA_200",
    "EMA_300",

    "MARKET_CURRENT",
    "MARKET_BTC",
    "REF_MARKET_CURRENT",
    "REF_MARKET_BTC",

    "ENGINE_SCALP",
    "ENGINE_SWING_SCALP",
    "ENGINE_SWING",
    "ENGINE_BREAKOUT",

    "ENGINE_SCALP_INDEX",
    "ENGINE_SWING_SCALP_INDEX",
    "ENGINE_SWING_INDEX",
    "ENGINE_BREAKOUT_INDEX",

    "ENGINE_COUNT",
    "engine_index",

    # Section 1.2
    "STATE_UNKNOWN",
    "REGIME_BULL_EXPANSION",
    "REGIME_BEAR_EXPANSION",
    "REGIME_BULL_TREND",
    "REGIME_BEAR_TREND",
    "REGIME_COMPRESSION",
    "REGIME_RANGE",

    "ENERGY_EXPANDING",
    "ENERGY_NORMAL",
    "ENERGY_CONTRACTING",
    "ENERGY_DEAD",

    "FATIGUE_NONE",
    "FATIGUE_BULLISH",
    "FATIGUE_BEARISH",

    "TREND_FRESH",
    "TREND_MATURE",
    "TREND_WEAK",
    "TREND_NONE",

    "TRANSITION_NONE",
    "TRANSITION_RISK",
    "TRANSITION_ACTIVE",

    "CONTROL_BULL",
    "CONTROL_BEAR",
    "CONTROL_BALANCED",
    "CONTROL_NONE",

    "SIDE_BULL",
    "SIDE_BEAR",
    "SIDE_NEUTRAL",

    "STRENGTH_NONE",
    "STRENGTH_WEAK",
    "STRENGTH_MODERATE",
    "STRENGTH_STRONG",

    "FVG_STATUS_NONE",
    "FVG_STATUS_FRESH",
    "FVG_STATUS_TESTED",
    "FVG_STATUS_DEFENDED",

    "FVG_REACTION_NONE",
    "FVG_REACTION_WEAK_TOUCH",
    "FVG_REACTION_STRONG_TOUCH",
    "FVG_REACTION_INVALIDATED",

    "normalize_relative",

    # Section 1.3
    "MarketMemory",

    # Section 1.4
    "FVGMemory",
    "SRMemory",
    "InstitutionalSRMemory",
    "SwingMemory",
    "MarketStructureMemory",
    "ExecutionMemory",
    "ADCNExecutionMemory",
    "GlobalLifecycleMemory",

    # Section 1.5
    "SUPPORTED_TIMEFRAMES",
    "SUPPORTED_TF_COUNT",
    "normalize_tf",
    "is_supported_tf",
    "get_supported_tf",
    "get_engine",
    "is_breakout_tf",

    # Section 1.6
    "EngineOutput",
    "ConfluenceOutput",
    "inactive_engine_output",
    "create_engine_output_buffer",

    # Section 1.8
    "CURRENT_SYMBOL",
    "BTC_SYMBOL",
    "set_current_symbol",
    "get_current_symbol",
    "get_btc_symbol",
    "get_market_symbol",

    # Packet
    "GlobalCorePacket",
    "create_global_core_packet",
    "read_decision_history",
    "read_liquidity",
    "read_liquidity_candle",
    "read_liquidity_market_context",
    "annotate_evidence",
    "read_analysis_page",
    "evaluate_price_point",
]

def read_decision_history(symbols=None,intervals=None):
    """Stream committed closed-bar strategy inputs through the public gateway."""
    from .memory_storage.Storage.db import iter_decision_history
    return iter_decision_history(symbols,intervals)


def read_liquidity(symbol,available_before_ms):
    """Observed Binance USDT perpetual features available by decision time.

    Independent venue/market identity; never a replacement for spot candle
    indicators or an estimate of hidden orders/liquidation positions.
    """
    from .liquidity.store import features_at
    return features_at(symbol.upper(),int(available_before_ms))


def read_liquidity_candle(symbol,open_ms,available_before_ms):
    """Closed one-minute perpetual summary; inspect coverage before training."""
    from .liquidity.store import candle_features_at
    return candle_features_at(symbol.upper(),int(open_ms),int(available_before_ms))


def read_liquidity_market_context(symbol,available_before_ms):
    """Causal BTC/ETH relative returns and correlations from recorded perpetuals."""
    from .liquidity.store import market_context_at
    return market_context_at(symbol.upper(),int(available_before_ms))


def annotate_evidence(bars,**options):
    """Public read-only analysis coordinator, separate from engine ownership."""
    from .analysis import annotate
    return annotate(bars,**options)


def read_analysis_page(symbol,interval,limit=1000,*,before=None,context_history=False):
    """Public closed-bar analysis view for local diagnostics and consumers."""
    from .memory_storage.Storage.db import read_state_page
    return read_state_page(symbol.upper(),interval,limit,before=before,context_history=context_history)


def evaluate_price_point(client,features,previous=None):
    """Pure point-in-time evidence coordinator; not a decision or execution gate."""
    from .analysis import evaluate_point
    return evaluate_point(client,features,previous)


def store_decision_evidence(symbol,interval,open_times,*,deadline=None):
    """Worker bridge: retain immutable independent-engine outputs in ADCN memory."""
    from .decision_evidence import capture
    return capture(symbol,interval,open_times,deadline=deadline)


def recover_decision_evidence(symbol,interval,*,deadline=None):
    """Worker bridge: bounded recovery of missing historical decision snapshots."""
    from .decision_evidence import recover_one
    return recover_one(symbol,interval,deadline=deadline)
