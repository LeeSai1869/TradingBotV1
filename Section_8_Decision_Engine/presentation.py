"""Read-only chart projection using the one active decision rule."""
import time
from .rules import di_turning_point as rule
from .sequence import alternate


def annotate(bars,last_signal=None):
    previous=[];last_close=None;now=int(time.time()*1000)
    for bar in bars:
        client=bar['client'];features=bar.get('features') or {}
        if last_close is not None and last_close+1!=bar['open_time']:previous=[]
        last_close=client['close_time']
        if client['close_time']>=now or features.get('formula_version')!=3:
            previous=[];bar['momentum']=None;continue
        current={key:features.get(key) for key in rule.FIELDS}
        current['close']=client['close']
        decision,last_signal=alternate(rule.evaluate(previous,current),last_signal)
        bar['momentum']={**decision,'rule':rule.RULE_ID}
        previous.append(current);previous=previous[-2:]
    return bars
