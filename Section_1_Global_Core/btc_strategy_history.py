"""Read-only chart gateway. Never alters feature checkpoints or live decisions."""
import sqlite3
import time
from . import data_policy,regime_inputs
from Section_8_Decision_Engine.btc_sell_rules import SellConfig,RULE_IDS
from Section_8_Decision_Engine.btc_research import FIELDS,TIMEFRAMES,simulate

def history(symbol,interval,limit=1000,before=None,days=90,include_all_trades=False,disabled_sell_rules=()):
    if symbol!='BTCUSDT' or interval not in TIMEFRAMES:raise ValueError('BTC strategy supports BTCUSDT: 5m, 15m, 30m, 1h')
    if type(limit) is not int or not 2<=limit<=1000 or before is not None and (type(before) is not int or before<0):raise ValueError('Invalid strategy window')
    if type(days) is not int or days not in (7,30,90,365):raise ValueError('Choose 7, 30, 90 or 365 days')
    if type(include_all_trades) is not bool:raise ValueError('Invalid trade detail scope')
    if not isinstance(disabled_sell_rules,(tuple,list)) or any(rule not in RULE_IDS for rule in disabled_sell_rules):raise ValueError('Unknown sell rule')
    sell_config=SellConfig(enabled=tuple(rule for rule in RULE_IDS if rule not in disabled_sell_rules))
    source=None
    try:
        with data_policy.snapshot_guard(timeout=1):
            source=regime_inputs.open_sources();meta=regime_inputs.source_metadata(source,symbol,interval,'initial',FIELDS)
            cap=source.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
            if not cap:raise regime_inputs.InputsUnavailable('Waiting for committed features')
            columns={r[1] for r in source.execute('PRAGMA table_info(features)')}
            if not set(FIELDS)<=columns:raise regime_inputs.InputsUnavailable('Strategy source fields missing')
            now=int(time.time()*1000);bound=min(now,before) if before is not None else now
            sql='SELECT k.open_time,k.close_time,k.open,k.high,k.low,k.close,f.formula_version,'+','.join('f.'+k for k in FIELDS)+''' FROM raw.klines k LEFT JOIN features f ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time WHERE k.symbol=? AND k.interval=? AND k.open_time<=? AND k.close_time<? AND k.open_time>=? ORDER BY k.open_time DESC LIMIT 105121'''
            raw=source.execute(sql,(symbol,interval,cap[0],bound,bound-days*86400000)).fetchall();rows=[]
            for r in reversed(raw):
                f=dict(zip(FIELDS,r[7:]))
                if r[6]!=3 or f['measurement_version']!='shared-v1' or not f['measurement_config_id']:raise regime_inputs.InputsUnavailable('Incompatible feature row in strategy window')
                rows.append(dict(zip(('open_time','close_time','open','high','low','close'),r[:6]),features=f))
        # Release the read transaction before the pure simulation. The chart
        # receives only its visible-sized tail; position state spans the horizon.
        source.close();source=None
        visible_start=rows[-limit]['open_time'] if len(rows)>=limit else rows[0]['open_time'] if rows else 0
        result=simulate(rows,detail_since=visible_start,sell_config=sell_config)
        total_trades=len(result['trades'])
        result['levels']=[level for level in result['levels'] if level['time']>=visible_start]
        result['events']=[event for event in result['events'] if event['time']>=visible_start]
        result['observations']=[event for event in result['observations'] if event['time']>=visible_start]
        if not include_all_trades:
            result['trades']=[trade for trade in result['trades'] if trade.get('exit_time',bound)>=visible_start]
        result['trade_detail_scope']='ALL' if include_all_trades else 'RECENT_CHART_WINDOW'
        return dict(result,symbol=symbol,timeframe=interval,source=meta,requested_days=days,total_trades=total_trades,display_candles=min(limit,len(rows)),window_start=rows[0]['open_time'] if rows else None,window_end=rows[-1]['open_time'] if rows else None)
    except (regime_inputs.InputsUnavailable,sqlite3.Error,OSError,TimeoutError) as error:return dict(status='UNAVAILABLE',reason=str(error),trades=[],levels=[])
    finally:
        if source:source.close()
