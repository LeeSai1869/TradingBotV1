# ======================================================
# FEATURE REGISTRY
# Lists every pure feature module. feature_builder loops this.
# Adding a feature = create the module + add one entry here.
# ======================================================

from __future__ import annotations
import importlib


MODULES = (
    "ema",
    "wma",
    "rsi",
    "di_adx",
    "atr",
    "volume",
    "candle",
    "vwap",
)


def load():
    """Return a list of (module_name, module_object, declaration_dict)."""
    out = []
    for name in MODULES:
        mod = importlib.import_module(
            f"Section_4_Features.features.{name}"
        )
        decl = {
            "name": getattr(mod, "NAME", name),
            "inputs": getattr(mod, "INPUTS", ("df",)),
            "output_fields": getattr(mod, "OUTPUT_FIELDS", ()),
            "module": mod,
        }
        out.append(decl)
    return out


__all__ = ["MODULES", "load"]
