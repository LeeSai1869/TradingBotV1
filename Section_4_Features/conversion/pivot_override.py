"""Reviewed Python override for the approved post-bootstrap pivot specification.

The archived Pine reference retains the original rule. Regeneration must retain
this explicit override until a separately tested Pine implementation is ported.
"""
from pathlib import Path
import re


def apply(code):
    if 'def update_confirmed_pair_swings' in code:return code
    line='from ..execution import runtime as rt\n'
    if 'from . import structure_events as event_export' not in code:
        code=code.replace(line,line+'from . import structure_events as event_export\n')
    if 'from . import pivot_rules' not in code:code=code.replace(line,line+'from . import pivot_rules\n')
    if "e.initialize('structureEventState'" not in code:
        code=code.replace('def update(e):\n',"def update(e):\n    if 'structureEventState' not in e.persistent:\n        e.initialize('structureEventState', event_export.new_state())\n    e['structureEventBuffer'] = []\n",1)
    a=code.index('    # Pine 2788');b=code.index('    # Pine 2888',a)
    legacy=(Path(__file__).with_name('overrides')/'bootstrap_swings.py.inc').read_text()
    code=code[:a]+"    if 'swingPivotRulesState' not in e.persistent:\n        e.initialize('swingPivotRulesState', None)\n    # First-pair bootstrap is retained; subsequent pivots use the approved rules.\n    if not e['swingHighPriceArray'] or not e['swingLowPriceArray'] or e['candidatePivot']==0:\n"+''.join('    '+line+'\n' for line in legacy.splitlines())+"    else:\n        update_confirmed_pair_swings(e)\n    state=e['swingPivotRulesState']\n    e['pivotRulesVersion']=pivot_rules.RULE_NAME if state else 'bootstrap'\n    e['pivotReferenceRange']=pivot_rules.level(state)[1] if state else rt.NA\n    e['pivotConfirmationLevel']=pivot_rules.level(state)[0] if state else rt.NA\n    e['pivotReverseCloses']=state['streak'] if state else 0\n"+code[b:]
    a=code.index('    # Pine 3365');head,tail=code[:a],code[a:]
    for name in ('candidatePivotHighPrice','candidatePivotHighBar','candidatePivotHighTime','candidatePivotLowPrice','candidatePivotLowBar','candidatePivotLowTime','candidatePivot','swingTransition','lastConfirmedPivotType','prevCandidatePivotHighBar','prevCandidatePivotLowBar','pivotHighConfirmationPrice','pivotLowConfirmationPrice'):
        tail=re.sub(r"        e\['"+name+r"'\] = [^\n]+",'        pass  # Swing tracking survives structure/BOS resets.',tail)
    return head+tail+(Path(__file__).with_name('overrides')/'confirmed_pair_swings.py.inc').read_text()
