"""Validated immutable paper account allocation, stored outside app configuration."""
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
import re


def money(value):
    try: result=Decimal(str(value))
    except (InvalidOperation,ValueError):raise ValueError('Use a finite decimal amount') from None
    if not result.is_finite():raise ValueError('Use a finite decimal amount')
    return result


@dataclass(frozen=True)
class Config:
    name: str
    symbol: str
    interval: str
    instance_id: str
    initial_capital: str
    capital_cap: str
    stop_loss_pct: str
    take_profit_pct: str
    fee_bps: str = '10'
    slippage_bps: str = '5'
    max_signal_age_seconds: int = 180
    mode: str = 'paper'
    strategy_source: str = 'selected'
    strategy_fingerprint: str = ''

    def __post_init__(self):
        if self.strategy_source not in ('selected','current'):raise ValueError('Choose current or selected strategy source')
        if self.strategy_source=='current' and self.instance_id!='current':raise ValueError('Use current as the identity for the existing strategy')
        if self.mode!='paper':raise ValueError('Only paper mode is implemented; live orders are disabled')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',self.name):raise ValueError('Use a short account name: letters, numbers, _ or -')
        if not re.fullmatch(r'[A-Z0-9]{2,30}USDT',self.symbol):raise ValueError('Choose a USDT Spot pair')
        if self.interval not in ('1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h','1d','3d','1w','1M'):raise ValueError('Unsupported timeframe')
        if not isinstance(self.instance_id,str) or not self.instance_id:raise ValueError('A selected strategy instance is required')
        if not 0<money(self.initial_capital)<=money(self.capital_cap):raise ValueError('Capital must be positive and no greater than its cap')
        if not 0<money(self.stop_loss_pct)<100 or not 0<money(self.take_profit_pct)<=1000:raise ValueError('Configure positive stop-loss (<100%) and take-profit percentages')
        for value in (self.fee_bps,self.slippage_bps):
            if not 0<=money(value)<=100:raise ValueError('Fee and slippage must be within 0..100 basis points')
        if type(self.max_signal_age_seconds) is not int or not 1<=self.max_signal_age_seconds<=3600:raise ValueError('Signal age must be 1..3600 seconds')

    def data(self):return asdict(self)
