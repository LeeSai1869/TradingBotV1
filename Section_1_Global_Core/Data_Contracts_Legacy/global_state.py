# ============================================================
# 08_global_state.py
# Runtime global state
# ============================================================

from .constants import (
    MARKET_CURRENT,
)

from .memory import GlobalLifecycleMemory
from .market_state import MarketMemory
from .outputs import (
    ConfluenceOutput,
    create_engine_output_buffer,
)
from ..Symbols.symbols import (
    CURRENT_SYMBOL,
    BTC_SYMBOL,
)


# ------------------------------------------------------------
# Processing state
# ------------------------------------------------------------

last_bull_pivot_processed = None
last_bear_pivot_processed = None

last_signal_processed = ""

diag_flow_signal = ""
diag_flow_decision = ""

previous_signal = ""
previous_net_score = 0.0


# ------------------------------------------------------------
# Market memory
# ------------------------------------------------------------

market_memory = MarketMemory()

global_memory = GlobalLifecycleMemory()


# ------------------------------------------------------------
# Failure diagnostics
# ------------------------------------------------------------

last_failure_stage = ""
last_failure_reason = ""

signal_attempt_count = 0
signal_rejected_count = 0


# ------------------------------------------------------------
# Timeframe buffers
# ------------------------------------------------------------

signal_buffer = []
regime_buffer = []
action_buffer = []

bull_score_buffer = []
bear_score_buffer = []
net_score_buffer = []
final_score_buffer = []
confidence_buffer = []


# ------------------------------------------------------------
# Engine outputs
# ------------------------------------------------------------

engine_output_buffer = create_engine_output_buffer()


# ------------------------------------------------------------
# Current scores
# ------------------------------------------------------------

bull_score = 0.0
bear_score = 0.0
net_score = 0.0
final_score = 0.0

confidence = 0.0
bias_score = 0.0
confluence = 0.0


# ------------------------------------------------------------
# Confluence
# ------------------------------------------------------------

confluence_output = ConfluenceOutput()


# ------------------------------------------------------------
# Market selection
# ------------------------------------------------------------

MARKET_PROFILE = MARKET_CURRENT# ============================================================
# 08_global_state.py
# Runtime global state
# ============================================================

from .constants import (
    MARKET_CURRENT,
)

from .memory import GlobalLifecycleMemory
from .market_state import MarketMemory
from .outputs import (
    ConfluenceOutput,
    create_engine_output_buffer,
)
from ..Symbols.symbols import (
    CURRENT_SYMBOL,
    BTC_SYMBOL,
)


# ------------------------------------------------------------
# Processing state
# ------------------------------------------------------------

last_bull_pivot_processed = None
last_bear_pivot_processed = None

last_signal_processed = ""

diag_flow_signal = ""
diag_flow_decision = ""

previous_signal = ""
previous_net_score = 0.0


# ------------------------------------------------------------
# Market memory
# ------------------------------------------------------------

market_memory = MarketMemory()

global_memory = GlobalLifecycleMemory()


# ------------------------------------------------------------
# Failure diagnostics
# ------------------------------------------------------------

last_failure_stage = ""
last_failure_reason = ""

signal_attempt_count = 0
signal_rejected_count = 0


# ------------------------------------------------------------
# Timeframe buffers
# ------------------------------------------------------------

signal_buffer = []
regime_buffer = []
action_buffer = []

bull_score_buffer = []
bear_score_buffer = []
net_score_buffer = []
final_score_buffer = []
confidence_buffer = []


# ------------------------------------------------------------
# Engine outputs
# ------------------------------------------------------------

engine_output_buffer = create_engine_output_buffer()


# ------------------------------------------------------------
# Current scores
# ------------------------------------------------------------

bull_score = 0.0
bear_score = 0.0
net_score = 0.0
final_score = 0.0

confidence = 0.0
bias_score = 0.0
confluence = 0.0


# ------------------------------------------------------------
# Confluence
# ------------------------------------------------------------

confluence_output = ConfluenceOutput()


# ------------------------------------------------------------
# Market selection
# ------------------------------------------------------------

MARKET_PROFILE = MARKET_CURRENT