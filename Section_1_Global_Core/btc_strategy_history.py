"""Read-only chart gateway. Never alters feature checkpoints or live decisions."""
import sqlite3
import time
from . import data_policy,regime_inputs
from Section_8_Decision_Engine.btc_research import FIELDS,TIMEFRAMES,simulate

def history(symbol,interval,limit=1000,before=None):
    if symbol!='BTCUSDT' or interval not in TIMEFRAMES:raise ValueError('BTC strategy supports BTCUSDT: 5m, 15m, 30m, 1h')
    if type(limit) is not int or not 2<=limit<=1000 or before is not None and (type(before) is not int or before<0):raise ValueError('Invalid strategy window')
    source=None
    try:
        with data_policy.snapshot_guard(timeout=1):
            source=regime_inputs.open_sources();meta=regime_inputs.source_metadata(source,symbol,interval,'initial',FIELDS)
            cap=source.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
            if not cap:raise regime_inputs.InputsUnavailable('Waiting for committed features')
            columns={r[1] for r in source.execute('PRAGMA table_info(features)')}
            if not set(FIELDS)<=columns:raise regime_inputs.InputsUnavailable('Strategy source fields missing')
            now=int(time.time()*1000);bound=min(now,before) if before is not None else now
            sql='SELECT k.open_time,k.close_time,k.open,k.high,k.low,k.close,f.formula_version,'+','.join('f.'+k for k in FIELDS)+''' FROM raw.klines k LEFT JOIN features f ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time WHERE k.symbol=? AND k.interval=? AND k.open_time<=? AND k.close_time<? ORDER BY k.open_time DESC LIMIT ?'''
            raw=source.execute(sql,(symbol,interval,cap[0],bound,limit)).fetchall();rows=[]
            for r in reversed(raw):
                f=dict(zip(FIELDS,r[7:]))
                if r[6]!=3 or f['measurement_version']!='shared-v1' or not f['measurement_config_id']:raise regime_inputs.InputsUnavailable('Incompatible feature row in strategy window')
                rows.append(dict(zip(('open_time','close_time','open','high','low','close'),r[:6]),features=f))
            return dict(simulate(rows),symbol=symbol,timeframe=interval,source=meta,window_start=rows[0]['open_time'] if rows else None,window_end=rows[-1]['open_time'] if rows else None)
    except (regime_inputs.InputsUnavailable,sqlite3.Error,OSError,TimeoutError) as error:return dict(status='UNAVAILABLE',reason=str(error),trades=[],levels=[])
    finally:
        if source:source.close()
