"""Section 5: transition; Pine lines 5871–5893."""
from Section_4_Features.individual import runtime as rt

def update(e):
    # Pine 5882
    e['transitionState'] = e['TRANSITION_NONE']
    # Pine 5883
    e['regimeChanged'] = (rt.truth((rt.truth(rt.binary('!=', e['lastRegime'], '')) and rt.truth(rt.binary('!=', e['lastRegime'], 'UNKNOWN')))) and rt.truth(rt.binary('!=', e['lastRegime'], e['regimeState'])))
    # Pine 5884
    e['weakeningTrend'] = (rt.truth((rt.truth((rt.truth((rt.truth(rt.binary('==', e['regimeState'], 'REGIME_BULL_TREND')) or rt.truth(rt.binary('==', e['regimeState'], 'REGIME_BEAR_TREND')))) or rt.truth(rt.binary('==', e['regimeState'], 'REGIME_BULL_EXPANSION')))) or rt.truth(rt.binary('==', e['regimeState'], 'REGIME_BEAR_EXPANSION')))) and rt.truth(rt.binary('<', e['adx'], e['prevADX'])))
    # Pine 5885
    e['compressionBuilding'] = (rt.truth(rt.binary('>', e['emaCompression'], 0)) and rt.truth(e['atrContracting']))
    # Pine 5886
    e['activeTransition'] = e['regimeChanged']
    # Pine 5888
    if rt.truth(e['activeTransition']):
        # Pine 5889
        e['transitionState'] = e['TRANSITION_ACTIVE']
    # Pine 5890
    elif rt.truth((rt.truth(e['weakeningTrend']) or rt.truth(e['compressionBuilding']))):
        # Pine 5891
        e['transitionState'] = e['TRANSITION_RISK']
    # Pine 5892
    else:
        # Pine 5893
        e['transitionState'] = e['TRANSITION_NONE']
