"""Section 5: trend_state; Pine lines 5834–5870."""
from Section_4_Features.individual import runtime as rt

def update(e):
    # Pine 5848
    e['prevDIStrength'] = rt.math_abs(rt.binary('-', e['prevDIPlus'], e['prevDIMinus']))
    # Pine 5849
    e['trendStrengthIncreasing'] = (rt.truth(rt.binary('>', e['adx'], e['prevADX'])) and rt.truth(rt.binary('>', e['diStrength'], e['prevDIStrength'])))
    # Pine 5850
    e['trendStrengthDecreasing'] = (rt.truth(rt.binary('<', e['adx'], e['prevADX'])) and rt.truth(rt.binary('<', e['diStrength'], e['prevDIStrength'])))
    # Pine 5851
    e['trendState'] = e['TREND_NONE']
    # Pine 5853
    if rt.truth((rt.truth(e['emaBullStructure']) or rt.truth(e['emaBearStructure']))):
        # Pine 5854
        if rt.truth(e['trendStrengthIncreasing']):
            # Pine 5855
            e['trendState'] = e['TREND_FRESH']
        # Pine 5857
        elif rt.truth(e['trendStrengthDecreasing']):
            # Pine 5858
            e['trendState'] = e['TREND_WEAK']
        # Pine 5860
        else:
            # Pine 5861
            e['trendState'] = e['TREND_MATURE']
