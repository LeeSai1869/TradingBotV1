"""Causal BTC spot hypothesis. Simulated fills only; never publishes decisions."""
import math
VERSION='btc-visual-v0.1'
TIMEFRAMES=('5m','15m','30m','1h')
FIELDS=('measurement_version','measurement_config_id','measurement_gap','candidate_pivot','candidate_pivot_low_price','candidate_pivot_low_time','di_plus','di_minus','atr')

def valid(value):
    return isinstance(value,(int,float)) and math.isfinite(value)

def simulate(rows):
    """Close-confirmed setup -> next open. Stops set at prior close only.

    Each timeframe is an independent simulation, initially flat at window start.
    A candidate low followed by price recovery and weakening DI- arms a buy.
    DI changes alone never exit. 0.5% activates trailing, never fixed take-profit.
    """
    trades=[];levels=[];observations=[];setup=None;pending=None;position=None;previous=None;used=set();gaps=0
    fee=.0004;slip=.0002
    for row in rows:
        f=row['features'];t=row['open_time'];o,h,l,c=(row[k] for k in ('open','high','low','close'))
        continuous=previous is None or previous['close_time']+1==t
        usable=all(valid(x) and x>0 for x in (o,h,l,c)) and l<=min(o,c)<=max(o,c)<=h and all(valid(f.get(k)) for k in ('di_plus','di_minus','atr')) and f['atr']>0 and not f.get('measurement_gap')
        if not continuous or not usable:
            gaps+=1
            if position:position.update(status='CENSORED',exit_time=t,reason='Missing or invalid candle/features')
            position=setup=pending=None;previous=None
            continue
        if pending and not position:
            if o>pending['low'] and o<=pending['trigger']*1.005:
                entry=o*(1+slip)
                position=dict(entry_time=t,entry=entry,hard_stop=entry*.995,stop=entry*.995,peak=entry,status='OPEN',setup_time=pending['time'],entry_reason='Candidate low recovery + DI- weakening + price confirmation')
                trades.append(position)
            pending=None
        if position:
            stop=position['stop'];levels.append(dict(time=t,entry_time=position['entry_time'],stop=stop,hard_stop=position['hard_stop'],entry=position['entry']))
            if o<=stop or l<=stop:
                fill=min(o,stop)*(1-slip)
                position.update(exit_time=t,exit=fill,status='CLOSED',reason='Trailing stop' if stop>position['hard_stop'] else 'Hard stop',net_pct=(fill*(1-fee)/(position['entry']*(1+fee))-1)*100)
                position=None;setup=None
            else:
                position['peak']=max(position['peak'],h)
                # Activation is a close observation. This updated stop first
                # applies to the next candle, never the current candle's low.
                if c>=position['entry']*1.005:
                    position['stop']=max(stop,position['peak']-1.5*f['atr'],position['entry']*(1+fee)/(1-fee)/(1-slip))
                    position['stop']=min(position['stop'],c)
        if not position:
            anchor=f.get('candidate_pivot_low_time');low=f.get('candidate_pivot_low_price')
            if f.get('candidate_pivot')==-1 and valid(anchor) and valid(low) and anchor not in used:
                if setup is None or setup['anchor']!=anchor or low<setup['low']:
                    setup=dict(anchor=anchor,low=low,time=t,age=0)
                    observations.append(dict(time=t,price=low,type='CANDIDATE LOW'))
            if setup:
                setup['age']+=1
                if l<setup['low'] or setup['age']>8:setup=None
                elif previous and t>setup['time'] and c>previous['high'] and f['di_minus']<previous['features']['di_minus'] and f['di_plus']>previous['features']['di_plus']:
                    pending={**setup,'trigger':c};used.add(setup['anchor']);setup=None
        previous=row
    return dict(version=VERSION,trades=trades,levels=levels,observations=observations,gaps=gaps,status='READY',candles=len(rows),interpretation='Experimental spot simulation; independent timeframe; starts flat at window start. No orders or alerts. Confidence is not a win probability.',costs=dict(fee_bps_per_side=4,slippage_bps_per_side=2),rules=dict(hard_stop_pct=.5,trailing_activation_pct=.5,trailing_atr=1.5))
