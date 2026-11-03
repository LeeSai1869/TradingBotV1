"""Immutable experimental Momentum configuration."""
from dataclasses import dataclass,asdict
import hashlib
import json
import math

@dataclass(frozen=True)
class MomentumConfig:
    entry_deadband:float=.15
    hold_deadband:float=.075
    confirmation_bars:int=3
    acceleration_deadband:float=.05
    exhaustion_bars:int=3
    corroboration_bars:int=5
    momentum_length:int=10
    atr_reference:float=2.
    roc_reference_pct:float=1.
    anchor_reference_points:float=10.
    macd_reference_atr:float=.1
    use_macd:bool=False

    def __post_init__(self):
        for key,value in asdict(self).items():
            if key=='use_macd':
                if type(value) is not bool:raise ValueError('Invalid '+key)
            elif key.endswith('_bars') or key.endswith('_length'):
                if type(value) is not int or not 1<=value<=5000:raise ValueError('Invalid '+key)
            elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Invalid '+key)
        if not self.hold_deadband<=self.entry_deadband<=1:raise ValueError('Invalid direction deadbands')

    @property
    def fingerprint(self):return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,separators=(',',':')).encode()).hexdigest()
