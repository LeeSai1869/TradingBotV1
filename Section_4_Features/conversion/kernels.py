"""Native implementations of Pine TA primitives, emitted into their owning features."""
KERNELS={
'ema': '''
def calculate(state,value,length):
    if not rt.is_na(value):
        alpha=2/(length+1)
        state['value']=value if 'value' not in state else alpha*value+(1-alpha)*state['value']
    return state.get('value',rt.NA)
''',
'rsi': '''
def calculate(state,value,length):
    previous=state.get('previous',rt.NA)
    change=rt.binary('-',value,previous)
    gain=rt.rma(state,'gain',max(change,0) if not rt.is_na(change) else rt.NA,int(length))
    loss=rt.rma(state,'loss',max(-change,0) if not rt.is_na(change) else rt.NA,int(length))
    state['previous']=value
    return rt.NA if rt.is_na(gain) or rt.is_na(loss) or gain==loss==0 else 100 if loss==0 else 100-100/(1+gain/loss)
''',
'atr': '''
def true_range(high,low,close,previous,first_bar=True):
    return max(high-low,abs(high-previous[2]),abs(low-previous[2])) if previous else high-low if first_bar else rt.NA

def calculate(state,client,length):
    high,low,close=(client[key] for key in ('high','low','close'))
    value=rt.rma(state,'atr',true_range(high,low,close,state.get('previous')),int(length))
    state['previous']=[high,low,close]
    return value
''',
'dmi': '''
def calculate(state,client,length,smoothing):
    from .volatility import true_range
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
    return dp,dm,calculate_adx(state,dp,dm,int(smoothing))
''',
'adx': '''
def calculate(state,plus,minus,length):
    total=plus+minus
    dx=rt.binary('/',abs(plus-minus),total if total!=0 else 1)
    return 100*rt.rma(state,'adx',dx,length)
''',
'wma': '''
def calculate(values):
    length=len(values)
    return sum((i+1)*value for i,value in enumerate(values))/(length*(length+1)/2)
''',
'vwap': '''
def session_value(context,client,new_day):
    if new_day:context.vwap_sum=context.vwap_volume=0.
    typical=(client['high']+client['low']+client['close'])/3
    context.vwap_sum+=typical*client['volume']
    context.vwap_volume+=client['volume']
    return context.vwap_sum/context.vwap_volume if context.vwap_volume>0 else rt.NA
''',
'volume': '''
def moving_average(context,volume):
    length=int(context.parameters['volumeLookback'])
    context.volumes.append(volume);context.volumes=context.volumes[-length:]
    return sum(context.volumes)/length if len(context.volumes)==length else rt.NA
''',
}
