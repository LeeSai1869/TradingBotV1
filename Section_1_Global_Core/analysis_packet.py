"""Public numeric contract for read-only analysis inputs; no strategy ownership."""
import math


def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def clean(value):return value if isinstance(value,(str,bool)) or number(value) else None
