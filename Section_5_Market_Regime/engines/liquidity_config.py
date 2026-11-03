"""Independent, experimental liquidity interpretation policy."""
from dataclasses import dataclass, asdict
import hashlib
import json
import math


@dataclass(frozen=True)
class LiquidityConfig:
    liquidity_length: int = 20
    pivot_max_age_bars: int = 500
    sweep_confirmation_bars: int = 2
    sweep_max_bars: int = 5
    at_level_bps: float = 1.
    near_level_bps: float = 50.
    depth_bps: int = 10
    execution_notional_usdt: int = 10000
    normal_depth_multiple: float = 2.
    deep_depth_multiple: float = 10.
    max_spread_bps: float = 2.
    max_slippage_bps: float = 5.
    withdrawal_fraction: float = .50
    oi_change_threshold_pct: float = .50
    max_cross_market_basis_bps: float = 100.
    sample_max_age_ms: int = 10000
    context_max_age_ms: int = 120000

    def __post_init__(self):
        integers = {'liquidity_length','pivot_max_age_bars','sweep_confirmation_bars','sweep_max_bars','depth_bps','execution_notional_usdt','sample_max_age_ms','context_max_age_ms'}
        for key, value in asdict(self).items():
            if key in integers:
                if type(value) is not int or value <= 0:raise ValueError('Invalid ' + key)
            elif isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or value <= 0:raise ValueError('Invalid ' + key)
        if self.depth_bps not in (5,10,25,50,100) or self.execution_notional_usdt not in (1000,10000,100000):raise ValueError('Unsupported recorded execution band/size')
        if self.at_level_bps >= self.near_level_bps or self.normal_depth_multiple >= self.deep_depth_multiple or self.withdrawal_fraction >= 1:raise ValueError('Invalid liquidity thresholds')
        if not self.sweep_confirmation_bars <= self.sweep_max_bars <= 5000 or self.liquidity_length > 5000 or self.pivot_max_age_bars > 5000:raise ValueError('Invalid interpretation window')
        if self.sample_max_age_ms > 10000 or self.context_max_age_ms > 120000:raise ValueError('Do not relax recorder freshness guarantees')

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(',',':')).encode()).hexdigest()
