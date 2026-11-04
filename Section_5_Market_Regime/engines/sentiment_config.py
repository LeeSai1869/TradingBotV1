"""Immutable research defaults for a partial derivatives-context classifier."""
from dataclasses import dataclass, asdict
import hashlib
import json
import math


@dataclass(frozen=True)
class SentimentConfig:
    news_ttl_ms: int = 21600000
    social_ttl_ms: int = 3600000
    external_neutral_band: float = .10
    external_extreme_band: float = .60
    market_wide_factor: float = .50
    funding_neutral_fraction: float = .00005
    funding_strength_fraction: float = .00030
    funding_change_fraction: float = .00005
    funding_rapid_change_fraction: float = .00020
    leverage_build_pct: float = 1.
    leverage_funding_fraction: float = .00030
    high_liquidations_usdt_per_second: float = 200000.
    extreme_liquidations_usdt_per_second: float = 2000000.
    max_cross_market_basis_bps: float = 100.
    sample_max_age_ms: int = 10000
    context_max_age_ms: int = 120000

    def __post_init__(self):
        for key,value in asdict(self).items():
            if key.endswith('_ms'):
                if type(value) is not int or value<=0:raise ValueError('Invalid '+key)
            elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Invalid '+key)
        if not self.funding_neutral_fraction<self.funding_strength_fraction or not self.funding_change_fraction<self.funding_rapid_change_fraction:raise ValueError('Invalid funding thresholds')
        if self.high_liquidations_usdt_per_second>=self.extreme_liquidations_usdt_per_second:raise ValueError('Invalid stress thresholds')
        if not 0<self.external_neutral_band<self.external_extreme_band<=1 or not 0<self.market_wide_factor<=1:raise ValueError('Invalid external score thresholds')
        if self.news_ttl_ms>604800000 or self.social_ttl_ms>86400000:raise ValueError('External TTL exceeds declared freshness bound')
        if self.sample_max_age_ms>10000 or self.context_max_age_ms>120000:raise ValueError('Cannot relax source freshness limits')

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,separators=(',',':')).encode()).hexdigest()
