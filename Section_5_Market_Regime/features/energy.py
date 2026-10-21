"""Section 5: energy; Pine lines 5761–5778."""
from Section_4_Features.execution import runtime as rt

def update(e):
    # Pine 5774
    e['atrExpanding'] = rt.binary('>', e['atrMARatio'], 1.2)
    # Pine 5775
    e['atrContracting'] = rt.binary('<', e['atrMARatio'], 0.8)
    # Pine 5777
    e['energyState'] = ('ENERGY_EXPANDING' if rt.truth((rt.truth(e['atrExpanding']) and rt.truth(rt.binary('>=', e['adx'], 35)))) else ('ENERGY_CONTRACTING' if rt.truth(e['atrContracting']) else ('ENERGY_NORMAL' if rt.truth(rt.binary('>=', e['adx'], 25)) else 'ENERGY_DEAD')))
