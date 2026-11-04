"""Operator-owned feature scheduling only; never part of formula/config signatures."""
import json
import math
from pathlib import Path
import tempfile
from . import data_policy

CONFIG_FILE=Path(__file__).with_name('feature_runtime.json')
DEFAULTS=dict(time_budget=1.,max_bars=1000,priority=None)


def validate(config):
    if not isinstance(config,dict) or set(config)-set(DEFAULTS):raise ValueError('Unknown feature runtime setting')
    result={**DEFAULTS,**config};seconds=result['time_budget'];bars=result['max_bars'];priority=result['priority']
    if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or not .25<=seconds<=10:raise ValueError('Feature time budget must be 0.25–10 seconds')
    if type(bars) is not int or not 200<=bars<=10000:raise ValueError('Feature row budget must be 200–10000')
    if priority is not None and (not isinstance(priority,dict) or set(priority)!={'symbol','timeframe'} or not isinstance(priority['symbol'],str) or not priority['symbol'].isalnum() or priority['timeframe'] not in data_policy.INTERVALS):raise ValueError('Choose a symbol and registered timeframe together')
    return result


def read():
    return validate(json.loads(CONFIG_FILE.read_text())) if CONFIG_FILE.is_file() else DEFAULTS.copy()


def write(config):
    result=validate(config)
    with data_policy.locked():
        with tempfile.NamedTemporaryFile(mode='w',dir=CONFIG_FILE.parent,delete=False) as stream:
            temp=Path(stream.name)
            try:json.dump(result,stream,indent=2)
            except BaseException:temp.unlink(missing_ok=True);raise
        temp.replace(CONFIG_FILE)
    return result
