"""Read-only, bounded as-of recorder projection for analytical liquidity.

Never fetches data, changes recorder state, or fills an old spot candle with a
current perpetual book. SQLite and decompression remain outside Section 5.
"""
from contextlib import contextmanager
import math
import json
import zlib
import sqlite3
from .liquidity import store

VERSION = 'liquidity-projection-v1'


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)


@contextmanager
def reader():
    conn = None
    try:
        conn = store.reader()
        if conn:conn.execute('BEGIN')
    except (OSError,sqlite3.Error):
        if conn:conn.close()
        conn = None
    try:yield conn
    finally:
        if conn:conn.close()


def _row(conn, symbol, at):
    row = conn.execute('SELECT available_ms,sampled_ms,payload FROM samples WHERE symbol=? AND available_ms<=? ORDER BY available_ms DESC LIMIT 1',(symbol,at)).fetchone()
    if not row:return None
    packet = store.unpack(row[2])
    if packet.get('available_ms') != row[0] or packet.get('sampled_ms',packet.get('available_ms')) != row[1]:return None
    return packet


def _project(packet, cfg):
    if packet is None:return None
    keys = ('venue','market','symbol','quote','observed','available_ms','sampled_ms','exchange_ms','book_received_ms','sequence','book_window_start_ms','window_start_ms','trade_coverage','reported_long_liquidations_usdt','reported_short_liquidations_usdt','liquidation_coverage')
    result = {key:packet.get(key) for key in keys}
    metrics = packet.get('metrics',{})
    selected = ('mid','best_bid','best_ask','spread_bps',f'bid_depth_{cfg.depth_bps}bps_usdt',f'ask_depth_{cfg.depth_bps}bps_usdt',f'buy_slippage_{cfg.execution_notional_usdt}_usdt_bps',f'sell_slippage_{cfg.execution_notional_usdt}_usdt_bps','bid_depth_10bps_change_usdt','ask_depth_10bps_change_usdt')
    result['metrics'] = {key:metrics.get(key) for key in selected}
    result['coverage'] = {key:packet.get('coverage',{}).get(key) for key in ('bid_bps','ask_bps')}
    context = packet.get('context',{})
    result['context'] = {key:context.get(key) for key in ('open_interest','open_interest_exchange_ms','open_interest_received_ms','mark_price','index_price','funding_rate','mark_exchange_ms','mark_received_ms')}
    analytics = packet.get('analytics',{})
    flow = analytics.get('60s',{})
    result['flow_60s'] = {key:flow.get(key) for key in ('complete','coverage','observed_window_ms','aggressive_buy_usdt','aggressive_sell_usdt','price_change_bps')}
    return result


def project(conn, snapshot, cfg):
    result = dict(version=VERSION,status='UNAVAILABLE',sample=None,oi_baseline=None,last_gap_ms=None,association=None)
    if conn is None:return result
    identity=snapshot['identity'];at=snapshot['as_of'];symbol=identity['symbol']
    if identity['venue']!='binance' or identity['instrument_id']!=symbol or not symbol.endswith('USDT'):return result
    try:
        packet=_row(conn,symbol,at)
        if not packet:return result
        sample=_project(packet,cfg)
        result.update(status='RECORDED',sample=sample)
        try:
            baseline=_row(conn,symbol,at-300000) if at>=300000 else None
            if baseline:
                base={key:baseline.get(key) for key in ('venue','market','symbol','quote','observed','available_ms','sampled_ms')}
                context=baseline.get('context',{})
                base['context']={key:context.get(key) for key in ('open_interest','open_interest_exchange_ms','open_interest_received_ms')}
                json.dumps(base,allow_nan=False)
                result['oi_baseline']=base
        except (sqlite3.Error,ValueError,TypeError,KeyError,OverflowError,AttributeError,zlib.error):
            # A corrupt/missing historical OI baseline cannot erase a good book.
            result['oi_baseline']=None
        result['last_gap_ms']=conn.execute("SELECT MAX(started_ms) FROM gaps WHERE symbol IN (?, '*') AND started_ms<=?",(symbol,at)).fetchone()[0]
        mid=sample['metrics']['mid'];close=snapshot['candle']['close']
        if identity['market_type']=='usdt_perpetual':result['association']=dict(kind='EXACT_MARKET')
        elif identity['market_type']=='spot' and finite(mid) and mid>0 and finite(close) and close>0:
            basis=(mid/close-1)*10000
            if finite(basis):result['association']=dict(kind='RELATED_PERPETUAL_CONTEXT',spot_close=close,spot_close_time=snapshot['candle_close_time'],perpetual_mid=mid,basis_bps=basis)
        json.dumps(result,allow_nan=False)
        return result
    except (sqlite3.Error,ValueError,TypeError,KeyError,OverflowError,AttributeError,zlib.error):
        return dict(version=VERSION,status='UNAVAILABLE',reason='Recorder projection unavailable',sample=None,oi_baseline=None,last_gap_ms=None,association=None)
