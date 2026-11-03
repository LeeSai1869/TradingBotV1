"""Causal numerical inputs for Section 5; no classifications or trade decisions.

Existing ATR/DI/EMA/volume MA are inputs, never recalculated here. State is bounded
and checkpointed with the owning feature context. Baseline ranks exclude the current observation.
"""
import hashlib
import json
import math
from bisect import bisect_left, bisect_right, insort

DEFAULTS = dict(measurementERLength=20, measurementBBLength=20,
    measurementBBMultiplier=2., measurementRankLength=500,
    measurementSlopeLength=5, measurementMomentumLength=10,
    measurementReturnLength=20, measurementChangeLength=5,
    measurementMACDFast=12, measurementMACDSlow=26, measurementMACDSignal=9)
GROUPS = {
    'momentum': ('di_signed_dominance','directional_movement_zero','efficiency_ratio',
        'roc_pct','momentum_atr','momentum_atr_change','momentum_strength_change',
        'macd_line','macd_signal','macd_histogram'),
    'trend': ('ema50_slope_atr','ema200_slope_atr','ema300_slope_atr',
        'positive_return_fraction','negative_return_fraction','flat_return_fraction'),
    'volatility': ('bb_middle','bb_stddev','bb_upper','bb_lower','bb_width_fraction',
        'natr_pct','natr_percentile','bb_width_percentile','natr_baseline_count',
        'bb_width_baseline_count','natr_baseline_degenerate','bb_width_baseline_degenerate',
        'natr_change_fraction','bb_width_change_fraction','realized_volatility',
        'return_skewness','zero_price_movement'),
    'volume': ('relative_volume_valid','relative_volume','volume_change_pct',
        'price_progress_per_relative_volume'),
    'shared_measurements': ('measurement_contiguous_bars','measurement_gap',
        'measurement_config_id','measurement_version'),
}
BOOLS={'directional_movement_zero','natr_baseline_degenerate','bb_width_baseline_degenerate',
       'zero_price_movement','relative_volume_valid','measurement_gap'}
INTS={'natr_baseline_count','bb_width_baseline_count','measurement_contiguous_bars'}
EXPORTS={key:('bool' if key in BOOLS else 'int' if key in INTS else 'string' if key in ('measurement_config_id','measurement_version') else 'float') for fields in GROUPS.values() for key in fields}


def valid(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def validate(config):
    for key in DEFAULTS:
        value=config[key]
        if key=='measurementBBMultiplier':
            if not valid(value) or not 0<value<=10:raise ValueError(f'{key} must be in (0,10]')
        elif type(value) is not int or not 2<=value<=5000:raise ValueError(f'{key} must be an integer in [2,5000]')
    if config['measurementMACDFast']>=config['measurementMACDSlow']:raise ValueError('MACD fast length must be below slow length')


def window(state,key,value,length):
    queue=state.setdefault(key,[])
    if not valid(value):queue.clear();return []
    queue.append(value)
    if len(queue)>length:del queue[0]
    return queue


def rank(state,key,value,length):
    """Midrank in a full *prior contiguous* baseline; O(log N) comparisons."""
    item=state.setdefault(key,{'queue':[],'sorted':[]});queue,ordered=item['queue'],item['sorted']
    if not valid(value):queue.clear();ordered.clear();return None,0,None
    count=len(queue);degenerate=ordered[0]==ordered[-1] if count==length else None
    result=100*(bisect_left(ordered,value)+.5*(bisect_right(ordered,value)-bisect_left(ordered,value)))/length if count==length else None
    if count==length:old=queue.pop(0);ordered.pop(bisect_left(ordered,old))
    queue.append(value);insort(ordered,value)
    return result,count,degenerate


def ema(state,key,value,length):
    old=state.get(key);value=value if old is None else old+2/(length+1)*(value-old)
    state[key]=value;return value


def calculate(state,client,di_plus,di_minus,atr,ema50,ema200,ema300,volume_ma,config):
    """Mutates only supplied state; caller processes an ordered candle prefix."""
    cfg={key:config[key] for key in DEFAULTS};validate(cfg)
    identity=hashlib.sha256(json.dumps(cfg,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    timestamp=client['open_time'];last=state.get('last_time')
    if last is not None and timestamp<=last:raise ValueError('Measurement candles must be strictly chronological')
    gap=last is not None and timestamp!=state['next_time']
    if gap or state.get('config')!=identity:state.clear()
    out={key:None for key in EXPORTS};out.update(measurement_gap=gap,measurement_config_id=identity,measurement_version='shared-v1')
    close=client['close'];good=valid(close) and close>0
    if not good:
        state.clear();state.update(config=identity,last_time=timestamp,next_time=client['close_time']+1,bars=0)
        out.update(measurement_contiguous_bars=0,relative_volume_valid=False,natr_baseline_count=0,bb_width_baseline_count=0)
        return out
    state.update(config=identity,last_time=timestamp,next_time=client['close_time']+1,bars=state.get('bars',0)+1)
    out['measurement_contiguous_bars']=state['bars']
    n=cfg['measurementERLength'];m=cfg['measurementMomentumLength'];r=cfg['measurementReturnLength'];change=cfg['measurementChangeLength']
    closes=window(state,'closes',close,max(n,m,r)+1)
    if len(closes)>=n+1:
        sample=closes[-n-1:];path=math.fsum(abs(b-a) for a,b in zip(sample,sample[1:]))
        out['efficiency_ratio']=abs(sample[-1]-sample[0])/path if path>0 else 0.
        out['zero_price_movement']=path==0
    if valid(di_plus) and valid(di_minus) and di_plus>=0 and di_minus>=0:
        total=di_plus+di_minus;out['directional_movement_zero']=total==0
        out['di_signed_dominance']=(di_plus-di_minus)/total if total else 0.
    if len(closes)>=m+1:
        displacement=close-closes[-m-1];out['roc_pct']=100*displacement/closes[-m-1]
        if valid(atr) and atr>0:out['momentum_atr']=displacement/atr
    previous=state.get('momentum')
    if previous is not None and out['momentum_atr'] is not None:
        out['momentum_atr_change']=out['momentum_atr']-previous
        out['momentum_strength_change']=abs(out['momentum_atr'])-abs(previous)
    state['momentum']=out['momentum_atr']
    fast=ema(state,'macd_fast',close,cfg['measurementMACDFast']);slow=ema(state,'macd_slow',close,cfg['measurementMACDSlow'])
    line=fast-slow;signal=ema(state,'macd_signal',line,cfg['measurementMACDSignal'])
    if state['bars']>=cfg['measurementMACDSlow']+cfg['measurementMACDSignal']-1:out.update(macd_line=line,macd_signal=signal,macd_histogram=line-signal)
    slope=cfg['measurementSlopeLength']
    for key,value in (('ema50',ema50),('ema200',ema200),('ema300',ema300)):
        values=window(state,key,value,slope+1)
        if len(values)==slope+1 and valid(atr) and atr>0:out[key+'_slope_atr']=(value-values[0])/atr
    if len(closes)>=r+1:
        returns=[math.log(b/a) for a,b in zip(closes[-r-1:],closes[-r:])]
        mean=math.fsum(returns)/r;variance=math.fsum((v-mean)**2 for v in returns)/r;sd=math.sqrt(variance)
        out.update(realized_volatility=sd,return_skewness=math.fsum((v-mean)**3 for v in returns)/r/sd**3 if sd else None,
            positive_return_fraction=sum(v>0 for v in returns)/r,negative_return_fraction=sum(v<0 for v in returns)/r,flat_return_fraction=sum(v==0 for v in returns)/r)
    bb=window(state,'bb',close,cfg['measurementBBLength'])
    if len(bb)==cfg['measurementBBLength']:
        middle=math.fsum(bb)/len(bb);sd=math.sqrt(math.fsum((v-middle)**2 for v in bb)/len(bb));half=cfg['measurementBBMultiplier']*sd
        out.update(bb_middle=middle,bb_stddev=sd,bb_upper=middle+half,bb_lower=middle-half,bb_width_fraction=2*half/middle)
    out['natr_pct']=100*atr/close if valid(atr) and atr>=0 else None
    for name,field in (('natr','natr_pct'),('bb_width','bb_width_fraction')):
        out[name+'_percentile'],out[name+'_baseline_count'],out[name+'_baseline_degenerate']=rank(state,name+'_rank',out[field],cfg['measurementRankLength'])
        values=window(state,name+'_change',out[field],change+1)
        if len(values)==change+1 and values[0]>0:out[name+'_change_fraction']=(values[-1]-values[0])/values[0]
    volume=client['volume'];volume_valid=valid(volume) and volume>=0 and valid(volume_ma) and volume_ma>0
    out['relative_volume_valid']=volume_valid
    if volume_valid:
        out['relative_volume']=volume/volume_ma
        if len(closes)>1 and volume>0:out['price_progress_per_relative_volume']=(close/closes[-2]-1)/out['relative_volume']
    old=state.get('volume')
    if valid(volume) and volume>=0 and valid(old) and old>0:out['volume_change_pct']=100*(volume-old)/old
    state['volume']=volume if valid(volume) and volume>=0 else None
    return out


def update(e):
    if 'sharedMeasurementsState' not in e.persistent:
        e.initialize('sharedMeasurementsState', {})
    e['sharedMeasurementValues'] = calculate(e['sharedMeasurementsState'], e.current_client,
        e['diPlus'], e['diMinus'], e['atr'], e['ema50'], e['ema200'], e['ema300'], e['volumeMA'], {
        'measurementERLength': e.input('measurementERLength', 20),
        'measurementBBLength': e.input('measurementBBLength', 20),
        'measurementBBMultiplier': e.input('measurementBBMultiplier', 2.0),
        'measurementRankLength': e.input('measurementRankLength', 500),
        'measurementSlopeLength': e.input('measurementSlopeLength', 5),
        'measurementMomentumLength': e.input('measurementMomentumLength', 10),
        'measurementReturnLength': e.input('measurementReturnLength', 20),
        'measurementChangeLength': e.input('measurementChangeLength', 5),
        'measurementMACDFast': e.input('measurementMACDFast', 12),
        'measurementMACDSlow': e.input('measurementMACDSlow', 26),
        'measurementMACDSignal': e.input('measurementMACDSignal', 9),
    })
    e['di_signed_dominance'] = e['sharedMeasurementValues']['di_signed_dominance']
    e['directional_movement_zero'] = e['sharedMeasurementValues']['directional_movement_zero']
    e['efficiency_ratio'] = e['sharedMeasurementValues']['efficiency_ratio']
    e['roc_pct'] = e['sharedMeasurementValues']['roc_pct']
    e['momentum_atr'] = e['sharedMeasurementValues']['momentum_atr']
    e['momentum_atr_change'] = e['sharedMeasurementValues']['momentum_atr_change']
    e['momentum_strength_change'] = e['sharedMeasurementValues']['momentum_strength_change']
    e['macd_line'] = e['sharedMeasurementValues']['macd_line']
    e['macd_signal'] = e['sharedMeasurementValues']['macd_signal']
    e['macd_histogram'] = e['sharedMeasurementValues']['macd_histogram']
    e['ema50_slope_atr'] = e['sharedMeasurementValues']['ema50_slope_atr']
    e['ema200_slope_atr'] = e['sharedMeasurementValues']['ema200_slope_atr']
    e['ema300_slope_atr'] = e['sharedMeasurementValues']['ema300_slope_atr']
    e['positive_return_fraction'] = e['sharedMeasurementValues']['positive_return_fraction']
    e['negative_return_fraction'] = e['sharedMeasurementValues']['negative_return_fraction']
    e['flat_return_fraction'] = e['sharedMeasurementValues']['flat_return_fraction']
    e['bb_middle'] = e['sharedMeasurementValues']['bb_middle']
    e['bb_stddev'] = e['sharedMeasurementValues']['bb_stddev']
    e['bb_upper'] = e['sharedMeasurementValues']['bb_upper']
    e['bb_lower'] = e['sharedMeasurementValues']['bb_lower']
    e['bb_width_fraction'] = e['sharedMeasurementValues']['bb_width_fraction']
    e['natr_pct'] = e['sharedMeasurementValues']['natr_pct']
    e['natr_percentile'] = e['sharedMeasurementValues']['natr_percentile']
    e['bb_width_percentile'] = e['sharedMeasurementValues']['bb_width_percentile']
    e['natr_baseline_count'] = e['sharedMeasurementValues']['natr_baseline_count']
    e['bb_width_baseline_count'] = e['sharedMeasurementValues']['bb_width_baseline_count']
    e['natr_baseline_degenerate'] = e['sharedMeasurementValues']['natr_baseline_degenerate']
    e['bb_width_baseline_degenerate'] = e['sharedMeasurementValues']['bb_width_baseline_degenerate']
    e['natr_change_fraction'] = e['sharedMeasurementValues']['natr_change_fraction']
    e['bb_width_change_fraction'] = e['sharedMeasurementValues']['bb_width_change_fraction']
    e['realized_volatility'] = e['sharedMeasurementValues']['realized_volatility']
    e['return_skewness'] = e['sharedMeasurementValues']['return_skewness']
    e['zero_price_movement'] = e['sharedMeasurementValues']['zero_price_movement']
    e['relative_volume_valid'] = e['sharedMeasurementValues']['relative_volume_valid']
    e['relative_volume'] = e['sharedMeasurementValues']['relative_volume']
    e['volume_change_pct'] = e['sharedMeasurementValues']['volume_change_pct']
    e['price_progress_per_relative_volume'] = e['sharedMeasurementValues']['price_progress_per_relative_volume']
    e['measurement_contiguous_bars'] = e['sharedMeasurementValues']['measurement_contiguous_bars']
    e['measurement_gap'] = e['sharedMeasurementValues']['measurement_gap']
    e['measurement_config_id'] = e['sharedMeasurementValues']['measurement_config_id']
    e['measurement_version'] = e['sharedMeasurementValues']['measurement_version']
