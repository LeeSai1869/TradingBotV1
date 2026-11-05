"""Descriptive pivot outcomes, never trading signals or causal attribution."""
import math

VERSION = 'pivot-moves-v1'


def measure(rows, reference, side, expected_start, *, bars=None, end_time=None, threshold=2.):
    """Stream closed candles after a reference; never infer intrabar ordering."""
    result = dict(status='CENSORED', reference=reference, threshold_pct=threshold,
                  bars_observed=0, first_hit=None, max_favorable_pct=None,
                  max_adverse_pct=None, complete=False, gap=False)
    if not isinstance(reference,(int,float)) or not math.isfinite(reference) or reference<=0:
        result.update(reference=None,gap=True,reason='Invalid reference price')
        return result
    previous_close = expected_start-1
    last_open = None
    favorable = adverse = 0.
    for row in rows:
        if bars is not None and result['bars_observed'] >= bars:
            break
        if end_time is not None and row['open_time'] > end_time:
            break
        values = [row[k] for k in ('open','high','low','close')]
        if (row['open_time'] != previous_close+1 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in values)
                or row['low']>min(row['open'],row['close']) or row['high']<max(row['open'],row['close'])):
            result['gap'] = True
            break
        previous_close = row['close_time'];last_open = row['open_time']
        result['bars_observed'] += 1
        good = (row['high']/reference-1)*100 if side=='BUY_SIDE' else (1-row['low']/reference)*100
        bad = (row['low']/reference-1)*100 if side=='BUY_SIDE' else (1-row['high']/reference)*100
        favorable = max(favorable,good);adverse = min(adverse,bad)
        if result['first_hit'] is None and good >= threshold-1e-10:
            result['first_hit'] = dict(candle_time=row['open_time'], known_by=row['close_time']+1,
                                       bars=result['bars_observed'])
    result['complete'] = not result['gap'] and ((bars is not None and result['bars_observed']==bars)
                                               or (end_time is not None and last_open==end_time))
    if result['bars_observed']:
        result.update(max_favorable_pct=favorable,max_adverse_pct=adverse)
    result['status'] = 'HIT' if result['first_hit'] else 'NO_HIT' if result['complete'] else 'CENSORED'
    return result


def summarize(cases):
    result = dict(pivots=0,by_side={})
    for case in cases:
        result['pivots']+=1
        side=result['by_side'].setdefault(case['side'],dict(pivots=0,origin_hits=0,after_known_hits=0,
                                                          origin_censored=0,after_known_censored=0,hits_by_confirmation=0))
        side['pivots']+=1
        for name,key in (('origin','origin'),('after_known','after_known')):
            side[key+'_hits']+=case[name]['status']=='HIT'
            side[key+'_censored']+=case[name]['status'] in ('CENSORED','NO_POST_CONFIRMATION_WINDOW')
        side['hits_by_confirmation']+=case['origin_hit_by_confirmation']
    return result
