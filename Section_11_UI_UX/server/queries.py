"""
DB reads for the chart server.
Range queries against the stores. One query per DB per request.
"""
from __future__ import annotations

from Section_1_Global_Core.memory_storage.Storage import db


def get_flags_current(symbol, interval):
    """Latest permanent ADCN row for (symbol, interval)."""
    a = db.read_latest_adcn(symbol, interval)
    if a is None:
        return _empty_flags(interval)
    return {
        "symbol": symbol,
        "tf": interval,
        "bar_time": int(a.get("open_time") or 0),
        "signal_type": a.get("signal_type") or "WAIT",
        "final_score": float(a.get("final_score") or 0.0),
        "decision_state": a.get("decision_state") or "NONE",
        "trigger": a.get("trigger") or "NO_TRIGGER",
        "looking_for": a.get("looking_for"),
        "has_memory": True,
        "memory_length": 1,
        "previous_signals": [],
        "previous_final_scores": [],
    }


def _empty_flags(tf):
    return {
        "tf": tf, "signal_type": "WAIT", "decision_state": "NONE",
        "final_score": 0.0, "trigger": "NO_TRIGGER", "looking_for": None,
        "has_memory": False, "memory_length": 0,
        "previous_signals": [], "previous_final_scores": [],
    }


# ------------------------------------------------------------------
# symbols
# ------------------------------------------------------------------
def get_symbols():
    from Section_1_Global_Core.Symbols.symbols import get_active_symbols
    return get_active_symbols()
