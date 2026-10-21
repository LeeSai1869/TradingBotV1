"""Adx. Generated main-feature implementation.
Stages execute in manifest dependency order; see individual/README.md."""
from . import runtime as rt

def update_dmi(e):
    # Pine 977
    e['diPlus'], e['diMinus'], e['adx'] = e.ta('dmi', '977', e['adxLen'], e['adxLen'])

def calculate_dmi(state,client,length,smoothing):
    from .atr import true_range
    length=int(length)
    high,low,close=(client[key] for key in ('high','low','close'))
    previous=state.get('previous')
    atr=rt.rma(state,'atr',true_range(high,low,close,previous,False),length)
    up=high-previous[0] if previous else rt.NA
    down=previous[1]-low if previous else rt.NA
    plus=rt.rma(state,'plus',rt.NA if not previous else up if up>down and up>0 else 0.,length)
    minus=rt.rma(state,'minus',rt.NA if not previous else down if down>up and down>0 else 0.,length)
    dp=rt.binary('/',100*plus,atr);dm=rt.binary('/',100*minus,atr)
    if rt.is_na(dp):dp=state.get('dp',rt.NA)
    if rt.is_na(dm):dm=state.get('dm',rt.NA)
    state.update(dp=dp,dm=dm,previous=[high,low,close])
    return dp,dm,calculate(state,dp,dm,int(smoothing))

def update_adx(e):
    # Pine 979
    e['prevADX'] = e.previous('adx', 1)

def calculate(state,plus,minus,length):
    total=plus+minus
    dx=rt.binary('/',abs(plus-minus),total if total!=0 else 1)
    return 100*rt.rma(state,'adx',dx,length)

def update_di_metrics(e):
    # Pine 980
    e['prevDIPlus'] = e.previous('diPlus', 1)
    # Pine 981
    e['prevDIMinus'] = e.previous('diMinus', 1)
    # Pine 982
    e['diDirection'] = rt.binary('-', e['diPlus'], e['diMinus'])
    # Pine 983
    e['diSpread'] = rt.math_abs(e['diDirection'])
    # Pine 984
    e['diDominance'] = (rt.binary('/', rt.math_abs(rt.binary('-', e['diPlus'], e['diMinus'])), rt.binary('+', e['diPlus'], e['diMinus'])) if rt.truth(rt.binary('>', rt.binary('+', e['diPlus'], e['diMinus']), 0)) else 0)

def update(e):
    update_dmi(e)
    update_adx(e)
    update_di_metrics(e)
