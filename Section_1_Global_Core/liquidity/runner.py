"""Run independently: python3 -m Section_1_Global_Core.liquidity.runner."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import os
import re
import signal
import threading
import time
from .. import data_policy
from . import store
from .recorder import RESTClient,Worker,Writer


def instruments(payload):
    return {s['symbol'] for s in payload['symbols'] if s.get('contractType')=='PERPETUAL' and s.get('status')=='TRADING'
            and s.get('quoteAsset')=='USDT' and re.fullmatch(r'[A-Z0-9]{2,30}USDT',s['symbol'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--symbols',nargs='*');args=parser.parse_args()
    store.ROOT.mkdir(parents=True,exist_ok=True)
    with (store.ROOT/'recorder.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('A liquidity recorder already owns this checkout')
        stopping=threading.Event()
        for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stopping.set())
        rest=RESTClient();writer=Writer();workers={};supported=set();next_discovery=0
        snapshots=ThreadPoolExecutor(max_workers=2,thread_name_prefix='book-snapshot')
        context=ThreadPoolExecutor(max_workers=2,thread_name_prefix='perp-context')
        writer.start();print(f'[liquidity] started pid={os.getpid()} binance/usdt_perpetual; independent candle runner; memory={store.DB_PATH}',flush=True)
        try:
            while not stopping.is_set():
                if writer.failed.is_set():raise RuntimeError('Liquidity storage failed: '+str(writer.error))
                now=time.monotonic()
                if now>=next_discovery:
                    try:
                        supported=instruments(rest.get('/fapi/v1/exchangeInfo'));next_discovery=now+3600
                        writer.status('*','recording','Public Binance USDT perpetual feed')
                    except Exception as error:
                        writer.status('*','unavailable',str(error));print(f'[liquidity] discovery unavailable: {error}',flush=True);next_discovery=now+60
                active=set(data_policy.active_symbols())
                if args.symbols is not None:active&={s.upper() for s in args.symbols}
                wanted=set(sorted(active & supported)[:50])
                for symbol in active-supported:
                    writer.status(symbol,'unsupported' if supported else 'unavailable','No trading USDT perpetual instrument' if supported else 'Exchange discovery unavailable')
                for symbol in list(workers):
                    if symbol not in wanted or not workers[symbol].is_alive():
                        workers[symbol].stop();workers[symbol].join(timeout=2);del workers[symbol]
                for symbol in sorted(wanted-workers.keys()):
                    workers[symbol]=Worker(symbol,writer,rest,snapshots,context);workers[symbol].start()
                stopping.wait(10)
        finally:
            for worker in workers.values():worker.stop()
            for worker in workers.values():worker.join(timeout=2)
            snapshots.shutdown(wait=False,cancel_futures=True);context.shutdown(wait=False,cancel_futures=True)
            writer.stopping.set();writer.join(timeout=10)
            if writer.is_alive():print('[liquidity] writer draining; recent data may remain unavailable',flush=True)


if __name__=='__main__':main()
