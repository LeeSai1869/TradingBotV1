"""Measure full feature calculation without touching production databases."""
import argparse
import json
import math
import time
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import fast


def bars(count):
    for i in range(count):
        close=300+math.sin(i/9)*14+i*.02
        yield dict(symbol='BENCHUSDT',interval='1m',open_time=i*60000,close_time=(i+1)*60000-1,
                   open=close-.5,high=close+2,low=close-3,close=close,volume=10+i%17)


def measure(clients,warmup,reference=False):
    resolver=fast.resolve
    if reference:fast.resolve=lambda module,name:getattr(module,name)
    try:
        engine=Engine('BENCHUSDT','1m')
        for client in clients[:warmup]:engine.step(client)
        started=time.perf_counter()
        packets=[engine.step(client) for client in clients[warmup:]]
        elapsed=time.perf_counter()-started
        return {'bars':len(packets),'seconds':elapsed,'bars_per_second':len(packets)/elapsed,
                'milliseconds_per_bar':elapsed*1000/len(packets)},packets
    finally:fast.resolve=resolver


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bars',type=int,default=1000)
    parser.add_argument('--warmup',type=int,default=500)
    parser.add_argument('--compare',action='store_true',help='Also time the original reviewed loops and compare every output')
    args=parser.parse_args()
    if not 1<=args.bars<=10000 or not 0<=args.warmup<=10000:parser.error('bars must be 1–10000; warmup must be 0–10000')
    clients=list(bars(args.bars+args.warmup));result={'method':'Synthetic full-feature calculation; excludes network, SQLite and scheduler waits; no production writes'}
    if args.compare:original,before=measure(clients,args.warmup,True);result['reference']=original
    current,after=measure(clients,args.warmup);result['optimized']=current
    if args.compare:
        result['identical_packets']=before==after
        if before!=after:raise RuntimeError('Optimized packets differ from the reviewed reference')
        result['calculation_speedup']=original['seconds']/current['seconds']
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
