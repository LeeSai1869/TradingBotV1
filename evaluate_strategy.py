"""Read-only closed-candle signal study, not an exit/position-management backtest."""
import argparse
from collections import deque
import json
from pathlib import Path
from Section_1_Global_Core.global_packet import read_decision_history
from Section_8_Decision_Engine.rules import di_turning_point as rule


def study(rows,horizons=(1,3,6,12),cost_bps=0):
    """Signal at close; enter next bar OPEN, exit at horizon bar CLOSE.

    All horizons count from entry. Gaps discard unfinished observations. Each
    signal is an independent event, so overlapping signals are not a portfolio.
    """
    previous=deque(maxlen=2);pending=[];last_close=None
    stats={str(h):{'observations':0,'wins':0,'sum_return_pct':0.0} for h in horizons}
    result={'bars':0,'buy_signals':0,'sell_signals':0,'horizons':stats}
    for row in rows:
        if last_close is not None and row['open_time']!=last_close+1:
            previous.clear();pending.clear()
        last_close=row['close_time'];result['bars']+=1
        remaining=[]
        for event in pending:
            if event['entry'] is None:event['entry']=row['open'];event['age']=0
            event['age']+=1
            if event['age'] in horizons and event['entry']>0:
                change=(row['close']/event['entry']-1)*100*event['sign']-cost_bps/100
                stat=stats[str(event['age'])];stat['observations']+=1;stat['wins']+=change>0;stat['sum_return_pct']+=change
            if event['age']<max(horizons):remaining.append(event)
        pending=remaining
        signal=rule.evaluate(list(previous),row)['signal_type']
        if signal:
            result['buy_signals' if signal=='BUY' else 'sell_signals']+=1
            pending.append({'entry':None,'age':0,'sign':1 if signal=='BUY' else -1})
        previous.append(row)
    for stat in stats.values():
        n=stat['observations'];stat['win_rate_pct']=100*stat['wins']/n if n else None
        stat['mean_return_pct']=stat.pop('sum_return_pct')/n if n else None
    return result


def evaluate(symbols=None,intervals=None,horizons=(1,3,6,12),cost_bps=0):
    report={'rule':rule.RULE_ID,'method':'Independent forward-return events; next-bar-open entry; no position sizing, stops, or portfolio simulation',
            'round_trip_cost_bps':cost_bps,'horizons_bars':list(horizons),'pairs':[]}
    for symbol,interval,cap,rows in read_decision_history(symbols,intervals):
        report['pairs'].append({'symbol':symbol,'interval':interval,'feature_replay_through':cap,
                                **study(rows,horizons,cost_bps)})
    report['warning']='Only the committed formula-v3 prefix is evaluated. Incomplete replay can exclude recent market regimes. Zero events or synthetic tests cannot establish profitability.'
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols',nargs='+');parser.add_argument('--intervals',nargs='+')
    parser.add_argument('--horizons',type=int,nargs='+',default=[1,3,6,12])
    parser.add_argument('--cost-bps',type=float,default=0,help='Total round-trip fees/slippage; default zero (gross returns)')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.horizons or min(args.horizons)<1:parser.error('Horizons must be positive')
    if args.cost_bps<0:parser.error('Costs cannot be negative')
    text=json.dumps(evaluate(args.symbols,args.intervals,tuple(sorted(set(args.horizons))),args.cost_bps),indent=2,allow_nan=False)
    if args.output:args.output.write_text(text+'\n')
    print(text)


if __name__=='__main__':main()
