"""Immutable experimental synthesis weights; not validated trading parameters."""
from dataclasses import dataclass,asdict
import hashlib
import json
import math


@dataclass(frozen=True)
class BiasConfig:
    trend_structure_weight:float=.45
    momentum_weight:float=.25
    observed_flow_weight:float=.15
    phase_weight:float=.05
    independent_sentiment_weight:float=.10
    trend_share:float=.5
    minimum_directional_coverage:float=.60
    entry_deadband:float=.15
    hold_deadband:float=.075
    strong_threshold:float=.65
    strong_context_min:float=.50
    conflict_min_points:float=.10
    confirmation_bars:int=3

    def __post_init__(self):
        for key,value in asdict(self).items():
            if key=='confirmation_bars':
                if type(value) is not int or not 1<=value<=5000:raise ValueError('Invalid '+key)
            elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:raise ValueError('Invalid '+key)
        weights=(self.trend_structure_weight,self.momentum_weight,self.observed_flow_weight,self.phase_weight,self.independent_sentiment_weight)
        if abs(sum(weights)-1)>1e-9:raise ValueError('Full directional budget must sum to one')
        if not 0<self.hold_deadband<=self.entry_deadband<self.strong_threshold<=1 or self.minimum_directional_coverage<=0:raise ValueError('Invalid Bias thresholds')

    @property
    def fingerprint(self):return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,separators=(',',':')).encode()).hexdigest()
