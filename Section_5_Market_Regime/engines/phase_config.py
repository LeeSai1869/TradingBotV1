"""Immutable experimental cycle-sequence settings, independent of other engines."""
from dataclasses import dataclass, asdict
import hashlib
import json
import math


@dataclass(frozen=True)
class PhaseConfig:
    preceding_bars: int = 5
    preceding_max_age: int = 200
    range_min_bars: int = 5
    range_max_bars: int = 120
    evidence_bars: int = 2
    breakout_bars: int = 3
    range_length: int = 100
    er_length: int = 20
    change_length: int = 5
    max_range_atr: float = 6.
    range_er_max: float = .30
    volatility_change_max: float = .05
    breakout_buffer_atr: float = .10
    reclaim_fraction: float = .25

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key in ('preceding_bars', 'preceding_max_age', 'range_min_bars', 'range_max_bars', 'evidence_bars', 'breakout_bars', 'range_length', 'er_length', 'change_length'):
                if type(value) is not int or not 1 <= value <= 5000:
                    raise ValueError('Invalid ' + key)
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('Invalid ' + key)
        if self.range_max_bars < self.range_min_bars or self.preceding_max_age < self.preceding_bars:
            raise ValueError('Invalid sequence lengths')
        if self.range_er_max > 1 or self.reclaim_fraction >= .5 or self.volatility_change_max >= 1:
            raise ValueError('Invalid fractional thresholds')

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
