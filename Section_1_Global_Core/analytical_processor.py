"""Bounded analytical turns in the existing runner; never gates decisions."""
import threading
import time
import traceback
from collections import OrderedDict
from . import regime_research,aggregation_processor,analytical_history

_LOCK=threading.RLock()
_cursor=0
_status=OrderedDict()


def maintenance(symbols,intervals,*,max_bars=200,time_budget=.20,max_pairs=4,history_time_budget=.5,history_max_bars=200,history_max_pairs=4,skip_complete=False):
    global _cursor
    pairs=[(symbol,interval,engine) for symbol in symbols for interval in intervals for engine in ('REGIME','STRUCTURE','TREND','MOMENTUM','VOLATILITY','PARTICIPATION','PHASE','LIQUIDITY','SENTIMENT','BIAS')]
    if not pairs or max_bars<=0 or time_budget<=0:return 0
    started=time.monotonic();total=0
    with _LOCK:
        for _ in range(min(max_pairs,len(pairs))):
            if total>=max_bars or time.monotonic()-started>=time_budget:break
            symbol,interval,engine=pairs[_cursor%len(pairs)];_cursor+=1
            if skip_complete and _status.get((symbol,interval,engine)) in ('caught up to committed feature prefix','caught up to common committed dependency prefix'):continue
            try:
                row=regime_research.catch_up(symbol,interval,limit=min(100,max_bars-total),since=None,engine_name=engine,lock_timeout=.02)
                total+=row['processed']+row.get('dependency_processed',0);key=(symbol,interval,engine)
                prior=_status.get(key);_status[key]=row['status'];_status.move_to_end(key)
                if len(_status)>max(2000,len(pairs)):_status.popitem(last=False)
                if row['processed'] or prior!=row['status']:
                    latest=row.get('latest') or {}
                    print(f"[{engine.lower()}] {symbol} {interval}: +{row['processed']} closed classifications; {row['status']}; through={latest.get('candle_open_time')}",flush=True)
                # Aggregate only public normal-runner responses. One family per
                # visit; base/dependency rows plus aggregate rows share this budget.
                if row.get('symbol')==symbol and row.get('timeframe')==interval and total<max_bars and time.monotonic()-started<time_budget:
                    aggregation_processor.observe(symbol,interval,engine,row)
                    aggregate=aggregation_processor.refresh(symbol,engine,intervals=intervals,deadline=started+time_budget)
                    total+=aggregate['processed']
            except TimeoutError:
                # A transient writer collision must not postpone this scope for
                # an entire universe rotation. Retry it next maintenance turn.
                _cursor-=1
                key=(symbol,interval,engine)
                message='Waiting for market-data writer; retry next turn'
                if _status.get(key)!=message:
                    print(f"[{engine.lower()}] {symbol} {interval}: {message}",flush=True)
                _status[key]=message;_status.move_to_end(key)
                if len(_status)>max(2000,len(pairs)):_status.popitem(last=False)
                break
            except Exception:
                traceback.print_exc()  # Other processors/pairs still get their turns.
    total+=analytical_history.maintenance(symbols,intervals,max_bars=history_max_bars,time_budget=history_time_budget,max_pairs=history_max_pairs,skip_complete=skip_complete)
    return total


def process_bar(event):
    # Maintenance owns backfill and new closes alike. Do not turn analytical
    # availability into a prerequisite for DI decisions/event cursor progress.
    return True
