"""Trigger/Activate rules for the existing offline closed-candle replay."""

def project(node,stage):
    """Apply the user's logical grouping independently within each marked stage."""
    for key in ('all','any'):
        if key in node:
            children=[child for child in (project(n,stage) for n in node[key]) if child is not None]
            return {key:children} if children else None
    if 'not' in node:
        child=project(node['not'],stage)
        return {'not':child} if child is not None else None
    return {k:v for k,v in node.items() if k!='stage'} if node.get('stage','activate')==stage else None


def match(memory,branch,program,index,armed,missing,*,allow_arm=False):
    """Latch a matching Trigger group; Activate on the selected same-or-later closed-candle timing.

    A trigger has no time expiry. It is scoped to one branch and one BUY/SELL
    cycle. The replay clears setups at a side change or a missing price gap.
    Unmarked legacy conditions remain ordinary close-time activation rules.
    """
    trigger,activation=program
    if trigger is None:return memory.evaluate(activation,index,missing)
    setup=armed.get(branch['id'])
    if setup is None:
        if not allow_arm:return False
        result=memory.evaluate(trigger,index,missing)
        if result is not True:return result
        from .strategy_analyzer import expression_operands
        row=memory.rows[index]
        setup=dict(index=index,candle_open_time=row['open_time'],known_time=row['close_time']+1,
                   branch_id=branch['id'],side=branch['side'],
                   inputs={f'{field}@lag{lag}':dict(zip(('value','missing_reason'),memory.value(index,field,lag))) for field,lag in expression_operands(trigger)})
        armed[branch['id']]=setup
    if index<setup['index'] or index==setup['index'] and branch.get('activation_timing','same_or_later')=='later':return False
    return memory.evaluate(activation,index,missing)


def explain(memory,node,index,path='Activate'):
    """Record each activation predicate without changing its grouped truth value."""
    if 'all' in node or 'any' in node:
        key='all' if 'all' in node else 'any'
        return [item for j,child in enumerate(node[key]) for item in explain(memory,child,index,f'{path}/{key}[{j+1}]')]
    if 'not' in node:return explain(memory,node['not'],index,path+'/not')
    value,missing=memory.value(index,node['field'],node.get('lag',0))
    other,other_missing=memory.value(index,node['other_field'],node.get('other_lag',0)) if 'other_field' in node else (node.get('value'),None)
    result=memory.evaluate(node,index,set())
    return [dict(path=path,condition=node,result='PASS' if result is True else 'FAIL' if result is False else 'UNKNOWN',
                 value=value,missing_reason=missing,other_value=other,other_missing_reason=other_missing)]
