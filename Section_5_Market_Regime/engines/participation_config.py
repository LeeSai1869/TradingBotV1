"""Immutable experimental Participation configuration."""
from dataclasses import dataclass,asdict
import hashlib
import json
import math

@dataclass(frozen=True)
class ParticipationConfig:
    very_low_rvol:float=.5
    low_rvol:float=.8
    high_rvol:float=1.5
    extreme_rvol:float=3.
    change_deadband_pct:float=10.
    price_deadband_fraction:float=.001
    confirmation_bars:int=3

    def __post_init__(self):
        for key,value in asdict(self).items():
            if key=='confirmation_bars':
                if type(value) is not int or not 1<=value<=5000:raise ValueError('Invalid '+key)
            elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Invalid '+key)
        if not self.very_low_rvol<self.low_rvol<self.high_rvol<self.extreme_rvol:raise ValueError('RVOL thresholds must increase')

    @property
    def fingerprint(self):return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,separators=(',',':')).encode()).hexdigest()
