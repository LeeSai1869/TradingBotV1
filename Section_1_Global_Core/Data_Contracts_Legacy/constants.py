# ============================================================
# 01_constants.py
# Fixed system constants
# ============================================================

# ------------------------------------------------------------
# Score thresholds
# ------------------------------------------------------------

STRONG_BUY_THRESHOLD = 80
BUY_THRESHOLD = 60
WEAK_BUY_THRESHOLD = 40

WEAK_SELL_THRESHOLD = -40
SELL_THRESHOLD = -60
STRONG_SELL_THRESHOLD = -80

SCORE_MAX = 100
SCORE_MIN = 0


# ------------------------------------------------------------
# FVG configuration
# ------------------------------------------------------------

FVG_MULTIPLIER_NORMAL = 1.0
FVG_MULTIPLIER_STRONG = 1.5
FVG_FAILURE_MEMORY_BARS = 50


# ------------------------------------------------------------
# EMA lengths
# ------------------------------------------------------------

EMA_7 = 7
EMA_25 = 25
EMA_50 = 50
EMA_100 = 100
EMA_200 = 200
EMA_300 = 300


# ------------------------------------------------------------
# Market references
# ------------------------------------------------------------

MARKET_CURRENT = "CURRENT"
MARKET_BTC = "BTC"


# ------------------------------------------------------------
# Engine definitions
# ------------------------------------------------------------

ENGINE_SCALP = "SCALP"
ENGINE_SWING_SCALP = "SWING_SCALP"
ENGINE_SWING = "SWING"
ENGINE_BREAKOUT = "BREAKOUT"

ENGINE_SCALP_INDEX = 0
ENGINE_SWING_SCALP_INDEX = 1
ENGINE_SWING_INDEX = 2
ENGINE_BREAKOUT_INDEX = 3

ENGINE_COUNT = 4


def engine_index(engine_name):
    mapping = {
        ENGINE_SCALP: ENGINE_SCALP_INDEX,
        ENGINE_SWING_SCALP: ENGINE_SWING_SCALP_INDEX,
        ENGINE_SWING: ENGINE_SWING_INDEX,
        ENGINE_BREAKOUT: ENGINE_BREAKOUT_INDEX,
    }

    return mapping.get(engine_name, -1)