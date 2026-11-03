"""Immutable experimental analytical configuration; no live settings mutation."""
from dataclasses import dataclass,asdict
import hashlib
import json
import math

@dataclass(frozen=True)
class RegimeConfig:
    adx_trend_entry:float=25.
    adx_trend_hold:float=21.
    adx_range_max:float=18.
    er_trend_entry:float=.45
    er_trend_hold:float=.35
    er_range_max:float=.30
    dominance_entry:float=.10
    dominance_hold:float=.05
    confirmation_bars:int=3
    volatility_confirmation_bars:int=3
    baseline_length:int=500
    er_length:int=20
    change_length:int=5
    change_deadband:float=.05

    def __post_init__(self):
        for key,value in asdict(self).items():
            if key in ('confirmation_bars','volatility_confirmation_bars','baseline_length','er_length','change_length'):
                if type(value) is not int or not 1<=value<=5000:raise ValueError(f'Invalid {key}')
            elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError(f'Invalid {key}')
        if not 0<=self.adx_range_max<self.adx_trend_hold<=self.adx_trend_entry<=100:raise ValueError('Invalid ADX thresholds')
        if not 0<=self.er_range_max<self.er_trend_hold<=self.er_trend_entry<=1:raise ValueError('Invalid efficiency thresholds')
        if not 0<self.dominance_hold<=self.dominance_entry<=1:raise ValueError('Invalid dominance deadbands')
        if not 0<self.change_deadband<1:raise ValueError('Invalid volatility deadband')

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,separators=(',',':')).encode()).hexdigest()
