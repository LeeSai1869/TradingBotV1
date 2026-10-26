"""Runs the individual feature functions in their explicit Pine dependency order."""
import importlib
from .context import Context,MANIFEST
from . import runtime as rt
from . import memory,fast
from .contract import canonical

STEPS=tuple((importlib.import_module(step['module'] if '.' in step['module'] else 'Section_4_Features.features.'+step['module'],__package__),step['function']) for step in MANIFEST['steps'])

EXTRA_STEP={'module':'Section_4_Features.execution.zone_lifecycle','function':'update'}
STEPS=(*STEPS,(importlib.import_module(EXTRA_STEP['module']),EXTRA_STEP['function']))
EXTRA_FIELDS=('obZoneEvents','srZoneEvents','instSupportZoneLow','instSupportZoneHigh','instResistanceZoneLow','instResistanceZoneHigh')

class Engine:
    def __init__(self,symbol,timeframe,parameters=None):
        self.context=Context(symbol,timeframe,parameters)
        from .components import catalog
        self.component_sources=catalog().source
    def step(self,client,*,is_confirmed=True,is_realtime=False,daily_bars=None,is_new=True):
        e=self.context;e.begin(client,is_confirmed,is_realtime,is_new);e.external_daily=daily_bars;memory.update(e)
        for module,function in STEPS:
            try:fast.resolve(module,function)(e)
            except Exception as error:raise RuntimeError(f'{module.__name__} at bar {e.index}, time {client["open_time"]}: {error}') from error
        # Named export avoids the supplied constructor's duplicate/misaligned slots.
        aliases={'vwap':'vwapValue','nearestSupport':'nearestSupportPrice','nearestResistance':'nearestResistancePrice','previousDayHigh':'prevDayHigh','previousDayLow':'prevDayLow'}
        values={name:e[aliases.get(name,name)] for name,_ in MANIFEST['contract']}
        values.update({key:e[key] for key in ('controlState','energyState','regimeState','fatigueState','trendState','transitionState')})
        result=canonical(values,e)
        from .contract import snake
        result.update({snake(name):e[name] for name in EXTRA_FIELDS})
        e.finish();return rt.clean(result)
