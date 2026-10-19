"""Audit configuration — all thresholds and paths."""

from pathlib import Path

_HERE = Path(__file__).resolve().parent
_STORAGE = _HERE.parent / "Storage"

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

KLINES_DB = _STORAGE / "klines.db"
METADATA_DB = _STORAGE / "metadata.db"
LOG_DIR = _HERE / "audit_log"

# ------------------------------------------------------------------
# A1 schema
# ------------------------------------------------------------------

A1_ENABLED = True
A1_MAX_FAILURES_REPORTED = 50

# ------------------------------------------------------------------
# A2 continuity
# ------------------------------------------------------------------

A2_ENABLED = True
A2_MAX_GAPS_REPORTED = 100
A2_AUTO_REFETCH = True
A2_REFETCH_TIMEOUT_S = 30
A2_MARK_COMPROMISED_AFTER_FAILED_REFETCH = True

# ------------------------------------------------------------------
# A3 cross-source
# ------------------------------------------------------------------

A3_ENABLED = True
A3_SAMPLE_PER_PAIR = 5
A3_RUN_INTERVAL_HOURS = 24

# ------------------------------------------------------------------
# A4 consistency
# ------------------------------------------------------------------

A4_ENABLED = True
A4_VOLUME_TOLERANCE = 0.005
A4_PAIRS = [
    ("1m", "15m", 15),
    ("5m", "1h", 12),
    ("15m", "4h", 16),
    ("1h", "1d", 24),
]

# ------------------------------------------------------------------
# A5 freshness
# ------------------------------------------------------------------

A5_ENABLED = True
A5_FRESHNESS_MULTIPLIER = 2.0
