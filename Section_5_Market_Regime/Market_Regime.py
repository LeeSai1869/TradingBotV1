"""Section 5: compose six individual regime features with pair-scoped memory."""
from dataclasses import dataclass
from Section_1_Global_Core.Data_Contracts_Legacy import market_definitions as definitions
from Section_4_Features.execution.context import Context,MANIFEST
from Section_4_Features.execution.contract import snake,REGIMES
from .features import control,energy,regime,fatigue,trend_state,transition


@dataclass
class MarketRegime:
    control_state:str=definitions.CONTROL_NONE
    energy_state:str=definitions.ENERGY_DEAD
    regime_state:str=definitions.REGIME_RANGE
    fatigue_state:str=definitions.FATIGUE_NONE
    trend_state:str=definitions.TREND_NONE
    transition_state:str=definitions.TRANSITION_NONE

_LAST={}


def calculate_market_regime(feature_packet,*,last_regime=None,commit=True):
    if feature_packet is None or not feature_packet.valid:return MarketRegime()
    values=feature_packet.features or {}
    # Streaming Section 4/5 already computed these against its checkpoint.
    if all(snake(key) in values for key in REGIMES):return MarketRegime(**{snake(key):values[snake(key)] for key in REGIMES})
    symbol=values.get('symbol','UNKNOWN');tf=feature_packet.tf;key=(symbol,tf)
    context=Context(symbol,tf)
    for name,_ in MANIFEST['contract']:context.values[name]=values.get(snake(name),float('nan'))
    context.values['lastRegime']=last_regime if last_regime is not None else _LAST.get(key,'UNKNOWN')
    for module in (control,energy,regime,fatigue,trend_state,transition):module.update(context)
    result=MarketRegime(**{snake(name):context[name] for name in REGIMES})
    if commit:_LAST[key]=result.regime_state
    return result
