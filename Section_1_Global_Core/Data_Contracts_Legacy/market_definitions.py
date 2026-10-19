# ============================================================
# 02_market_definitions.py
# Market state definitions
# ============================================================


# ------------------------------------------------------------
# Market regime
# ------------------------------------------------------------

STATE_UNKNOWN = "UNKNOWN"

REGIME_BULL_EXPANSION = "BULL_EXPANSION"
REGIME_BEAR_EXPANSION = "BEAR_EXPANSION"

REGIME_BULL_TREND = "BULL_TREND"
REGIME_BEAR_TREND = "BEAR_TREND"

REGIME_COMPRESSION = "COMPRESSION"
REGIME_RANGE = "RANGE"


# ------------------------------------------------------------
# Market energy
# ------------------------------------------------------------

ENERGY_EXPANDING = "EXPANDING"
ENERGY_NORMAL = "NORMAL"
ENERGY_CONTRACTING = "CONTRACTING"
ENERGY_DEAD = "DEAD"


# ------------------------------------------------------------
# Fatigue
# ------------------------------------------------------------

FATIGUE_NONE = "NONE"
FATIGUE_BULLISH = "BULLISH"
FATIGUE_BEARISH = "BEARISH"


# ------------------------------------------------------------
# Trend maturity
# ------------------------------------------------------------

TREND_FRESH = "FRESH"
TREND_MATURE = "MATURE"
TREND_WEAK = "WEAK"
TREND_NONE = "NONE"


# ------------------------------------------------------------
# Transition
# ------------------------------------------------------------

TRANSITION_NONE = "NONE"
TRANSITION_RISK = "RISK"
TRANSITION_ACTIVE = "ACTIVE"


# ------------------------------------------------------------
# Market control
# ------------------------------------------------------------

CONTROL_BULL = "BULL"
CONTROL_BEAR = "BEAR"
CONTROL_BALANCED = "BALANCED"
CONTROL_NONE = "NONE"


# ------------------------------------------------------------
# Market side
# ------------------------------------------------------------

SIDE_BULL = "BULL"
SIDE_BEAR = "BEAR"
SIDE_NEUTRAL = "NEUTRAL"


# ------------------------------------------------------------
# Strength
# ------------------------------------------------------------

STRENGTH_NONE = "NONE"
STRENGTH_WEAK = "WEAK"
STRENGTH_MODERATE = "MODERATE"
STRENGTH_STRONG = "STRONG"


# ------------------------------------------------------------
# FVG state
# ------------------------------------------------------------

FVG_STATUS_NONE = "NONE"
FVG_STATUS_FRESH = "FRESH"
FVG_STATUS_TESTED = "TESTED"
FVG_STATUS_DEFENDED = "DEFENDED"

FVG_REACTION_NONE = "NONE"
FVG_REACTION_WEAK_TOUCH = "WEAK_TOUCH"
FVG_REACTION_STRONG_TOUCH = "STRONG_TOUCH"
FVG_REACTION_INVALIDATED = "INVALIDATED"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def normalize_relative(
    value,
    minimum,
    maximum,
    power=1.0,
    higher_is_better=True,
):
    """
    Normalize a value to the range 0.0 - 1.0.
    """

    if value is None or minimum is None or maximum is None:
        return None

    if maximum <= minimum:
        return 1.0

    relative = (value - minimum) / (maximum - minimum)

    relative = max(0.0, min(1.0, relative))

    if not higher_is_better:
        relative = 1.0 - relative

    if power != 1.0:
        relative = relative ** power

    return relative