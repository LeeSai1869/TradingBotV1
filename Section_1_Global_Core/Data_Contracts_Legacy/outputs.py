# ============================================================
# 06_outputs.py
# Engine and confluence outputs
# ============================================================

from dataclasses import dataclass
from .constants import (
    ENGINE_SCALP,
    ENGINE_SWING_SCALP,
    ENGINE_SWING,
    ENGINE_BREAKOUT,
)


# ------------------------------------------------------------
# Engine output
# ------------------------------------------------------------

@dataclass
class EngineOutput:

    engine_name: str = ""

    active: bool = False

    engine_score: float = 0.0
    opportunity_score: float = 0.0
    confidence_score: float = 0.0
    decision_score: float = 0.0

    signal_type: str = "NONE"


# ------------------------------------------------------------
# Confluence output
# ------------------------------------------------------------

@dataclass
class ConfluenceOutput:

    active: bool = False
    score: float = 0.0

    contributing_engines: int = 0
    contributing_timeframes: int = 0


# ------------------------------------------------------------
# Engine helpers
# ------------------------------------------------------------

def inactive_engine_output(engine_name):

    return EngineOutput(
        engine_name=engine_name,
        active=False,
        engine_score=0.0,
        opportunity_score=0.0,
        confidence_score=0.0,
        decision_score=0.0,
        signal_type="NONE",
    )


def create_engine_output_buffer():

    return [
        inactive_engine_output(ENGINE_SCALP),
        inactive_engine_output(ENGINE_SWING_SCALP),
        inactive_engine_output(ENGINE_SWING),
        inactive_engine_output(ENGINE_BREAKOUT),
    ]# ============================================================
# 06_outputs.py
# Engine and confluence outputs
# ============================================================

from dataclasses import dataclass
from .constants import (
    ENGINE_SCALP,
    ENGINE_SWING_SCALP,
    ENGINE_SWING,
    ENGINE_BREAKOUT,
)


# ------------------------------------------------------------
# Engine output
# ------------------------------------------------------------

@dataclass
class EngineOutput:

    engine_name: str = ""

    active: bool = False

    engine_score: float = 0.0
    opportunity_score: float = 0.0
    confidence_score: float = 0.0
    decision_score: float = 0.0

    signal_type: str = "NONE"


# ------------------------------------------------------------
# Confluence output
# ------------------------------------------------------------

@dataclass
class ConfluenceOutput:

    active: bool = False
    score: float = 0.0

    contributing_engines: int = 0
    contributing_timeframes: int = 0


# ------------------------------------------------------------
# Engine helpers
# ------------------------------------------------------------

def inactive_engine_output(engine_name):

    return EngineOutput(
        engine_name=engine_name,
        active=False,
        engine_score=0.0,
        opportunity_score=0.0,
        confidence_score=0.0,
        decision_score=0.0,
        signal_type="NONE",
    )


def create_engine_output_buffer():

    return [
        inactive_engine_output(ENGINE_SCALP),
        inactive_engine_output(ENGINE_SWING_SCALP),
        inactive_engine_output(ENGINE_SWING),
        inactive_engine_output(ENGINE_BREAKOUT),
    ]