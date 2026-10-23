"""Versioned JSON checkpoints. Never pickle or execute stored feature state."""
import json
import math
from collections import deque
from .engine import Engine
from .context import MANIFEST

VERSION=3
ATTRIBUTES=('index','last_time','last_client','daily_bars','day','vwap_sum','vwap_volume','volumes','last_regime','persistent','histories','technical')

def encode(value):
    if isinstance(value,float) and math.isnan(value):return {'__pine_na__':1}
    if isinstance(value,dict):return {k:encode(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,deque)):return [encode(v) for v in value]
    return value

def decode(value):
    if value=={'__pine_na__':1}:return float('nan')
    return value

def dump(engine,epoch):
    context=engine.context
    return json.dumps(encode({'version':VERSION,'source':MANIFEST['source_sha256'],'epoch':list(epoch),'parameters':context.parameters,
                              'components':pack_sources(getattr(engine,'component_sources',None)),
                              'state':{key:getattr(context,key) for key in ATTRIBUTES}}),allow_nan=False,separators=(',',':'))

def restore(symbol,interval,text,epoch):
    saved=json.loads(text,object_hook=decode)
    if saved['version']!=VERSION or saved['epoch']!=list(epoch):return None
    from .components import baseline_sources
    engine=Engine(symbol,interval,parameters=saved['parameters'])
    sources=unpack_sources(saved.get('components'))
    if sources is None:
        baseline,source=baseline_sources()
        sources=baseline if saved['source']==source else {}
    engine.component_sources=sources
    for key,value in saved['state'].items():setattr(engine.context,key,value)
    engine.context.histories={key:deque(value,maxlen=engine.context.capacity) for key,value in engine.context.histories.items()}
    return engine



def pack_sources(sources):
    if sources is None:return None
    from .components import baseline_sources,digest
    baseline,_=baseline_sources()
    return {'baseline':digest(baseline),'overrides':{k:v for k,v in sources.items() if baseline.get(k)!=v},'removed':list(baseline.keys()-sources.keys())}


def unpack_sources(sources):
    if sources is None or 'baseline' not in sources:return sources
    from .components import baseline_sources,digest
    baseline,_=baseline_sources()
    if sources['baseline']!=digest(baseline):return {}
    result={**baseline,**sources['overrides']}
    for key in sources['removed']:result.pop(key,None)
    return result
