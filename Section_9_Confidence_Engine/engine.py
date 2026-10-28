"""Directional evidence scores, not calibrated outcome probabilities.

Pure closed-bar calculation. Missing inputs never award points. Correlated
features share capped families rather than counting each as a separate vote.
"""
from functools import lru_cache
from Section_1_Global_Core.analysis_packet import number,clean

VERSION='confidence-v2'
FIELDS=('atr','ema50','ema200','vwap','rsi','di_plus','di_minus','adx',
        'current_structure','bullish_structure_active','bearish_structure_active',
        'support_zone_low','support_zone_high','resistance_zone_low','resistance_zone_high',
        'inst_support_zone_low','inst_support_zone_high','inst_resistance_zone_low','inst_resistance_zone_high',
        'nearest_bull_fvg_low','nearest_bull_fvg_high','nearest_bear_fvg_low','nearest_bear_fvg_high',
        'active_bull_ob_low','active_bull_ob_high','active_bear_ob_low','active_bear_ob_high','atr_ma_ratio')


def clamp(value,lo=0.,hi=1.):return max(lo,min(hi,value))


PREVIOUS=('close','rsi','di_plus','di_minus')
CANDLE=('open','high','low')


def evaluate(close,features,*,previous=None,candle=None):
    return _context(close if number(close) else None,tuple(clean(features.get(k)) for k in FIELDS),
        tuple(clean((previous or {}).get(k)) for k in PREVIOUS),tuple(clean((candle or {}).get(k)) for k in CANDLE))


@lru_cache(maxsize=8192)
def _context(close,values,previous_values,candle_values):
    trend=_evaluate(close,values);f=dict(zip(FIELDS,values));previous=dict(zip(PREVIOUS,previous_values));candle=dict(zip(CANDLE,candle_values))
    turning=reversal(close,f,previous,candle,trend)
    high,low,opened=candle.get('high'),candle.get('low'),candle.get('open');rsi=f.get('rsi');ema=f.get('ema50')
    geometry=all(number(v) for v in (close,high,low,opened)) and high>low and low<=min(opened,close)<=max(opened,close)<=high
    buy_turn=geometry and ((min(opened,close)-low)/(high-low)>=.35 or close>opened and (close-low)/(high-low)>=.65) and (number(rsi) and rsi<=45 or number(ema) and close<ema)
    sell_turn=geometry and ((high-max(opened,close))/(high-low)>=.35 or close<opened and (high-close)/(high-low)>=.65) and (number(rsi) and rsi>=55 or number(ema) and close>ema)
    output={**trend,'mode':'price_point_context','continuation':trend,'reversal':turning}
    for side,turn in (('buy',buy_turn),('sell',sell_turn)):
        chosen=turning if turn else trend
        output[side+'_score']=chosen[side+'_score'];output[side+'_mode']='reversal' if turn else 'continuation'
        output[side+'_status']=chosen['status']
    output['coverage']=min(turning['coverage'] if buy_turn else trend['coverage'],turning['coverage'] if sell_turn else trend['coverage'])
    output['status']='ready' if all(output[side+'_status']=='ready' for side in ('buy','sell')) else 'insufficient evidence'
    output['interpretation']='price-point evidence /100; setup mode from candle context, never from BUY/SELL decisions'
    output['preference']='not a decision'
    return output


@lru_cache(maxsize=8192)
def _evaluate(close,values):
    f=dict(zip(FIELDS,values));atr=f['atr'];groups=[]
    valid=number(close) and close>0 and number(atr) and atr>0
    def group(name,weight,evidence,expected):
        known=[clamp(v) for v in evidence if v is not None]
        fraction=len(known)/expected
        quality=sum(known)/len(known) if known else None
        groups.append(dict(name=name,weight=weight,coverage=fraction,
            buy_points=weight*fraction*quality if quality is not None else 0.,
            sell_points=weight*fraction*(1-quality) if quality is not None else 0.))
    trend=[]
    for key in ('ema50','ema200','vwap'):
        value=f[key]
        trend.append(.5+.5*clamp((close-value)/(2*atr),-1,1) if valid and number(value) and value>0 else None)
    group('trend',20,trend,3)
    plus,minus,rsi,adx=f['di_plus'],f['di_minus'],f['rsi'],f['adx']
    di=plus/(plus+minus) if number(plus) and number(minus) and plus>=0 and minus>=0 and plus+minus>0 else None
    strength=clamp(adx/40) if number(adx) and 0<=adx<=100 else None
    directional=.5+(di-.5)*strength if di is not None and strength is not None else None
    group('momentum',25,[directional,rsi/100 if number(rsi) and 0<=rsi<=100 else None],2)
    structure=f['current_structure']
    bull=f['bullish_structure_active'];bear=f['bearish_structure_active']
    structure_quality=(.5 if bull and bear else 1. if bull else 0. if bear else
        1. if structure=='STRUCTURE_BULL' else 0. if structure=='STRUCTURE_BEAR' else
        .5 if structure=='STRUCTURE_RANGE' else None)
    group('structure',20,[structure_quality],1)
    supports=[];resistances=[]
    for low,high in (('support_zone_low','support_zone_high'),('resistance_zone_low','resistance_zone_high'),
        ('inst_support_zone_low','inst_support_zone_high'),('inst_resistance_zone_low','inst_resistance_zone_high'),
        ('nearest_bull_fvg_low','nearest_bull_fvg_high'),('nearest_bear_fvg_low','nearest_bear_fvg_high'),
        ('active_bull_ob_low','active_bull_ob_high'),('active_bear_ob_low','active_bear_ob_high')):
        lo,hi=f[low],f[high]
        if valid and number(lo) and number(hi) and 0<lo<hi:
            if hi<=close:supports.append(clamp(1-(close-hi)/(3*atr)))
            elif lo>=close:resistances.append(clamp(1-(lo-close)/(3*atr)))
    location=clamp(.5+.5*(max(supports,default=0)-max(resistances,default=0))) if supports or resistances else None
    group('location',25,[location],1)
    ratio=f['atr_ma_ratio']
    environment=clamp(1-abs(ratio-1)/2) if valid and number(ratio) and ratio>0 else None
    # Environment is nondirectional suitability; both sides may score well.
    group('environment',10,[environment],1)
    if environment is not None:groups[-1]['sell_points']=groups[-1]['buy_points']
    coverage=sum(g['weight']*g['coverage'] for g in groups)/100
    ready=valid and coverage>=.75
    buy=round(sum(g['buy_points'] for g in groups),2) if valid else None
    sell=round(sum(g['sell_points'] for g in groups),2) if valid else None
    return dict(version=VERSION,status='ready' if ready else 'insufficient evidence',
        buy_score=buy,sell_score=sell,coverage=round(coverage,3),groups=groups,
        interpretation='evidence score /100; not a win probability',scope='closed chart timeframe; no HTF or live perpetual inputs',
        preference='not a decision')


def reversal(close,f,previous,candle,trend):
    """Close-time turning evidence; no outcome, later candle or peak label."""
    atr=f.get('atr');valid=number(close) and close>0 and number(atr) and atr>0
    groups=[]
    def add(name,weight,buy,sell):
        known=[(b,s) for b,s in zip(buy,sell) if b is not None and s is not None]
        groups.append(dict(name=name,weight=weight,coverage=len(known)/len(buy),
            buy_points=weight*sum(clamp(b) for b,s in known)/len(buy),
            sell_points=weight*sum(clamp(s) for b,s in known)/len(buy)))
    rsi=f.get('rsi');ema=f.get('ema50')
    high_rsi=clamp((rsi-50)/25) if number(rsi) and 0<=rsi<=100 else None
    low_rsi=clamp((50-rsi)/25) if high_rsi is not None else None
    stretch=clamp((close-ema)/(2*atr),-1,1) if valid and number(ema) else None
    add('exhaustion',25,[low_rsi,max(0,-stretch) if stretch is not None else None],
        [high_rsi,max(0,stretch) if stretch is not None else None])
    high,low,opened=candle.get('high'),candle.get('low'),candle.get('open')
    geometry=valid and all(number(v) for v in (high,low,opened)) and low<=min(opened,close)<=max(opened,close)<=high and high>low
    upper=(high-max(opened,close))/(high-low) if geometry else None
    lower=(min(opened,close)-low)/(high-low) if geometry else None
    add('rejection',25,[clamp(lower/.5) if geometry else None,(close-low)/(high-low) if geometry else None],
        [clamp(upper/.5) if geometry else None,(high-close)/(high-low) if geometry else None])
    prev_close=previous.get('close');prev_rsi=previous.get('rsi')
    change=(close-prev_close)/(.5*atr) if valid and number(prev_close) else None
    rsi_change=(rsi-prev_rsi)/5 if number(rsi) and number(prev_rsi) else None
    plus,minus=f.get('di_plus'),f.get('di_minus')
    prev_plus,prev_minus=previous.get('di_plus'),previous.get('di_minus')
    buy_turn=clamp((prev_minus-minus)/10) if number(prev_minus) and number(minus) else None
    sell_turn=clamp((prev_plus-plus)/10) if number(prev_plus) and number(plus) else None
    add('turn_confirmation',25,[buy_turn,clamp(change) if change is not None else None,clamp(rsi_change) if rsi_change is not None else None],
        [sell_turn,clamp(-change) if change is not None else None,clamp(-rsi_change) if rsi_change is not None else None])
    supports=[];resistances=[]
    for prefix in ('support_zone','resistance_zone','inst_support_zone','inst_resistance_zone',
                   'nearest_bull_fvg','nearest_bear_fvg','active_bull_ob','active_bear_ob'):
        lo,hi=f.get(prefix+'_low'),f.get(prefix+'_high')
        if valid and number(lo) and number(hi) and 0<lo<hi:
            distance=max(lo-close,close-hi,0)
            quality=1. if geometry and low<=hi and high>=lo else clamp(1-distance/(2*atr))
            (supports if (lo+hi)/2<=close else resistances).append(quality)
    known=bool(supports or resistances)
    add('reversal_location',15,[max(supports,default=0) if known else None],[max(resistances,default=0) if known else None])
    ratio=f.get('atr_ma_ratio')
    environment=clamp(1-abs(ratio-1)/2) if valid and number(ratio) and ratio>0 else None
    add('environment',10,[environment],[environment])
    coverage=sum(g['weight']*g['coverage'] for g in groups)/100
    ready=valid and coverage>=.75
    buy=round(sum(g['buy_points'] for g in groups),2) if valid else None
    sell=round(sum(g['sell_points'] for g in groups),2) if valid else None
    return dict(version=VERSION,mode='reversal',status='ready' if ready else 'insufficient evidence',
        buy_score=buy,sell_score=sell,coverage=round(coverage,3),groups=groups,
        continuation=dict(buy_score=trend['buy_score'],sell_score=trend['sell_score'],status=trend['status']),
        interpretation='turning-point evidence /100, not a win probability or hindsight peak rating',
        scope='closed signal candle and its preceding closed candle; no future data',
        preference='not a decision')
