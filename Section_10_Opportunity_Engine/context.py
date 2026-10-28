"""Immutable price-point scenario lifecycle. This module never emits decisions.

The caller supplies an anchor selected elsewhere. Both directions are evaluated
independently at that point; later prices can mark hits, never move the levels.
"""
import copy


def anchor(packet,*,side,open_time,confidence=None,previous=None):
    plan=packet.get(side.lower())
    if side not in ('BUY','SELL') or not plan:return None
    return dict(side=side,open_time=open_time,entry=packet['entry'],plan=copy.deepcopy(plan),
        confidence=copy.deepcopy(confidence),opportunity=copy.deepcopy(packet),costs=packet['costs'],state='active',targets_touched=[],previous=previous)


def advance(context,bar):
    if context is None or context['state']!='active':return context
    if bar['open_time']<=context['open_time']:return context
    state=copy.deepcopy(context);plan=state['plan'];client=bar['client'];buy=state['side']=='BUY'
    stopped=client['low']<=plan['invalidation'] if buy else client['high']>=plan['invalidation']
    touches=[i+1 for i,t in enumerate(plan['targets']) if (client['high']>=t['price'] if buy else client['low']<=t['price'])]
    new=[i for i in touches if i not in state['targets_touched']]
    if stopped:
        state['state']='ambiguous intrabar' if new else 'invalidated'
        state['ended_at']=bar['open_time']
        # OHLC cannot tell whether the target or invalidation happened first.
        state['same_bar_possible_targets']=new
    else:
        state['targets_touched']=sorted(set(state['targets_touched']+touches))
        if plan['targets'] and len(state['targets_touched'])==len(plan['targets']):
            state['state']='all known targets touched';state['ended_at']=bar['open_time']
    return state
