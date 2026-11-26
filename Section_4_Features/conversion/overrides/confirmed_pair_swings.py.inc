
def update_confirmed_pair_swings(e):
    """Approved confirmed-pair + two-close rule after legacy first-pair bootstrap."""
    if 'swingPivotRulesState' not in e.persistent:
        e.initialize('swingPivotRulesState', None)
    state=e['swingPivotRulesState']
    if state is None:
        direction=e['candidatePivot']
        pair=([e['swingHighPriceArray'][-1],e['swingLowPriceArray'][-1]] if direction==1 else
              [e['swingLowPriceArray'][-1],e['swingHighPriceArray'][-1]])
        price=e['candidatePivotHighPrice'] if direction==1 else e['candidatePivotLowPrice']
        origin=e['candidatePivotHighTime'] if direction==1 else e['candidatePivotLowTime']
        bar=e['candidatePivotHighBar'] if direction==1 else e['candidatePivotLowBar']
        state=pivot_rules.seed(pair,direction,price,origin,bar,e.previous('c',1),e.last_client['close_time'] if e.last_client else None)
    old_high=e['candidatePivotHighBar'];old_low=e['candidatePivotLowBar']
    event=pivot_rules.advance(state,e.current_client,e['bar_index']) if e['barstate.isconfirmed'] else None
    e['swingPivotRulesState']=state
    candidate=state['candidate']
    if event:
        kind='high' if event['type']=='PIVOT_HIGH' else 'low'
        if kind=='high':
            rt.arr_push(e['swingHighPriceArray'], event['price'])
            rt.arr_push(e['swingHighBarArray'], event['origin_bar'])
            rt.arr_push(e['swingHighTimeArray'], event['origin_time'])
            e['candidatePivotHighPrice']=event['price'];e['candidatePivotHighBar']=event['origin_bar'];e['candidatePivotHighTime']=event['origin_time']
            e['lastConfirmedPivotType']=1
        else:
            rt.arr_push(e['swingLowPriceArray'], event['price'])
            rt.arr_push(e['swingLowBarArray'], event['origin_bar'])
            rt.arr_push(e['swingLowTimeArray'], event['origin_time'])
            e['candidatePivotLowPrice']=event['price'];e['candidatePivotLowBar']=event['origin_bar'];e['candidatePivotLowTime']=event['origin_time']
            e['lastConfirmedPivotType']=-1
        e['structureEventState'],e['structureEventBuffer']=event_export.pivot(e['structureEventState'],e['structureEventBuffer'],e.symbol,e.timeframe,e.current_client,
            kind,event['price'],event['origin_bar'],event['origin_time'])
        if e['currentActivePivotTypeArray']:
            rt.arr_push(e['prevActivePivotTypeArray'], e['currentActivePivotTypeArray'][-1])
        rt.arr_push(e['currentActivePivotTypeArray'], e['lastConfirmedPivotType'])
    e['candidatePivot']=state['direction']
    if state['direction']==1:
        e['candidatePivotHighPrice']=candidate['price'];e['candidatePivotHighBar']=candidate['bar'];e['candidatePivotHighTime']=candidate['origin']
    else:
        e['candidatePivotLowPrice']=candidate['price'];e['candidatePivotLowBar']=candidate['bar'];e['candidatePivotLowTime']=candidate['origin']
    e['prevCandidatePivotHighBar']=old_high if old_high!=e['candidatePivotHighBar'] else rt.NA
    e['prevCandidatePivotLowBar']=old_low if old_low!=e['candidatePivotLowBar'] else rt.NA
    e['swingHighCount']=len(e['swingHighPriceArray']);e['swingLowCount']=len(e['swingLowPriceArray'])
    e['latestConfirmedPivotLow']=e['swingLowPriceArray'][-1] if state['direction']==1 else rt.NA
    e['latestConfirmedPivotHigh']=e['swingHighPriceArray'][-1] if state['direction']==-1 else rt.NA
    threshold,span=pivot_rules.level(state)
    e['pivotHighConfirmationPrice']=threshold if state['direction']==1 else rt.NA
    e['pivotLowConfirmationPrice']=threshold if state['direction']==-1 else rt.NA
    e['swingDistance']=span;e['validationDistance']=span*.25
    e['currentSwingDirection']='SWING_UP' if state['direction']==1 else 'SWING_DOWN'
    e['swingTransition']=1 if state['streak']>0 else 0
