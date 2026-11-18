"""Bounded, read-only timing of Core's complete stored-chart page on local data."""
import argparse
from contextlib import ExitStack
import cProfile
import functools
import json
import pstats
import subprocess
import sys
import time
from unittest.mock import patch


def measure(symbol, interval, limit, *, profile=False):
    from Section_1_Global_Core import analysis, data_policy
    from Section_1_Global_Core.memory_storage.Storage import db, features_store, opportunity_inventory
    if not data_policy.enabled(symbol, interval):
        print(json.dumps(dict(skipped='inactive coin/timeframe',symbol=symbol,interval=interval)),flush=True)
        return
    stages={}
    def wrap(original,label):
        @functools.wraps(original)
        def timed(*args,**kwargs):
            name=label(args) if callable(label) else label
            print(json.dumps(dict(stage=name,event='start')),flush=True)
            started=time.perf_counter()
            try:return original(*args,**kwargs)
            finally:
                elapsed=time.perf_counter()-started
                item=stages.setdefault(name,dict(calls=0,seconds=0))
                item['calls']+=1;item['seconds']+=elapsed
                print(json.dumps(dict(stage=name,event='end',seconds=round(elapsed,4))),flush=True)
        return timed
    profiler=cProfile.Profile() if profile else None
    with ExitStack() as stack:
        for module,field,label in (
            (db,'_read_derived',lambda args:args[0].__name__.rsplit('.',1)[-1]),
            (db,'read_previous_decision_candidate','previous_decision_search'),
            (db,'read_analysis_reference','analysis_reference'),
            (opportunity_inventory,'read_seed','opportunity_history_seed'),
            (analysis,'annotate','analysis_projection'),
        ):
            stack.enter_context(patch.object(module,field,wrap(getattr(module,field),label)))
        print(json.dumps(dict(symbol=symbol,interval=interval,limit=limit,
            batched_feature_reader='resolve_rows' in __import__('inspect').getsource(features_store.read_range))),flush=True)
        reference=None
        for run in ('first','repeat'):
            stages.clear();started=time.perf_counter()
            if profiler:profiler.enable()
            page=db.read_state_page(symbol,interval,limit,analysis_reference=reference)
            if profiler:profiler.disable()
            read_seconds=time.perf_counter()-started
            started=time.perf_counter();encoded=json.dumps(page,allow_nan=False)
            report=dict(run=run,analysis_reference=reference,rows=len(page['bars']),read_seconds=round(read_seconds,4),
                json_seconds=round(time.perf_counter()-started,4),payload_MiB=round(len(encoded.encode())/1024**2,3),
                stages={name:dict(calls=v['calls'],seconds=round(v['seconds'],4)) for name,v in stages.items()})
            print('RESULT: '+json.dumps(report),flush=True)
            reference=next((bar['signal_context']['open_time'] for bar in reversed(page['bars']) if bar.get('signal_context')),None)
    if profiler:
        stats=pstats.Stats(profiler)
        top=sorted(stats.stats.items(),key=lambda item:item[1][3],reverse=True)[:12]
        print('PROFILE: '+json.dumps([dict(function=f'{key[0].rsplit("/",1)[-1]}:{key[1]}:{key[2]}',
            calls=value[1],cumulative_seconds=round(value[3],4)) for key,value in top]),flush=True)
    print('No database values, settings, or services changed.',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol',default='BTCUSDT')
    parser.add_argument('--interval',default='5m')
    parser.add_argument('--limit',type=int,default=200)
    parser.add_argument('--timeout',type=int,default=45)
    parser.add_argument('--profile',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not 1<=args.limit<=1000 or not 1<=args.timeout<=120:parser.error('Limit 1..1000; timeout 1..120 seconds')
    if args.worker:
        measure(args.symbol,args.interval,args.limit,profile=args.profile)
        return
    command=[sys.executable,'-u',__file__,'--worker','--symbol',args.symbol,
             '--interval',args.interval,'--limit',str(args.limit)]
    if args.profile:command.append('--profile')
    try:
        result=subprocess.run(command,timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print('Stopped at the time limit. The last stage=start identifies the blocked work. No cleanup was run.',flush=True)
        raise SystemExit(2)
    raise SystemExit(result.returncode)


if __name__=='__main__':main()
