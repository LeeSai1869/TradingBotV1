"""Directional evidence scores, not calibrated outcome probabilities.

Pure closed-bar calculation. Missing inputs never award points. Correlated
features share capped families rather than counting each as a separate vote.
"""
import math
from functools import lru_cache

VERSION='confidence-v1'
FIELDS=('atr','ema50','ema200','vwap','rsi','di_plus','di_minus','adx',
        'current_structure','bullish_structure_active','bearish_structure_active',
        'support_zone_low','support_zone_high','resistance_zone_low','resistance_zone_high',
        'inst_support_zone_low','inst_support_zone_high','inst_resistance_zone_low','inst_resistance_zone_high',
        'nearest_bull_fvg_low','nearest_bull_fvg_high','nearest_bear_fvg_low','nearest_bear_fvg_high',
        'active_bull_ob_low','active_bull_ob_high','active_bear_ob_low','active_bear_ob_high','atr_ma_ratio')


def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def clamp(value,lo=0.,hi=1.):return max(lo,min(hi,value))


def clean(value):return value if isinstance(value,(str,bool)) or number(value) else None


def evaluate(close,features):
    return _evaluate(close if number(close) else None,tuple(clean(features.get(k)) for k in FIELDS))


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
        preference=('BUY' if buy-sell>=10 else 'SELL' if sell-buy>=10 else 'MIXED') if ready else 'WAIT')
