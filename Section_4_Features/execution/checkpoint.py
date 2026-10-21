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
                              'state':{key:getattr(context,key) for key in ATTRIBUTES}}),allow_nan=False,separators=(',',':'))

def restore(symbol,interval,text,epoch):
    saved=json.loads(text,object_hook=decode)
    if saved['version']!=VERSION or saved['source']!=MANIFEST['source_sha256'] or saved['epoch']!=list(epoch):return None
    engine=Engine(symbol,interval)
    if saved['parameters']!=engine.context.parameters:return None
    for key,value in saved['state'].items():setattr(engine.context,key,value)
    engine.context.histories={key:deque(value,maxlen=engine.context.capacity) for key,value in engine.context.histories.items()}
    return engine
