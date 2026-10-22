"""Closed-candle buy after two bearish DI/spread setup candles."""
import math

RULE_ID='DI_SPREAD_RECOVERY_V1'
VERSION=1
LOOKBACK=2
FIELDS=('di_plus','di_minus','di_spread')


def valid(row):
    return all(isinstance(row.get(key),(float,int)) and not isinstance(row[key],bool)
               and math.isfinite(row[key]) and row[key]>=0 for key in FIELDS)


def evaluate(previous,current):
    """previous is chronological and excludes current. No mutable trade position."""
    if len(previous)<LOOKBACK or not valid(current) or not all(valid(row) for row in previous[-LOOKBACK:]):
        return {'signal_type':None,'decision_state':'WARMUP','trigger':None}
    setup=all(row['di_minus']>row['di_plus'] and row['di_minus']>row['di_spread']
              and row['di_plus']<row['di_spread'] for row in previous[-LOOKBACK:])
    last=previous[-1]
    buy=(setup and current['di_plus']>=current['di_spread']
         and current['di_plus']>last['di_plus'] and current['di_minus']<last['di_minus'])
    return {'signal_type':'BUY' if buy else None,'decision_state':'BUY' if buy else 'WAIT',
            'trigger':RULE_ID if buy else None}
