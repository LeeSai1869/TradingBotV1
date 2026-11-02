"""Momentum-owned causal DI extrema, price anchors and regime context.

Detection never depends on eligibility thresholds. Only this module's new fields
are exported; legacy diSpread/DI signals are never assigned here.
"""
import json
import math

CHANNELS=('di_plus','di_minus','di_signed_spread')
DEFAULTS={
    'diAnchorReversal':2.,'diAnchorConfirmBars':1,'diAnchorConfirmSpacing':1,
    'diAnchorHistory':32,'diAnchorSourceHistory':256,
    'diAnchorRetestATR':.1,'diAnchorRetestAge':1,
    'diAnchorPlusHighMin':30.,'diAnchorPlusHighMax':100.,'diAnchorPlusLowMin':0.,'diAnchorPlusLowMax':30.,
    'diAnchorMinusHighMin':30.,'diAnchorMinusHighMax':100.,'diAnchorMinusLowMin':0.,'diAnchorMinusLowMax':30.,
    'diAnchorSpreadHighMin':0.,'diAnchorSpreadHighMax':100.,'diAnchorSpreadLowMin':-100.,'diAnchorSpreadLowMax':0.,
}
EXPORTS={'di_signed_spread':'float','di_anchor_events':'string','di_anchor_continuous':'bool'}
for channel in CHANNELS:
    EXPORTS[channel+'_peak_phase']='string'
    for kind in ('high','low'):
        root=channel+'_local_'+kind
        EXPORTS.update({root:'float',root+'_bar':'int',root+'_time':'int',root+'_confirmed_time':'int',
            root+'_qualified':'bool',root+'_confirmed_age':'int',root+'_delta':'float',root+'_since_min':'float',root+'_since_max':'float'})
        EXPORTS[channel+'_candidate_'+kind]='float'
for kind in ('high','low'):
    root='di_price_'+kind
    EXPORTS.update({root+'_anchor':'float',root+'_time':'int',root+'_known_time':'int',root+'_age':'int',
                    root+'_broken':'bool',root+'_retest_rejection':'bool',root+'_tolerance':'float',root+'_regime':'string'})
    for channel in CHANNELS:
        EXPORTS.update({channel+'_at_price_'+kind:'float',channel+'_at_price_'+kind+'_confirmation':'float',
            channel+'_from_price_'+kind:'float',channel+'_price_'+kind+'_since_min':'float',channel+'_price_'+kind+'_since_max':'float'})


def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def validate(parameters):
    for key in DEFAULTS:
        value=parameters[key]
        if not finite(value):raise ValueError(key+' must be finite')
        if key in ('diAnchorConfirmBars','diAnchorConfirmSpacing','diAnchorHistory','diAnchorSourceHistory','diAnchorRetestAge'):
            limit=512 if key=='diAnchorSourceHistory' else 128 if key=='diAnchorHistory' else 5000
            if type(value) is not int or not 1<=value<=limit:raise ValueError(key+f' must be an integer in 1..{limit}')
    if parameters['diAnchorSourceHistory']<=max(parameters['diAnchorConfirmBars'],parameters['diAnchorConfirmSpacing']):raise ValueError('DI anchor source history must exceed confirmation delays')
    if not 0<=parameters['diAnchorReversal']<=200:raise ValueError('diAnchorReversal must be in 0..200 DI points')
    if not 0<=parameters['diAnchorRetestATR']<=10:raise ValueError('diAnchorRetestATR must be in 0..10')
    for channel in ('Plus','Minus','Spread'):
        for kind in ('High','Low'):
            low=parameters[f'diAnchor{channel}{kind}Min'];high=parameters[f'diAnchor{channel}{kind}Max']
            if not (-100 if channel=='Spread' else 0)<=low<=high<=100:raise ValueError(f'Invalid {channel} {kind} qualification range')


def new_state():
    return dict(last_time=None,last_close=None,row=None,ready=False,continuous=False,pending=[],history=[],
                channels={name:dict(phase='SEEK_TURN',candidate_high=None,candidate_low=None,high=None,low=None,
                    highs=[],lows=[],last_confirmation=None) for name in CHANNELS},prices=dict(high=None,low=None))


def detect(state,client,index,plus,minus,confirmed,reversal,confirm_bars,spacing,history_limit,source_limit):
    if not confirmed:return state
    opened=client['open_time']
    if state['last_time'] is not None and opened<state['last_time']:raise ValueError('Momentum anchors require chronological candles')
    if opened==state['last_time']:return state
    continuous=state['last_close'] is not None and state['last_close']+1==opened
    if state['last_time'] is not None and not continuous:state=new_state()
    if not finite(plus) or not finite(minus) or plus<0 or minus<0:
        state=new_state();state.update(last_time=opened,last_close=client['close_time']);return state
    if not state['ready']:continuous=False
    values=dict(zip(CHANNELS,(plus,minus,plus-minus)))
    row=dict(bar=index,time=opened,available=client['close_time']+1,close=client['close'],high=client['high'],low=client['low'],values=values,regime=None,structure=None)
    state.update(last_time=opened,last_close=client['close_time'],row=row,ready=True,continuous=continuous,pending=[])
    state['history'].append(row);state['history']=state['history'][-source_limit:]
    for name,value in values.items():
        series=state['channels'][name]
        for kind in ('high','low'):
            anchor=series[kind]
            if anchor:
                anchor['since_min']=min(anchor['since_min'],value);anchor['since_max']=max(anchor['since_max'],value)
        phase=series['phase']
        if phase in ('SEEK_TURN','SEEK_HIGH') and (series['candidate_high'] is None or value>series['candidate_high']['value']):
            series['candidate_high']=dict(value=value,row=row)
        if phase in ('SEEK_TURN','SEEK_LOW') and (series['candidate_low'] is None or value<series['candidate_low']['value']):
            series['candidate_low']=dict(value=value,row=row)
        turn=None
        for kind in ('high','low'):
            if phase not in ('SEEK_TURN','SEEK_HIGH' if kind=='high' else 'SEEK_LOW'):continue
            candidate=series['candidate_'+kind]
            if candidate is None:continue
            amount=candidate['value']-value if kind=='high' else value-candidate['value']
            if amount>0 and amount>=reversal and index-candidate['row']['bar']>=confirm_bars and (series['last_confirmation'] is None or index-series['last_confirmation']>=spacing):
                turn=kind;break
        if turn is None:continue
        candidate=series['candidate_'+turn];origin=candidate['row'];previous=series[turn]
        label=('HH' if candidate['value']>previous['value'] else 'LH' if candidate['value']<previous['value'] else 'EH') if previous and turn=='high' else ('LL' if candidate['value']<previous['value'] else 'HL' if candidate['value']>previous['value'] else 'EL') if previous else None
        event=dict(type='di_'+turn,channel=name,value=candidate['value'],bar=origin['bar'],time=origin['time'],
            confirmed_bar=index,confirmed_time=row['available'],reversal=abs(value-candidate['value']),classification=label,
            price=origin['close'],price_high=origin['high'],price_low=origin['low'],origin_regime=origin['regime'],origin_structure=origin['structure'])
        # Each cycle appends. Previously confirmed records are never replaced.
        series[turn]=dict(event,since_min=value,since_max=value)
        series[turn+'s'].append(dict(event));series[turn+'s']=series[turn+'s'][-history_limit:]
        state['pending'].append(event);series['last_confirmation']=index
        series['phase']='SEEK_LOW' if turn=='high' else 'SEEK_HIGH'
        # Preserve opposite extremes between origin and delayed confirmation.
        next_kind='high' if turn=='low' else 'low';seed=None
        for historical in reversed(state['history']):
            if historical['bar']<origin['bar']:break
            point=historical['values'][name]
            if seed is None or (point>=seed['value'] if next_kind=='high' else point<=seed['value']):seed=dict(value=point,row=historical)
        series['candidate_high']=seed if next_kind=='high' else None
        series['candidate_low']=seed if next_kind=='low' else None
    return state


def qualify(value,channel,kind,parameters):
    prefix={'di_plus':'Plus','di_minus':'Minus','di_signed_spread':'Spread'}[channel]
    return parameters[f'diAnchor{prefix}{kind.title()}Min']<=value<=parameters[f'diAnchor{prefix}{kind.title()}Max']


def link(state,client,index,confirmed,price_high,price_low,atr,regime,structure,parameters):
    """Observe already-confirmed price references only after upstream calculations."""
    output={key:None for key in EXPORTS};output['di_anchor_events']='[]';output['di_anchor_continuous']=False
    if not state['ready']:return state,output
    row=state['row'];values=row['values'];events=[]
    advance=confirmed and row['time']==client['open_time'] and state.get('linked_time')!=row['time']
    if advance:
        row['regime']=regime if isinstance(regime,str) else None;row['structure']=structure if isinstance(structure,str) else None
        for kind,reference in (('high',price_high),('low',price_low)):
            value,bar,time=reference;old=state['prices'][kind]
            valid=all(finite(v) for v in reference) and value>0 and time<=row['time'] and bar<=index
            if valid and (old is None or (old['time'],old['bar'],old['price'])!=(time,bar,value)):
                origin=next((r for r in reversed(state['history']) if r['time']==time),None)
                price=dict(type='price_'+kind,price=value,bar=int(bar),time=int(time),known_bar=index,known_time=row['available'],
                    regime=row['regime'],structure=row['structure'],origin_momentum=origin['values'].copy() if origin else None,
                    momentum=values.copy(),since_min=values.copy(),since_max=values.copy(),
                    tolerance=atr*parameters['diAnchorRetestATR'] if finite(atr) and atr>0 else None)
                state['prices'][kind]=price
                events.append({k:v for k,v in price.items() if k not in ('since_min','since_max')})
            price=state['prices'][kind]
            if price:
                for channel,value in values.items():
                    price['since_min'][channel]=min(price['since_min'][channel],value);price['since_max'][channel]=max(price['since_max'][channel],value)
        for event in state['pending']:
            event={**event,'qualified':qualify(event['value'],event['channel'],event['type'][3:],parameters),
                'confirmation_regime':row['regime'],'confirmation_structure':row['structure'],
                'price_anchors':{k:{field:p[field] for field in ('price','bar','time','known_time')} if p else None for k,p in state['prices'].items()}}
            for kind in ('high','low'):
                price=state['prices'][kind]
                event['price_'+kind+'_origin_lag_bars']=event['bar']-price['bar'] if price else None
            kind=event['type'][3:];series=state['channels'][event['channel']]
            series[kind].update(event)
            series[kind+'s'][-1].update(event)  # Finalize this confirmation, never an older cycle.
            events.append(event)
        state['linked_time']=row['time'];state['pending']=[]
    output['di_signed_spread']=values['di_signed_spread'];output['di_anchor_continuous']=state['continuous']
    for channel,value in values.items():
        series=state['channels'][channel];output[channel+'_peak_phase']=series['phase']
        for kind in ('high','low'):
            candidate=series['candidate_'+kind];output[channel+'_candidate_'+kind]=candidate['value'] if candidate else None
            anchor=series[kind]
            if not anchor:continue
            root=channel+'_local_'+kind;output[root]=anchor['value']
            for suffix,key in (('_bar','bar'),('_time','time'),('_confirmed_time','confirmed_time'),('_since_min','since_min'),('_since_max','since_max')):output[root+suffix]=anchor[key]
            output[root+'_qualified']=qualify(anchor['value'],channel,kind,parameters)
            output[root+'_confirmed_age']=row['bar']-anchor['confirmed_bar'];output[root+'_delta']=value-anchor['value']
    for kind,price in state['prices'].items():
        if price is None:continue
        root='di_price_'+kind;age=row['bar']-price['known_bar'];tolerance=price['tolerance']
        output.update({root+'_anchor':price['price'],root+'_time':price['time'],root+'_known_time':price['known_time'],root+'_age':age,
                       root+'_tolerance':tolerance,root+'_regime':price['regime']})
        if tolerance is not None:
            level=price['price'];mature=age>=parameters['diAnchorRetestAge']
            output[root+'_broken']=row['close']>level+tolerance if kind=='high' else row['close']<level-tolerance
            output[root+'_retest_rejection']=mature and (row['high']>=level-tolerance and row['high']<=level+tolerance and row['close']<level-tolerance if kind=='high' else row['low']<=level+tolerance and row['low']>=level-tolerance and row['close']>level+tolerance)
        for channel,value in values.items():
            output[channel+'_at_price_'+kind]=(price['origin_momentum'] or {}).get(channel)
            output[channel+'_at_price_'+kind+'_confirmation']=price['momentum'][channel]
            output[channel+'_from_price_'+kind]=value-price['momentum'][channel]
            for suffix in ('min','max'):output[channel+'_price_'+kind+'_since_'+suffix]=price['since_'+suffix][channel]
    output['di_anchor_events']=json.dumps(events,separators=(',',':'),allow_nan=False)
    return state,output


def update(e):
    # Final Momentum feature attachment: existing structure/regime outputs are known now.
    e['diAnchorsState'],e['diAnchorValues'] = link(e['diAnchorsState'],e.current_client,e['bar_index'],e['barstate.isconfirmed'],
        (e['nearestSwingHigh'],e['nearestSwingHighBar'],e['nearestSwingHighTime']),
        (e['nearestSwingLow'],e['nearestSwingLowBar'],e['nearestSwingLowTime']),
        e['atr'],e['regimeState'],e['currentStructure'],{
            'diAnchorReversal':e.input('diAnchorReversal',2.0),
            'diAnchorConfirmBars':e.input('diAnchorConfirmBars',1),
            'diAnchorConfirmSpacing':e.input('diAnchorConfirmSpacing',1),
            'diAnchorHistory':e.input('diAnchorHistory',32),
            'diAnchorSourceHistory':e.input('diAnchorSourceHistory',256),
            'diAnchorRetestATR':e.input('diAnchorRetestATR',0.1),
            'diAnchorRetestAge':e.input('diAnchorRetestAge',1),
            'diAnchorPlusHighMin':e.input('diAnchorPlusHighMin',30.0),
            'diAnchorPlusHighMax':e.input('diAnchorPlusHighMax',100.0),
            'diAnchorPlusLowMin':e.input('diAnchorPlusLowMin',0.0),
            'diAnchorPlusLowMax':e.input('diAnchorPlusLowMax',30.0),
            'diAnchorMinusHighMin':e.input('diAnchorMinusHighMin',30.0),
            'diAnchorMinusHighMax':e.input('diAnchorMinusHighMax',100.0),
            'diAnchorMinusLowMin':e.input('diAnchorMinusLowMin',0.0),
            'diAnchorMinusLowMax':e.input('diAnchorMinusLowMax',30.0),
            'diAnchorSpreadHighMin':e.input('diAnchorSpreadHighMin',0.0),
            'diAnchorSpreadHighMax':e.input('diAnchorSpreadHighMax',100.0),
            'diAnchorSpreadLowMin':e.input('diAnchorSpreadLowMin',-100.0),
            'diAnchorSpreadLowMax':e.input('diAnchorSpreadLowMax',0.0),
        })
    e['di_signed_spread'] = e['diAnchorValues']['di_signed_spread']
    e['di_anchor_events'] = e['diAnchorValues']['di_anchor_events']
    e['di_anchor_continuous'] = e['diAnchorValues']['di_anchor_continuous']
    e['di_plus_peak_phase'] = e['diAnchorValues']['di_plus_peak_phase']
    e['di_plus_local_high'] = e['diAnchorValues']['di_plus_local_high']
    e['di_plus_local_high_bar'] = e['diAnchorValues']['di_plus_local_high_bar']
    e['di_plus_local_high_time'] = e['diAnchorValues']['di_plus_local_high_time']
    e['di_plus_local_high_confirmed_time'] = e['diAnchorValues']['di_plus_local_high_confirmed_time']
    e['di_plus_local_high_qualified'] = e['diAnchorValues']['di_plus_local_high_qualified']
    e['di_plus_local_high_confirmed_age'] = e['diAnchorValues']['di_plus_local_high_confirmed_age']
    e['di_plus_local_high_delta'] = e['diAnchorValues']['di_plus_local_high_delta']
    e['di_plus_local_high_since_min'] = e['diAnchorValues']['di_plus_local_high_since_min']
    e['di_plus_local_high_since_max'] = e['diAnchorValues']['di_plus_local_high_since_max']
    e['di_plus_candidate_high'] = e['diAnchorValues']['di_plus_candidate_high']
    e['di_plus_local_low'] = e['diAnchorValues']['di_plus_local_low']
    e['di_plus_local_low_bar'] = e['diAnchorValues']['di_plus_local_low_bar']
    e['di_plus_local_low_time'] = e['diAnchorValues']['di_plus_local_low_time']
    e['di_plus_local_low_confirmed_time'] = e['diAnchorValues']['di_plus_local_low_confirmed_time']
    e['di_plus_local_low_qualified'] = e['diAnchorValues']['di_plus_local_low_qualified']
    e['di_plus_local_low_confirmed_age'] = e['diAnchorValues']['di_plus_local_low_confirmed_age']
    e['di_plus_local_low_delta'] = e['diAnchorValues']['di_plus_local_low_delta']
    e['di_plus_local_low_since_min'] = e['diAnchorValues']['di_plus_local_low_since_min']
    e['di_plus_local_low_since_max'] = e['diAnchorValues']['di_plus_local_low_since_max']
    e['di_plus_candidate_low'] = e['diAnchorValues']['di_plus_candidate_low']
    e['di_minus_peak_phase'] = e['diAnchorValues']['di_minus_peak_phase']
    e['di_minus_local_high'] = e['diAnchorValues']['di_minus_local_high']
    e['di_minus_local_high_bar'] = e['diAnchorValues']['di_minus_local_high_bar']
    e['di_minus_local_high_time'] = e['diAnchorValues']['di_minus_local_high_time']
    e['di_minus_local_high_confirmed_time'] = e['diAnchorValues']['di_minus_local_high_confirmed_time']
    e['di_minus_local_high_qualified'] = e['diAnchorValues']['di_minus_local_high_qualified']
    e['di_minus_local_high_confirmed_age'] = e['diAnchorValues']['di_minus_local_high_confirmed_age']
    e['di_minus_local_high_delta'] = e['diAnchorValues']['di_minus_local_high_delta']
    e['di_minus_local_high_since_min'] = e['diAnchorValues']['di_minus_local_high_since_min']
    e['di_minus_local_high_since_max'] = e['diAnchorValues']['di_minus_local_high_since_max']
    e['di_minus_candidate_high'] = e['diAnchorValues']['di_minus_candidate_high']
    e['di_minus_local_low'] = e['diAnchorValues']['di_minus_local_low']
    e['di_minus_local_low_bar'] = e['diAnchorValues']['di_minus_local_low_bar']
    e['di_minus_local_low_time'] = e['diAnchorValues']['di_minus_local_low_time']
    e['di_minus_local_low_confirmed_time'] = e['diAnchorValues']['di_minus_local_low_confirmed_time']
    e['di_minus_local_low_qualified'] = e['diAnchorValues']['di_minus_local_low_qualified']
    e['di_minus_local_low_confirmed_age'] = e['diAnchorValues']['di_minus_local_low_confirmed_age']
    e['di_minus_local_low_delta'] = e['diAnchorValues']['di_minus_local_low_delta']
    e['di_minus_local_low_since_min'] = e['diAnchorValues']['di_minus_local_low_since_min']
    e['di_minus_local_low_since_max'] = e['diAnchorValues']['di_minus_local_low_since_max']
    e['di_minus_candidate_low'] = e['diAnchorValues']['di_minus_candidate_low']
    e['di_signed_spread_peak_phase'] = e['diAnchorValues']['di_signed_spread_peak_phase']
    e['di_signed_spread_local_high'] = e['diAnchorValues']['di_signed_spread_local_high']
    e['di_signed_spread_local_high_bar'] = e['diAnchorValues']['di_signed_spread_local_high_bar']
    e['di_signed_spread_local_high_time'] = e['diAnchorValues']['di_signed_spread_local_high_time']
    e['di_signed_spread_local_high_confirmed_time'] = e['diAnchorValues']['di_signed_spread_local_high_confirmed_time']
    e['di_signed_spread_local_high_qualified'] = e['diAnchorValues']['di_signed_spread_local_high_qualified']
    e['di_signed_spread_local_high_confirmed_age'] = e['diAnchorValues']['di_signed_spread_local_high_confirmed_age']
    e['di_signed_spread_local_high_delta'] = e['diAnchorValues']['di_signed_spread_local_high_delta']
    e['di_signed_spread_local_high_since_min'] = e['diAnchorValues']['di_signed_spread_local_high_since_min']
    e['di_signed_spread_local_high_since_max'] = e['diAnchorValues']['di_signed_spread_local_high_since_max']
    e['di_signed_spread_candidate_high'] = e['diAnchorValues']['di_signed_spread_candidate_high']
    e['di_signed_spread_local_low'] = e['diAnchorValues']['di_signed_spread_local_low']
    e['di_signed_spread_local_low_bar'] = e['diAnchorValues']['di_signed_spread_local_low_bar']
    e['di_signed_spread_local_low_time'] = e['diAnchorValues']['di_signed_spread_local_low_time']
    e['di_signed_spread_local_low_confirmed_time'] = e['diAnchorValues']['di_signed_spread_local_low_confirmed_time']
    e['di_signed_spread_local_low_qualified'] = e['diAnchorValues']['di_signed_spread_local_low_qualified']
    e['di_signed_spread_local_low_confirmed_age'] = e['diAnchorValues']['di_signed_spread_local_low_confirmed_age']
    e['di_signed_spread_local_low_delta'] = e['diAnchorValues']['di_signed_spread_local_low_delta']
    e['di_signed_spread_local_low_since_min'] = e['diAnchorValues']['di_signed_spread_local_low_since_min']
    e['di_signed_spread_local_low_since_max'] = e['diAnchorValues']['di_signed_spread_local_low_since_max']
    e['di_signed_spread_candidate_low'] = e['diAnchorValues']['di_signed_spread_candidate_low']
    e['di_price_high_anchor'] = e['diAnchorValues']['di_price_high_anchor']
    e['di_price_high_time'] = e['diAnchorValues']['di_price_high_time']
    e['di_price_high_known_time'] = e['diAnchorValues']['di_price_high_known_time']
    e['di_price_high_age'] = e['diAnchorValues']['di_price_high_age']
    e['di_price_high_broken'] = e['diAnchorValues']['di_price_high_broken']
    e['di_price_high_retest_rejection'] = e['diAnchorValues']['di_price_high_retest_rejection']
    e['di_price_high_tolerance'] = e['diAnchorValues']['di_price_high_tolerance']
    e['di_price_high_regime'] = e['diAnchorValues']['di_price_high_regime']
    e['di_plus_at_price_high'] = e['diAnchorValues']['di_plus_at_price_high']
    e['di_plus_at_price_high_confirmation'] = e['diAnchorValues']['di_plus_at_price_high_confirmation']
    e['di_plus_from_price_high'] = e['diAnchorValues']['di_plus_from_price_high']
    e['di_plus_price_high_since_min'] = e['diAnchorValues']['di_plus_price_high_since_min']
    e['di_plus_price_high_since_max'] = e['diAnchorValues']['di_plus_price_high_since_max']
    e['di_minus_at_price_high'] = e['diAnchorValues']['di_minus_at_price_high']
    e['di_minus_at_price_high_confirmation'] = e['diAnchorValues']['di_minus_at_price_high_confirmation']
    e['di_minus_from_price_high'] = e['diAnchorValues']['di_minus_from_price_high']
    e['di_minus_price_high_since_min'] = e['diAnchorValues']['di_minus_price_high_since_min']
    e['di_minus_price_high_since_max'] = e['diAnchorValues']['di_minus_price_high_since_max']
    e['di_signed_spread_at_price_high'] = e['diAnchorValues']['di_signed_spread_at_price_high']
    e['di_signed_spread_at_price_high_confirmation'] = e['diAnchorValues']['di_signed_spread_at_price_high_confirmation']
    e['di_signed_spread_from_price_high'] = e['diAnchorValues']['di_signed_spread_from_price_high']
    e['di_signed_spread_price_high_since_min'] = e['diAnchorValues']['di_signed_spread_price_high_since_min']
    e['di_signed_spread_price_high_since_max'] = e['diAnchorValues']['di_signed_spread_price_high_since_max']
    e['di_price_low_anchor'] = e['diAnchorValues']['di_price_low_anchor']
    e['di_price_low_time'] = e['diAnchorValues']['di_price_low_time']
    e['di_price_low_known_time'] = e['diAnchorValues']['di_price_low_known_time']
    e['di_price_low_age'] = e['diAnchorValues']['di_price_low_age']
    e['di_price_low_broken'] = e['diAnchorValues']['di_price_low_broken']
    e['di_price_low_retest_rejection'] = e['diAnchorValues']['di_price_low_retest_rejection']
    e['di_price_low_tolerance'] = e['diAnchorValues']['di_price_low_tolerance']
    e['di_price_low_regime'] = e['diAnchorValues']['di_price_low_regime']
    e['di_plus_at_price_low'] = e['diAnchorValues']['di_plus_at_price_low']
    e['di_plus_at_price_low_confirmation'] = e['diAnchorValues']['di_plus_at_price_low_confirmation']
    e['di_plus_from_price_low'] = e['diAnchorValues']['di_plus_from_price_low']
    e['di_plus_price_low_since_min'] = e['diAnchorValues']['di_plus_price_low_since_min']
    e['di_plus_price_low_since_max'] = e['diAnchorValues']['di_plus_price_low_since_max']
    e['di_minus_at_price_low'] = e['diAnchorValues']['di_minus_at_price_low']
    e['di_minus_at_price_low_confirmation'] = e['diAnchorValues']['di_minus_at_price_low_confirmation']
    e['di_minus_from_price_low'] = e['diAnchorValues']['di_minus_from_price_low']
    e['di_minus_price_low_since_min'] = e['diAnchorValues']['di_minus_price_low_since_min']
    e['di_minus_price_low_since_max'] = e['diAnchorValues']['di_minus_price_low_since_max']
    e['di_signed_spread_at_price_low'] = e['diAnchorValues']['di_signed_spread_at_price_low']
    e['di_signed_spread_at_price_low_confirmation'] = e['diAnchorValues']['di_signed_spread_at_price_low_confirmation']
    e['di_signed_spread_from_price_low'] = e['diAnchorValues']['di_signed_spread_from_price_low']
    e['di_signed_spread_price_low_since_min'] = e['diAnchorValues']['di_signed_spread_price_low_since_min']
    e['di_signed_spread_price_low_since_max'] = e['diAnchorValues']['di_signed_spread_price_low_since_max']
