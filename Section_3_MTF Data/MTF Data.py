# ======================================================
# SECTION 3: MTF DATA ACCESS
# ======================================================
# In Python we do not have request.security.
# This layer defines the data contract and the active
# timeframe system. Actual data will be injected later
# by a DataProvider (Binance, CSV, etc.).
# ======================================================

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from section_01_globals import (
    normalize_tf,
    is_supported_tf,
    SUPPORTED_TIMEFRAMES,
    get_engine,
    ENGINE_SCALP,
    ENGINE_SWING_SCALP,
    ENGINE_SWING,
    ENGINE_BREAKOUT
)
from section_02_inputs import (
    HUD_TF_COUNT,
    get_hud_tf,
    is_hud_tf_active,
    ENABLE_SCALP_ENGINE,
    ENABLE_SWING_SCALP_ENGINE,
    ENABLE_SWING_ENGINE,
    ENABLE_BREAKOUT_ENGINE,
    VOLUME_LOOKBACK
)

# =========================
# 3.1 MTF DATA CONTRACT
# =========================

@dataclass
class MTFData:
    tf: str

    # Price
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    prev_open: Optional[float] = None
    prev_high: Optional[float] = None
    prev_low: Optional[float] = None
    prev_close: Optional[float] = None

    volume: float = 0.0
    prev_volume: Optional[float] = None
    volume_ma: Optional[float] = None

    time: Optional[int] = None
    prev_time: Optional[int] = None

    bar_index: int = 0
    prev_bar_index: Optional[int] = None

    current_price: float = 0.0

    vwap: Optional[float] = None

    hl2: Optional[float] = None
    hlc3: Optional[float] = None
    ohlc4: Optional[float] = None

    # EMAs
    ema7: Optional[float] = None
    ema25: Optional[float] = None
    ema50: Optional[float] = None
    ema100: Optional[float] = None
    ema200: Optional[float] = None
    ema300: Optional[float] = None

    ema7_1: Optional[float] = None
    ema25_1: Optional[float] = None
    ema50_1: Optional[float] = None
    ema100_1: Optional[float] = None
    ema200_1: Optional[float] = None
    ema300_1: Optional[float] = None

    wma50: Optional[float] = None

# =========================
# 3.2 REQUIRED TF REGISTRY
# =========================

required_tf_registry: List[str] = []

def required_tf(tf: str):
    """Add a timeframe to the required registry (unique only)."""
    global required_tf_registry
    normalized = normalize_tf(tf)
    if normalized and normalized not in required_tf_registry:
        required_tf_registry.append(normalized)

def build_required_tf_registry(current_chart_tf: str = "15"):
    """
    Build the list of timeframes that must be active.
    Call this once at startup.
    """
    global required_tf_registry
    required_tf_registry = []

    # Source A: HUD selected TFs
    for i in range(8):
        if is_hud_tf_active(i):
            tf = get_hud_tf(i)
            if tf:
                required_tf(tf)

    # Source B: Current chart timeframe
    required_tf(current_chart_tf)

    # Source C: Engine dependencies
    if ENABLE_SCALP_ENGINE:
        required_tf("1")
        required_tf("5")
        required_tf("15")
        # Confidence context
        required_tf("30")
        required_tf("60")
        required_tf("120")
        required_tf("240")

    if ENABLE_SWING_SCALP_ENGINE:
        required_tf("30")
        required_tf("60")
        required_tf("120")
        required_tf("240")

    if ENABLE_SWING_ENGINE:
        required_tf("1D")
        required_tf("1W")
        required_tf("1M")
        required_tf("3M")
        required_tf("6M")

    if ENABLE_BREAKOUT_ENGINE:
        required_tf("5")
        required_tf("15")
        required_tf("60")

def is_required_tf(tf: str) -> bool:
    return normalize_tf(tf) in required_tf_registry

# =========================
# 3.3 ACTIVE TF FLAGS
# =========================

active_tf: Dict[str, bool] = {tf: False for tf in SUPPORTED_TIMEFRAMES}

def update_active_tf_flags():
    """Update the active_tf dictionary from the required registry."""
    global active_tf
    for tf in SUPPORTED_TIMEFRAMES:
        active_tf[tf] = is_required_tf(tf)

# Convenience shortcuts (updated after build_required_tf_registry)
def refresh_active_flags():
    update_active_tf_flags()

# =========================
# 3.4 ENGINE ACTIVE FLAGS
# =========================

def is_scalp_engine_active() -> bool:
    return active_tf.get("1", False) or active_tf.get("5", False) or active_tf.get("15", False)

def is_swing_scalp_engine_active() -> bool:
    return (active_tf.get("30", False) or active_tf.get("60", False) or
            active_tf.get("120", False) or active_tf.get("240", False))

def is_swing_engine_active() -> bool:
    return (active_tf.get("1D", False) or active_tf.get("1W", False) or
            active_tf.get("1M", False) or active_tf.get("3M", False) or
            active_tf.get("6M", False))

def is_breakout_baseline_active() -> bool:
    return active_tf.get("5", False) or active_tf.get("15", False) or active_tf.get("60", False)

# =========================
# 3.5 MTF DATA STORE
# =========================

# This dictionary will hold the latest MTFData for each active timeframe.
# It will be filled by the DataProvider later.
mtf_data_store: Dict[str, Optional[MTFData]] = {tf: None for tf in SUPPORTED_TIMEFRAMES}

def get_mtf_data(tf: str) -> Optional[MTFData]:
    """Return the MTFData for a timeframe, or None if not available."""
    normalized = normalize_tf(tf)
    return mtf_data_store.get(normalized)

def set_mtf_data(tf: str, data: MTFData):
    """Store MTFData for a timeframe."""
    normalized = normalize_tf(tf)
    mtf_data_store[normalized] = data

# =========================
# 3.6 INITIALIZATION HELPER
# =========================

def initialize_mtf_layer(current_chart_tf: str = "15"):
    """
    Call this once at program start.
    """
    build_required_tf_registry(current_chart_tf)
    refresh_active_flags()
    print(f"[MTF] Required timeframes: {required_tf_registry}")
    print(f"[MTF] Active flags: {[tf for tf, active in active_tf.items() if active]}")

# ======================================================
# SECTION 3 END
# ======================================================