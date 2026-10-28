"""Immutable price-point scenario lifecycle. This module never emits decisions.

The caller supplies an anchor selected elsewhere. Both directions are evaluated
independently at that point; later prices can mark hits, never move the levels.
"""
import copy
from Section_1_Global_Core.analysis_packet import number


def anchor(packet,*,side,open_time,confidence=None,previous=None):
    snapshot=copy.deepcopy(packet)
    plan=snapshot.get(side.lower())
    if side not in ('BUY','SELL') or not plan:return None
    area_map=snapshot.get('areas',{'resistance':snapshot.get('buy',{}).get('targets',[]),'support':snapshot.get('sell',{}).get('targets',[])})
    return dict(side=side,open_time=open_time,entry=snapshot['entry'],plan=plan,
        area_map=area_map,area_progress={'resistance':[],'support':[]},next_area={role:1 if areas else None for role,areas in area_map.items()},
        confidence=copy.deepcopy(confidence),opportunity=snapshot,costs=snapshot['costs'],state='active',targets_touched=[],previous=previous)


def advance(context,bar):
    if context is None or context['state']=='coverage unknown':return context
    if bar['open_time']<=context['open_time']:return context
    state=copy.deepcopy(context);plan=state['plan'];client=bar['client'];buy=state['side']=='BUY'
    for role,areas in state.get('area_map',{}).items():
        previous=state.get('area_progress',{}).get(role,[]);progress=[]
        for index,area in enumerate(areas):
            old=previous[index] if index<len(previous) else {}
            touched=client['low']<=area['high'] and client['high']>=area['low']
            beyond=client['close']>area['high'] if role=='resistance' else client['close']<area['low']
            progress.append(dict(touched=old.get('touched',False) or touched,crossed=old.get('crossed',False) or beyond,
                current='beyond' if beyond else 'inside' if area['low']<=client['close']<=area['high'] else 'approaching'))
        state.setdefault('area_progress',{})[role]=progress
        state.setdefault('next_area',{})[role]=next((i+1 for i,p in enumerate(progress) if not p['crossed']),None)
    if state['state']!='active':return state
    stop=plan.get('invalidation')
    stopped=number(stop) and (client['low']<=stop if buy else client['high']>=stop)
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
