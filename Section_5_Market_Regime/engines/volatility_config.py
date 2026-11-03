"""Immutable experimental volatility policy."""
from dataclasses import dataclass,asdict
import hashlib
import json
import math

@dataclass(frozen=True)
class VolatilityConfig:
    baseline_length:int=500
    change_length:int=5
    return_length:int=20
    confirmation_bars:int=3
    shock_confirmation_bars:int=1
    change_deadband:float=.05
    skew_threshold:float=1.
    moderate_shock_atr:float=3.
    extreme_shock_atr:float=5.

    def __post_init__(self):
        for key,value in asdict(self).items():
            if key.endswith('_length') or key.endswith('_bars'):
                if type(value) is not int or not (2 if key.endswith('_length') else 1)<=value<=5000:raise ValueError('Invalid '+key)
            elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Invalid '+key)
        if self.change_deadband>=1 or self.moderate_shock_atr>=self.extreme_shock_atr:raise ValueError('Invalid volatility thresholds')

    @property
    def fingerprint(self):return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,separators=(',',':')).encode()).hexdigest()
