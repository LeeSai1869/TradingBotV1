"""Section 5: fatigue; Pine lines 5820–5833."""
from Section_4_Features.execution import runtime as rt

def update(e):
    # Pine 5830
    e['bullFatigue'] = (rt.truth((rt.truth(e['emaBullStructure']) and rt.truth(rt.binary('<', e['diPlus'], e['prevDIPlus'])))) and rt.truth(rt.binary('<', e['adx'], e['prevADX'])))
    # Pine 5831
    e['bearFatigue'] = (rt.truth((rt.truth(e['emaBearStructure']) and rt.truth(rt.binary('<', e['diMinus'], e['prevDIMinus'])))) and rt.truth(rt.binary('<', e['adx'], e['prevADX'])))
    # Pine 5832
    e['fatigueState'] = ('FATIGUE_BULLISH' if rt.truth(e['bullFatigue']) else ('FATIGUE_BEARISH' if rt.truth(e['bearFatigue']) else 'FATIGUE_NONE'))
