# ======================================================
# SECTION 4 — STATE RESET
# ======================================================
# Clears every per-(symbol, tf) state store in Section 4.
# Call this before starting a fresh backfill pass, or when
# you want a clean slate for debugging.
# ======================================================

from __future__ import annotations


def reset_all_state() -> None:
    from Section_4_Features.features.support_resistance import _sr_memory_store
    from Section_4_Features.features.bos_structure import (
        _structure_memory_store,
        _SWING_PIVOT_STATES,
        _FLIP_CANDIDATE_STATES,
    )
    from Section_4_Features.features.market_imbalance import _imbalance_memory_store
    from Section_4_Features.features.market_location import _location_memory_store

    _sr_memory_store.clear()
    _structure_memory_store.clear()
    _SWING_PIVOT_STATES.clear()
    _FLIP_CANDIDATE_STATES.clear()
    _imbalance_memory_store.clear()
    _location_memory_store.clear()


__all__ = ["reset_all_state"]