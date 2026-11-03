"""Explicit horizon policy; weights are research defaults, not predictive weights."""
from dataclasses import dataclass, asdict
import hashlib
import json
import math


@dataclass(frozen=True)
class AggregationConfig:
    short_max_ms: int = 900000
    medium_max_ms: int = 14400000
    freshness_grace_ms: int = 30000
    minimum_coverage: float = .50
    consensus_share: float = .67
    allow_pending: bool = False
    availability: str = 'ACTUAL'
    horizon_weights: tuple = (('short',1.),('medium',1.),('long',1.))
    timeframe_weights: tuple = ()

    def __post_init__(self):
        for key in ('short_max_ms','medium_max_ms','freshness_grace_ms'):
            if type(getattr(self,key)) is not int or getattr(self,key)<0:raise ValueError('Invalid '+key)
        if not 0<self.short_max_ms<self.medium_max_ms:raise ValueError('Invalid horizon boundaries')
        for key in ('minimum_coverage','consensus_share'):
            value=getattr(self,key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<value<=1:raise ValueError('Invalid '+key)
        if type(self.allow_pending) is not bool or self.availability not in ('ACTUAL','RECONSTRUCTED_CLOSE'):raise ValueError('Invalid availability policy')
        for key in ('horizon_weights','timeframe_weights'):
            pairs=tuple(tuple(pair) for pair in getattr(self,key))
            if any(len(pair)!=2 or not isinstance(pair[0],str) or not pair[0] or isinstance(pair[1],bool) or not isinstance(pair[1],(int,float)) or not math.isfinite(pair[1]) or pair[1]<=0 for pair in pairs):raise ValueError('Invalid '+key)
            if len({pair[0] for pair in pairs})!=len(pairs):raise ValueError('Duplicate '+key)
            object.__setattr__(self,key,pairs)
        if set(dict(self.horizon_weights))!={'short','medium','long'}:raise ValueError('All horizon weights required')

    @property
    def fingerprint(self):return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,separators=(',',':')).encode()).hexdigest()
