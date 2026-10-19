# ============================================================
# 05_timeframes.py
# Timeframe normalization and routing
# ============================================================

from .constants import (
    ENGINE_SCALP,
    ENGINE_SWING_SCALP,
    ENGINE_SWING,
)


# ------------------------------------------------------------
# Supported timeframes
# ------------------------------------------------------------

SUPPORTED_TIMEFRAMES = [
    "1",
    "5",
    "15",
    "30",
    "60",
    "120",
    "240",
    "1D",
    "1W",
    "1M",
    "3M",
    "6M",
]

SUPPORTED_TF_COUNT = len(SUPPORTED_TIMEFRAMES)


# ------------------------------------------------------------
# Normalization
# ------------------------------------------------------------

def normalize_tf(tf):

    if tf is None:
        return None

    tf = str(tf).strip().upper()

    aliases = {
        "D": "1D",
        "W": "1W",
        "M": "1M",
    }

    return aliases.get(tf, tf)


# ------------------------------------------------------------
# Validation
# ------------------------------------------------------------

def is_supported_tf(tf):

    tf = normalize_tf(tf)

    return tf in SUPPORTED_TIMEFRAMES


# ------------------------------------------------------------
# Indexed access
# ------------------------------------------------------------

def get_supported_tf(index):

    if 0 <= index < SUPPORTED_TF_COUNT:
        return SUPPORTED_TIMEFRAMES[index]

    return "6M"


# ------------------------------------------------------------
# Engine routing
# ------------------------------------------------------------

def get_engine(tf):

    tf = normalize_tf(tf)

    if tf in ("1", "5", "15"):
        return ENGINE_SCALP

    if tf in ("30", "60", "120", "240"):
        return ENGINE_SWING_SCALP

    if tf in ("1D", "1W", "1M", "3M", "6M"):
        return ENGINE_SWING

    return ""


def is_breakout_tf(tf):

    tf = normalize_tf(tf)

    return tf in ("5", "15", "60")