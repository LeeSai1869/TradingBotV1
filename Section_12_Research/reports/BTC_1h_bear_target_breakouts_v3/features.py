"""Causal 5m breakout/crash observations, never hindsight swing labels."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))

from collections import deque
from dataclasses import dataclass
import math
from Section_4_Features.features.volatility import calculate as atr

STEP=300000

@dataclass(slots=True)
class Observation:
    known_time:int
    ready:bool=False
    breakout_up:bool=False
    breakdown:bool=False
    crash:bool=False
    crash_recent:bool=False
    crash_unrecovered:bool=False
    micro_reclaim:bool=False
    range_low_reclaim:bool=False
    breakout_retest:bool=False
    rvol:float|None=None
    tr_atr:float|None=None
    return_5m_pct:float|None=None
    return_15m_pct:float|None=None
    prior_high:float|None=None
    prior_low:float|None=None
    close_location:float|None=None
    retest_level:float|None=None
    def __getitem__(self,key):return getattr(self,key)

def observe(bars,volumes):
    history=deque(maxlen=20);state={};previous_atr=None;out=[];last_crash=None;crash_high=None;crash_recovered=False;breakout_anchor=None;last_t=None
    for k,(bar,volume) in enumerate(zip(bars,volumes)):
        t,end,o,h,l,c=bar
        continuous=last_t is None or t==last_t+STEP
        if not continuous:history.clear();state={};previous_atr=None;last_crash=None;crash_high=None;crash_recovered=False;breakout_anchor=None
        ready=len(history)==20 and previous_atr is not None and math.isfinite(previous_atr) and previous_atr>0 and end==t+STEP-1
        f=Observation(known_time=end+1,ready=ready)
        if end!=t+STEP-1:
            out.append(f);history.clear();state={};previous_atr=None;last_crash=None;crash_high=None;crash_recovered=False;breakout_anchor=None;last_t=t;continue
        if ready:
            prev=list(history);prev_high=max(r[3] for r,v in prev[-12:]);prev_low=min(r[4] for r,v in prev[-12:]);micro_high=max(r[3] for r,v in prev[-3:]);prev_close=prev[-1][0][5]
            tr=max(h-l,abs(h-prev_close),abs(l-prev_close));position=(c-l)/(h-l) if h>l else .5
            available=[v for r,v in prev if v is not None and math.isfinite(v) and v>=0]
            denominator=sum(available)/20 if len(available)==20 else None
            rvol=volume/denominator if denominator and volume is not None and math.isfinite(volume) and volume>=0 else None
            ret=(c/prev_close-1)*100;ret3=(c/prev[-3][0][5]-1)*100;scale=tr/previous_atr
            up=c>prev_high and c>o and position>=.7 and scale>=1.2 and rvol is not None and rvol>=1.5
            down=c<prev_low and c<o and position<=.3 and scale>=1.5 and rvol is not None and rvol>=1.5
            crash=down and (ret<=-.5 or ret3<=-1)
            if crash:last_crash=k;crash_high=h;crash_recovered=False
            elif crash_high is not None and c>crash_high:crash_recovered=True
            recent=last_crash is not None and k-last_crash<=3
            unrecovered=last_crash is not None and k-last_crash<=12 and not crash_recovered
            micro=c>micro_high and c>o and position>=.6
            reclaim=l<prev_low and c>prev_low and position>=.65 and rvol is not None and rvol>=1.2
            retest=False;retest_level=None
            if breakout_anchor is not None:
                origin,level=breakout_anchor
                retest=1<=k-origin<=6 and l<=level*1.0005 and c>level and position>=.6 and not recent
                if retest:retest_level=level;breakout_anchor=None
                elif k-origin>6 or c<level or crash:breakout_anchor=None
            if up:breakout_anchor=(k,prev_high)
            for key,value in dict(breakout_up=up,breakdown=down,crash=crash,crash_recent=recent,crash_unrecovered=unrecovered,micro_reclaim=micro,range_low_reclaim=reclaim,breakout_retest=retest,retest_level=retest_level,rvol=rvol,tr_atr=scale,return_5m_pct=ret,return_15m_pct=ret3,prior_high=prev_high,prior_low=prev_low,close_location=position).items():setattr(f,key,value)
        out.append(f);previous_atr=atr(state,dict(high=h,low=l,close=c),14)
        history.append((bar,volume));last_t=t
    return out
