"""Section 5: regime; Pine lines 5779–5819."""
from Section_4_Features.individual import runtime as rt

def update(e):
    # Pine 5799
    e['bullTrend'] = (rt.truth((rt.truth((rt.truth(e['emaBullStructure']) and rt.truth(e['priceAboveEMA50']))) and rt.truth(e['priceAboveEMA200']))) and rt.truth(e['priceAboveVWAP']))
    # Pine 5800
    e['bearTrend'] = (rt.truth((rt.truth((rt.truth(e['emaBearStructure']) and rt.truth(e['priceBelowEMA50']))) and rt.truth(e['priceBelowEMA200']))) and rt.truth(e['priceBelowVWAP']))
    # Pine 5801
    e['regimeState'] = 'REGIME_RANGE'
    # Pine 5803
    if rt.truth(e['bullTrend']):
        # Pine 5804
        e['regimeState'] = ('REGIME_BULL_EXPANSION' if rt.truth(e['atrExpanding']) else 'REGIME_BULL_TREND')
    # Pine 5806
    elif rt.truth(e['bearTrend']):
        # Pine 5807
        e['regimeState'] = ('REGIME_BEAR_EXPANSION' if rt.truth(e['atrExpanding']) else 'REGIME_BEAR_TREND')
    # Pine 5809
    elif rt.truth(e['atrContracting']):
        # Pine 5810
        e['regimeState'] = 'REGIME_COMPRESSION'
    # Pine 5812
    else:
        # Pine 5813
        e['regimeState'] = 'REGIME_RANGE'
