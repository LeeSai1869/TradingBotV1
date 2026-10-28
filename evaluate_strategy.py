"""Read-only closed-candle signal study, not an exit/position-management backtest."""
import argparse
from collections import deque
from datetime import datetime,timezone
import json
import math
from pathlib import Path
from Section_1_Global_Core.global_packet import read_decision_history
from Section_8_Decision_Engine.rules import di_turning_point as rule
from Section_8_Decision_Engine.sequence import alternate


def _stats(horizons):
    return {str(h):dict(observations=0,wins=0,gross_wins=0,sum_return_pct=0.,sum_gross_return_pct=0.) for h in horizons}


def _finish(stats):
    for stat in stats.values():
        n=stat['observations'];gross=stat.pop('sum_gross_return_pct');net=stat.pop('sum_return_pct')
        stat.update(win_rate_pct=100*stat['wins']/n if n else None,
            gross_win_rate_pct=100*stat['gross_wins']/n if n else None,
            mean_return_pct=net/n if n else None,mean_gross_return_pct=gross/n if n else None,
            break_even_round_trip_cost_bps=100*gross/n if n else None)
    return stats


def study(rows,horizons=(1,3,6,12),cost_bps=0,*,since_ms=None,until_ms=None,split_ms=None):
    """Signal at close; enter next bar OPEN, exit at horizon bar CLOSE.

    Pre-window bars seed the exact original gate/alternation, never outcomes.
    Signal availability selects the period. Outcomes beyond its end are excluded;
    unfinished earlier-period events are purged at the split. Overlapping events
    are not a portfolio. Costs are a fixed assumed round-trip bps deduction.
    """
    if not horizons or any(not isinstance(h,int) or h<1 for h in horizons):raise ValueError('Horizons must be positive integers')
    if not math.isfinite(cost_bps) or cost_bps<0:raise ValueError('Costs must be finite and nonnegative')
    if since_ms is not None and until_ms is not None and since_ms>=until_ms:raise ValueError('Since must precede until')
    if split_ms is not None and ((since_ms is not None and split_ms<=since_ms) or (until_ms is not None and split_ms>=until_ms)):raise ValueError('Split must be inside the evaluation window')
    previous=deque(maxlen=2);pending=[];last_close=None;last_signal=None
    stats=_stats(horizons);by_side={s:_stats(horizons) for s in ('BUY','SELL')}
    periods={p:{'horizons':_stats(horizons),'by_side':{s:_stats(horizons) for s in ('BUY','SELL')}} for p in ('earlier','later')} if split_ms is not None else {}
    result=dict(bars=0,bars_scanned=0,buy_signals=0,sell_signals=0,horizons=stats,by_side=by_side,periods=periods,
        first_signal_available_ms=None,last_signal_available_ms=None,first_outcome_available_ms=None,last_outcome_available_ms=None,
        gap_discarded_events=0,split_purged_events=0)
    for row in rows:
        available=row['close_time']+1
        if until_ms is not None and available>until_ms:break
        result['bars_scanned']+=1
        in_window=(since_ms is None or available>=since_ms) and (until_ms is None or available<until_ms)
        if in_window:result['bars']+=1
        if last_close is not None and row['open_time']!=last_close+1:
            previous.clear();result['gap_discarded_events']+=len(pending);pending.clear()
        last_close=row['close_time'];remaining=[]
        for event in pending:
            if event['period']=='earlier' and available>split_ms:
                result['split_purged_events']+=1;continue
            if event['entry'] is None:event['entry']=row['open'];event['age']=0
            event['age']+=1
            if event['age'] in horizons and event['entry']>0:
                gross=(row['close']/event['entry']-1)*100*event['sign'];net=gross-cost_bps/100
                groups=[stats,by_side[event['side']]]
                if periods:groups.extend([periods[event['period']]['horizons'],periods[event['period']]['by_side'][event['side']]])
                for group in groups:
                    stat=group[str(event['age'])];stat['observations']+=1;stat['wins']+=net>0;stat['gross_wins']+=gross>0
                    stat['sum_return_pct']+=net;stat['sum_gross_return_pct']+=gross
                if result['first_outcome_available_ms'] is None:result['first_outcome_available_ms']=available
                result['last_outcome_available_ms']=available
            if event['age']<max(horizons):remaining.append(event)
        pending=remaining
        decision,last_signal=alternate(rule.evaluate(list(previous),row),last_signal)
        signal=decision['signal_type']
        if signal and in_window:
            result['buy_signals' if signal=='BUY' else 'sell_signals']+=1
            if result['first_signal_available_ms'] is None:result['first_signal_available_ms']=available
            result['last_signal_available_ms']=available
            period=('earlier' if available<split_ms else 'later') if split_ms is not None else None
            pending.append(dict(entry=None,age=0,sign=1 if signal=='BUY' else -1,side=signal,period=period))
        previous.append(row)
    _finish(stats)
    for group in by_side.values():_finish(group)
    for period in periods.values():
        _finish(period['horizons'])
        for group in period['by_side'].values():_finish(group)
    result['unfinished_events']=len(pending)
    return result


def evaluate(symbols=None,intervals=None,horizons=(1,3,6,12),cost_bps=0,*,since_ms=None,until_ms=None,split_ms=None):
    report={'rule':rule.RULE_ID,'method':'Independent forward-return events; next-bar-open entry; no position sizing, stops, or portfolio simulation',
            'round_trip_cost_bps':cost_bps,'horizons_bars':list(horizons),
            'window':dict(since_ms=since_ms,until_ms=until_ms,split_ms=split_ms,basis='signal available at candle close + 1ms; exits cannot cross window/split end'),
            'pairs':[]}
    for symbol,interval,cap,rows in read_decision_history(symbols,intervals):
        report['pairs'].append({'symbol':symbol,'interval':interval,'feature_replay_through':cap,
                                **study(rows,horizons,cost_bps,since_ms=since_ms,until_ms=until_ms,split_ms=split_ms)})
    report['warning']='Only the committed formula-v3 prefix is evaluated. Incomplete replay can exclude recent regimes. Chronological splits are descriptive, not proof of out-of-sample profitability. Overlapping events are not independent portfolio trades. Spot-price signals do not establish perpetual execution returns.'
    return report


def summary(report):
    """Compact console view; --output still preserves the complete JSON report."""
    lines=[f"Assumed round-trip cost: {report['round_trip_cost_bps']:g} bps. Independent events, not portfolio P&L.",
           'SYMBOL     TF  PERIOD   SIDE  BARS      N   GROSS_BP    NET_BP  NET_WIN%']
    fmt=lambda value:f'{value:.3f}' if value is not None else 'unknown'
    for pair in report['pairs']:
        periods=pair['periods'] or {'full':{'by_side':pair['by_side']}}
        for period,data in periods.items():
            for side,stats in data['by_side'].items():
                for horizon,stat in stats.items():
                    gross=stat['mean_gross_return_pct'];net=stat['mean_return_pct']
                    lines.append(f"{pair['symbol']:<10} {pair['interval']:<3} {period:<8} {side:<4} {horizon:>5} {stat['observations']:>6} {fmt(100*gross if gross is not None else None):>10} {fmt(100*net if net is not None else None):>9} {fmt(stat['win_rate_pct']):>9}")
    if not report['pairs']:lines.append('No stored eligible pairs in this checkout.')
    lines.append(report['warning'])
    return '\n'.join(lines)


def timestamp(text):
    try:
        value=datetime.fromisoformat(text.replace('Z','+00:00'))
        if value.tzinfo is None:
            if len(text)!=10:raise ValueError('Datetime must include a timezone offset')
            value=value.replace(tzinfo=timezone.utc)
        return int(value.timestamp()*1000)
    except ValueError as error:raise argparse.ArgumentTypeError(str(error)) from error


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols',nargs='+');parser.add_argument('--intervals',nargs='+')
    parser.add_argument('--horizons',type=int,nargs='+',default=[1,3,6,12])
    parser.add_argument('--cost-bps',type=float,default=0,help='Assumed total round-trip fees/slippage; default zero (gross returns)')
    parser.add_argument('--since',type=timestamp,help='Inclusive signal availability; YYYY-MM-DD means UTC midnight')
    parser.add_argument('--until',type=timestamp,help='Exclusive signal cutoff; exits may close exactly at this boundary')
    parser.add_argument('--split-at',type=timestamp,help='Report earlier/later periods separately, purging unfinished earlier events at the split')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--summary',action='store_true',help='Print a compact table; --output continues to save full JSON')
    args=parser.parse_args()
    try:
        # Validate before opening a database, including when this checkout has no data.
        study([],tuple(args.horizons),args.cost_bps,since_ms=args.since,until_ms=args.until,split_ms=args.split_at)
    except ValueError as error:parser.error(str(error))
    report=evaluate(args.symbols,args.intervals,tuple(sorted(set(args.horizons))),args.cost_bps,
        since_ms=args.since,until_ms=args.until,split_ms=args.split_at)
    text=json.dumps(report,indent=2,allow_nan=False)
    if args.output:args.output.write_text(text+'\n')
    print(summary(report) if args.summary else text)


if __name__=='__main__':main()
