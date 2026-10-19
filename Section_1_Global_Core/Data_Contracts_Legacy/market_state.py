# ============================================================
# 07_market_state.py
# Current market state
# ============================================================

from dataclasses import dataclass


@dataclass
class MarketMemory:

    last_regime: str = "UNKNOWN"
    last_signal: str = ""

    signal_age: int = 0

    last_strong_high: float | None = None
    last_strong_low: float | None = None

    last_fvg_state: str = ""

    trend_age: int = 0

    previous_score: float = 0.0
    previous_confidence: float = 0.0# ============================================================
# 07_market_state.py
# Current market state
# ============================================================

from dataclasses import dataclass


@dataclass
class MarketMemory:

    last_regime: str = "UNKNOWN"
    last_signal: str = ""

    signal_age: int = 0

    last_strong_high: float | None = None
    last_strong_low: float | None = None

    last_fvg_state: str = ""

    trend_age: int = 0

    previous_score: float = 0.0
    previous_confidence: float = 0.0# ============================================================
# 07_market_state.py
# Current market state
# ============================================================

from dataclasses import dataclass


@dataclass
class MarketMemory:

    last_regime: str = "UNKNOWN"
    last_signal: str = ""

    signal_age: int = 0

    last_strong_high: float | None = None
    last_strong_low: float | None = None

    last_fvg_state: str = ""

    trend_age: int = 0

    previous_score: float = 0.0
    previous_confidence: float = 0.0