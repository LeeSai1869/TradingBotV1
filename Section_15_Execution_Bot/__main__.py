"""CLI and separately supervised paper worker; never imported by the chart runner."""
import argparse
import json
from pathlib import Path
import signal
import sqlite3
import time
from .config import Config, money
from .engine import Ledger
from . import quotes, source
from .reporting import Reporter

DEFAULT_DB=Path.home()/'.tradingindicator'/'paper-bot.sqlite3'


def turn(ledger,*,fetch=quotes.fetch,now_ms=None):
    results=[];cache={}
    for account in ledger.report():
        cfg=Config(**account['config']);state=account['state']
        if not state['enabled'] and money(state['quantity'])==0:continue
        try:
            # Snapshot/quote acquisition happens outside the private ledger write
            # transaction. No market database write locks are taken by this bot.
            try:feed=source.snapshot(cfg,state['cursor'],armed_at=state['armed_at'])
            except (ValueError,OSError,sqlite3.Error) as error:feed=None;results.append(dict(account=cfg.name,warning=str(error)))
            quote=cache.get(cfg.symbol)
            if quote is None:quote=cache[cfg.symbol]=fetch(cfg.symbol)
            now=int(time.time()*1000) if now_ms is None else now_ms
            fills=ledger.step(cfg.name,quote,feed,now)
            results.append(dict(account=cfg.name,paper_fills=fills))
        except Exception as error:
            # One failed pair/quote must not stop position protection elsewhere.
            ledger.failure(cfg.name,str(error),int(time.time()*1000) if now_ms is None else now_ms)
            results.append(dict(account=cfg.name,error=str(error),no_fill=True))
    return results


def main():
    parser=argparse.ArgumentParser(description='Binance Spot PAPER bot. Cannot submit real orders.')
    parser.add_argument('--db',type=Path,default=DEFAULT_DB)
    sub=parser.add_subparsers(dest='command',required=True)
    create=sub.add_parser('create');create.add_argument('--name',required=True);create.add_argument('--symbol',required=True)
    create.add_argument('--interval',required=True)
    strategy=create.add_mutually_exclusive_group()
    strategy.add_argument('--instance-id',help='Optional explicitly selected strategy instance')
    strategy.add_argument('--strategy',choices=['current'],default='current',help='Use the existing live strategy (default)')
    create.add_argument('--capital',required=True);create.add_argument('--capital-cap',required=True)
    create.add_argument('--stop-loss-pct',required=True);create.add_argument('--take-profit-pct',required=True)
    create.add_argument('--fee-bps',default='10');create.add_argument('--slippage-bps',default='5')
    for command in ('enable','pause'):
        sub.add_parser(command).add_argument('name')
    sub.add_parser('status')
    diagnostic=sub.add_parser('diagnose');diagnostic.add_argument('name',nargs='?')
    history=sub.add_parser('history');history.add_argument('name');history.add_argument('--limit',type=int,default=100)
    sub.add_parser('demo')
    run=sub.add_parser('run');run.add_argument('--once',action='store_true');run.add_argument('--poll-seconds',type=float,default=5)
    run.add_argument('--heartbeat-seconds',type=float,default=30);run.add_argument('--verbose',action='store_true')
    args=parser.parse_args();ledger=Ledger(args.db);now=int(time.time()*1000)
    try:
        if args.command=='demo':
            from .demo import demonstrate
            print(json.dumps(demonstrate(),indent=2))
        elif args.command=='create':
            config=Config(args.name,args.symbol,args.interval,args.instance_id or 'current',args.capital,args.capital_cap,
                          args.stop_loss_pct,args.take_profit_pct,args.fee_bps,args.slippage_bps,
                          strategy_source='selected' if args.instance_id else 'current')
            config=source.bind_current(config)
            source.snapshot(config,-1,armed_at=now)  # read-only selection/identity validation
            ledger.create(config,now);print('Paper account created PAUSED. No exchange credentials or orders.')
        elif args.command in ('enable','pause'):
            ledger.enabled(args.name,args.command=='enable',now)
        elif args.command=='diagnose':
            from .diagnostics import diagnose
            print(json.dumps(diagnose(args.db,name=args.name),indent=2))
        elif args.command=='history':print(json.dumps(ledger.history(args.name,args.limit),indent=2))
        elif args.command=='run':
            if not 1<=args.poll_seconds<=60:raise ValueError('Poll interval must be 1..60 seconds')
            if not 5<=args.heartbeat_seconds<=3600:raise ValueError('Heartbeat must be 5..3600 seconds')
            reporter=Reporter(args.heartbeat_seconds)
            import threading
            stopped=threading.Event()
            for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stopped.set())
            while not stopped.is_set():
                results=turn(ledger)
                packet=results if args.once or args.verbose else reporter.packet(results,time.monotonic())
                if packet is not None:print(json.dumps(packet),flush=True)
                if args.once:break
                stopped.wait(args.poll_seconds)
        else:print(json.dumps(ledger.report(),indent=2))
    except (ValueError,OSError,sqlite3.Error) as error:parser.exit(2,str(error)+'\n')


if __name__=='__main__':main()
