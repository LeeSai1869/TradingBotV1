"""Read-only paper account and strategy-path diagnostics. No quotes/orders fetched."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time
from .config import Config, money
from . import source
from .engine import Ledger


def diagnose(path, *, name=None, now_ms=None):
    now=int(time.time()*1000) if now_ms is None else now_ms
    path=Path(path)
    if not path.is_file():raise ValueError('Paper ledger does not exist')
    snapshot=Ledger(path).view(name)
    rows=[(a['name'],a['config'],a['state']) for a in snapshot['accounts'] if not name or a['name']==name]
    if name and not rows:raise ValueError('Unknown paper account')
    result=[]
    for account,text,saved in rows:
        cfg=Config(**text);state=saved
        quote_age=(now-state['last_quote_ms'])/1000 if state.get('last_quote_ms') is not None else None
        report=dict(account=account,symbol=cfg.symbol,interval=cfg.interval,mode=cfg.mode,enabled=state['enabled'],halted=state['halted'],
            cash=state['cash'],cash_scope='shared_bot_wallet',quantity=state['quantity'],cursor=state['cursor'],quote_age_seconds=round(quote_age,1) if quote_age is not None else None,
            armed_at_ms=state['armed_at'],last_worker_status=state.get('status'),last_error_ms=state.get('last_error_ms'))
        try:
            pipeline=source.health(cfg,now_ms=now);report['pipeline']=pipeline
            if state['halted']:reason='HALTED_REVIEW_REQUIRED'
            elif pipeline['raw_stale']:reason='MARKET_DATA_STALE'
            elif pipeline['feature_through_ms'] is None or pipeline['feature_through_ms']<pipeline['raw_open_ms']:reason='FEATURE_WORKER_BEHIND'
            elif pipeline['decision_through_ms'] is None or pipeline['decision_through_ms']<pipeline['raw_open_ms']:reason='DECISION_WORKER_BEHIND'
            elif quote_age is None or not 0<=quote_age<=10:reason='QUOTE_UNAVAILABLE_OR_STALE'
            elif not state['enabled']:reason='ENTRIES_PAUSED'
            elif money(state['quantity'])>0:reason='POSITION_OPEN_MONITORING_EXITS'
            elif money(state['cash'])<=0:reason='WAITING_FOR_SHARED_CASH'
            else:
                signal=pipeline['latest_signal_last_24h'];close=signal.get('close_time') if signal else None
                if signal and signal['side']=='BUY' and close is not None and close>=state['armed_at'] and signal['open_time']>state['cursor']:
                    reason='FRESH_BUY_PENDING' if 0<=now-close<=cfg.max_signal_age_seconds*1000 else 'RECENT_BUY_TOO_OLD_TO_EXECUTE'
                else:reason='WAITING_FOR_NEW_CONFIRMED_BUY'
            report['diagnosis']=reason
        except (ValueError,OSError,sqlite3.Error,KeyError,TypeError) as error:
            report.update(diagnosis='STRATEGY_FEED_UNAVAILABLE',error=str(error))
        result.append(report)
    return result
