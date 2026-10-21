"""Section 5: control; Pine lines 5741–5760."""
from Section_4_Features.execution import runtime as rt

def update(e):
    # Pine 5754
    e['diDirection'] = rt.binary('-', e['diPlus'], e['diMinus'])
    # Pine 5755
    e['diStrength'] = rt.math_abs(e['diDirection'])
    # Pine 5757
    e['controlState'] = ('CONTROL_BULL' if rt.truth(rt.binary('>', e['diDirection'], 10)) else ('CONTROL_BEAR' if rt.truth(rt.binary('<', e['diDirection'], rt.neg(10))) else ('CONTROL_NONE' if rt.truth(rt.binary('<', e['diStrength'], 5)) else 'CONTROL_BALANCED')))
