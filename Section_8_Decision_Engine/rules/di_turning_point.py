"""Faithful three-closed-candle translation of the supplied TradingView rule."""
import math

RULE_ID='DI_TURNING_POINT_V2'
VERSION=2
LOOKBACK=2
FIELDS=('di_plus','di_minus','di_spread','adx','close')


def valid(row,fields=FIELDS):
    return all(isinstance(row.get(key),(float,int)) and not isinstance(row[key],bool)
               and math.isfinite(row[key]) and row[key]>=0 for key in fields)


def evaluate(previous,current):
    if len(previous)<LOOKBACK or not valid(current) or not valid(previous[-1]) or not valid(previous[-2],FIELDS[:3]):
        return {'signal_type':None,'decision_state':'WARMUP','trigger':None}
    a,b=previous[-2:];c=current
    rising_adx=b['adx']<c['adx']
    spread_peak=a['di_spread']<b['di_spread'] and b['di_spread']>c['di_spread']
    buy_gate=(a['di_minus']<b['di_minus'] and b['di_minus']>c['di_minus']
              and spread_peak and c['close']>b['close'] and rising_adx)
    buy_cross=(a['di_minus']<a['di_plus'] and b['di_minus']<b['di_plus'] and c['di_minus']>c['di_plus'])
    buy_cont=(b['di_spread']>b['di_plus'] and a['di_minus']>a['di_plus']
              and b['di_minus']>b['di_plus'] and c['di_minus']>c['di_plus'])
    sell_gate=(a['di_plus']<b['di_plus'] and b['di_plus']>c['di_plus']
               and spread_peak and c['close']<b['close'] and rising_adx)
    sell_cross=(a['di_plus']<a['di_minus'] and b['di_plus']<b['di_minus'] and c['di_plus']>c['di_minus'])
    sell_cont=(b['di_spread']>b['di_minus'] and a['di_plus']>a['di_minus']
               and b['di_plus']>b['di_minus'] and c['di_plus']>c['di_minus'])
    decision=''
    if buy_gate and (buy_cross or buy_cont):decision='BUY'
    # Independent if, matching Pine's assignment order.
    if sell_gate and (sell_cross or sell_cont):decision='SELL'
    return {'signal_type':decision or None,'decision_state':decision or 'WAIT',
            'trigger':RULE_ID if decision else None}
