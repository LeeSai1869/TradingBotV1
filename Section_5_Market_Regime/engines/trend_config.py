"""Immutable Trend settings; separate from other engines' configurations."""
from dataclasses import dataclass,asdict
import hashlib
import json
import math

@dataclass(frozen=True)
class TrendConfig:
    entry_deadband:float=.20
    hold_deadband:float=.10
    slope_reference_atr:float=.5
    confirmation_bars:int=3
    persistence_bars:int=5
    persistence_points:float=5.
    exhaustion_bars:int=3
    established_strength:float=50.
    er_length:int=20
    slope_length:int=5
    consistency_length:int=20

    def __post_init__(self):
        for key,value in asdict(self).items():
            if key.endswith('_bars') or key.endswith('_length'):
                if type(value) is not int or not 1<=value<=5000:raise ValueError('Invalid '+key)
            elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Invalid '+key)
        if not 0<self.hold_deadband<=self.entry_deadband<=1:raise ValueError('Invalid direction deadbands')
        if not 0<self.slope_reference_atr<=10:raise ValueError('Invalid slope reference')
        if not 0<self.persistence_points<=100 or not 0<self.established_strength<=100:raise ValueError('Invalid strength thresholds')

    @property
    def fingerprint(self):return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,separators=(',',':')).encode()).hexdigest()
