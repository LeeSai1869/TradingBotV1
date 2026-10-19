# ============================================================
# section_1_8_symbols.py  —  v2
# Global symbol registry — the single source of truth
# ============================================================
#
#   active    = approved ∩ top50            (capped at active_cap)
#   inactive  = approved − top50
#   processing = active
#
# Rules:
#   - Coin drops from top50       -> stays approved, becomes inactive.
#   - Coin re-enters top50        -> goes to pending (reactivation).
#   - New top-50 coin             -> goes to pending (new entrant).
#   - active_cap is configurable in symbols.json (default 50).
# ============================================================

from __future__ import annotations

import json
from pathlib import Path


_SYMBOLS_JSON = Path(__file__).resolve().parent / "symbols.json"

BTC_SYMBOL = "BTCUSDT"

_CACHE: dict = {}
_CACHE_MTIME: float = 0.0


def _load_from_disk() -> dict:
    if not _SYMBOLS_JSON.exists():
        raise FileNotFoundError(str(_SYMBOLS_JSON))
    data = json.loads(_SYMBOLS_JSON.read_text(encoding="utf-8"))

    if data.get("schema_version") != 2:
        raise ValueError(
            "symbols.json must be schema_version 2 (got "
            + str(data.get("schema_version")) + ")"
        )
    for key in ("approved", "disapproved", "pending", "top50"):
        if not isinstance(data.get(key), list):
            raise ValueError("symbols.json: '" + key + "' must be a list")

    cap = int(data.get("active_cap", 50))
    if cap < 1:
        raise ValueError("active_cap must be >= 1")

    app = {e["symbol"] for e in data["approved"]}
    dis = {e["symbol"] for e in data["disapproved"]}
    if app & dis:
        raise ValueError(
            "symbols.json: overlap approved/disapproved: "
            + ", ".join(sorted(app & dis))
        )
    return data


def _ensure_cache() -> None:
    global _CACHE, _CACHE_MTIME
    mtime = _SYMBOLS_JSON.stat().st_mtime
    if not _CACHE or mtime != _CACHE_MTIME:
        _CACHE = _load_from_disk()
        _CACHE_MTIME = mtime


def reload() -> None:
    global _CACHE, _CACHE_MTIME
    _CACHE = {}
    _CACHE_MTIME = 0.0


# ------------------------------------------------------------
# Read API
# ------------------------------------------------------------

def get_active_cap() -> int:
    _ensure_cache()
    return int(_CACHE.get("active_cap", 50))


def get_approved_symbols() -> list[str]:
    _ensure_cache()
    return [e["symbol"] for e in _CACHE["approved"]]


def get_disapproved_symbols() -> list[str]:
    _ensure_cache()
    return [e["symbol"] for e in _CACHE["disapproved"]]


def get_pending() -> list[dict]:
    _ensure_cache()
    return list(_CACHE.get("pending", []))


def get_top50() -> list[str]:
    _ensure_cache()
    return [e["symbol"] for e in _CACHE.get("top50", [])]


def get_active_symbols() -> list[str]:
    """approved ∩ top50, capped by active_cap."""
    _ensure_cache()
    top = set(get_top50())
    approved = [e["symbol"] for e in _CACHE["approved"]]
    active = [s for s in approved if s in top]
    cap = get_active_cap()
    return active[:cap]


def get_inactive_symbols() -> list[str]:
    """approved − top50."""
    _ensure_cache()
    top = set(get_top50())
    return [e["symbol"] for e in _CACHE["approved"] if e["symbol"] not in top]


def get_processing_symbols() -> list[str]:
    """Backward-compat alias for get_active_symbols()."""
    return get_active_symbols()


def is_approved(symbol: str) -> bool:
    return symbol in set(get_approved_symbols())


def is_disapproved(symbol: str) -> bool:
    return symbol in set(get_disapproved_symbols())


def is_active(symbol: str) -> bool:
    return symbol in set(get_active_symbols())


def get_staged_symbols() -> list[str]:
    """Symbols approved in principle but not yet active (Phase A: BTC+SUI only)."""
    _ensure_cache()
    return [e["symbol"] for e in _CACHE.get("staged", [])]


def get_btc_symbol() -> str:
    return BTC_SYMBOL


# ------------------------------------------------------------
# Legacy compat
# ------------------------------------------------------------

CURRENT_SYMBOL = ""


def set_current_symbol(symbol):
    global CURRENT_SYMBOL
    CURRENT_SYMBOL = "" if symbol is None else str(symbol).upper()
    return CURRENT_SYMBOL


def get_current_symbol():
    return CURRENT_SYMBOL


def get_market_symbol(market_profile):
    return BTC_SYMBOL if market_profile == "BTC" else CURRENT_SYMBOL
