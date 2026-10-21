"""Runs the individual feature functions in their explicit Pine dependency order."""
import importlib
from .context import Context,MANIFEST
from . import runtime as rt
from . import _memory
from .contract import canonical

MODULES=tuple(importlib.import_module(name if '.' in name else '.'+name,__package__) for name in MANIFEST['modules'])

class Engine:
    def __init__(self,symbol,timeframe,parameters=None):self.context=Context(symbol,timeframe,parameters)
    def step(self,client,*,is_confirmed=True,is_realtime=False,daily_bars=None,is_new=True):
        e=self.context;e.begin(client,is_confirmed,is_realtime,is_new);e.external_daily=daily_bars;_memory.update(e)
        for module in MODULES:
            try:module.update(e)
            except Exception as error:raise RuntimeError(f'{module.__name__} at bar {e.index}, time {client["open_time"]}: {error}') from error
        # Named export avoids the supplied constructor's duplicate/misaligned slots.
        aliases={'vwap':'vwapValue','nearestSupport':'nearestSupportPrice','nearestResistance':'nearestResistancePrice','previousDayHigh':'prevDayHigh','previousDayLow':'prevDayLow'}
        values={name:e[aliases.get(name,name)] for name,_ in MANIFEST['contract']}
        values.update({key:e[key] for key in ('controlState','energyState','regimeState','fatigueState','trendState','transitionState')})
        result=canonical(values,e);e.finish();return rt.clean(result)
