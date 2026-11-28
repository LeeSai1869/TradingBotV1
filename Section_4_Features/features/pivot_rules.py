"""Closed-candle current-move swing rules; independent of structure/BOS state."""
from decimal import Decimal

VERSION=2
RULE_NAME="current-move-v2"
EXPORTS={'pivot_rules_version':'string','pivot_reference_range':'float','pivot_confirmation_level':'float','pivot_reverse_closes':'float'}


def level(state):
    anchor=Decimal(str(state['pair'][-1]));candidate=Decimal(str(state['candidate']['price']))
    span=abs(candidate-anchor)
    return float(candidate-state['direction']*Decimal('.25')*span),float(span)


def seed(pair,direction,price,origin,bar,previous_close,last_close_time):
    if direction not in (-1,1) or pair[0]==pair[1]:raise ValueError('A confirmed pair and an active opposite candidate are required')
    return dict(version=VERSION,pair=list(pair),direction=direction,candidate=dict(price=price,origin=origin,bar=bar),
                streak=0,tail=[],previous_close=previous_close,last_close_time=last_close_time)


def advance(state,client,index):
    """Mutate only caller-owned JSON state. Return at most one confirmed pivot."""
    if state.get('version')!=VERSION:raise ValueError('Pivot checkpoint requires current-move historical repair')
    direction=state['direction'];candidate=state['candidate'];stamp=client['open_time']
    if state['last_close_time'] is not None and stamp<=state['last_close_time']:raise ValueError('Pivot candles must advance chronologically')
    continuous=state['last_close_time'] is not None and stamp==state['last_close_time']+1
    point=dict(origin=stamp,bar=index,high=client['high'],low=client['low'])
    extreme=point['high' if direction==1 else 'low']
    extended=extreme>candidate['price'] if direction==1 else extreme<candidate['price']
    event=None
    if extended:
        state['candidate']=dict(price=extreme,origin=stamp,bar=index);state['streak']=0;state['tail']=[]
    else:
        if stamp>candidate['origin']:state['tail'].append(point)
        reverse=(client['close']<state['previous_close'] if direction==1 else client['close']>state['previous_close'])
        state['streak']=state['streak']+1 if continuous and reverse and stamp>candidate['origin'] else 0
        threshold,span=level(state)
        crossed=client['close']<=threshold if direction==1 else client['close']>=threshold
        if span>0 and crossed and state['streak']>=2 and stamp>candidate['origin']:
            event=dict(type='PIVOT_HIGH' if direction==1 else 'PIVOT_LOW',price=candidate['price'],origin_time=candidate['origin'],origin_bar=candidate['bar'],
                confirmation_time=stamp,known_time=client['close_time']+1,reference_range=span,threshold=threshold,reverse_closes=state['streak'])
            field='low' if direction==1 else 'high'
            opposite=(min if direction==1 else max)(state['tail'],key=lambda p:p[field])
            state['pair']=[state['pair'][-1],candidate['price']];state['direction']=-direction
            state['candidate']=dict(price=opposite[field],origin=opposite['origin'],bar=opposite['bar'])
            state['tail']=[p for p in state['tail'] if p['origin']>opposite['origin']];state['streak']=0
    state['previous_close']=client['close'];state['last_close_time']=client['close_time']
    return event
