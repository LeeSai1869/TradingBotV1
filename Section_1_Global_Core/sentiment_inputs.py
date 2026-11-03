"""Bounded recorder context projection; no feeds, sentiment model or indicators.

Source prices only establish an explicit spot/perpetual association. Funding is
indicative provider-period funding, not a normalized eight-hour or settled rate.
"""
from contextlib import contextmanager
import json
import math
import sqlite3
import zlib
from .liquidity import store

VERSION='sentiment-projection-v1'


@contextmanager
def reader():
    conn=None
    try:
        conn=store.reader()
        if conn:conn.execute('BEGIN')
    except (OSError,sqlite3.Error):
        if conn:conn.close()
        conn=None
    try:yield conn
    finally:
        if conn:conn.close()


def row_at(conn,symbol,at):
    row=conn.execute('SELECT available_ms,sampled_ms,payload FROM samples WHERE symbol=? AND available_ms<=? ORDER BY available_ms DESC LIMIT 1',(symbol,at)).fetchone()
    if not row:return None
    sample=store.unpack(row[2])
    if sample.get('available_ms')!=row[0] or sample.get('sampled_ms',sample.get('available_ms'))!=row[1]:return None
    keys=('venue','market','symbol','quote','observed','available_ms','sampled_ms','exchange_ms','book_received_ms','sequence','window_start_ms','reported_long_liquidations_usdt','reported_short_liquidations_usdt','liquidation_coverage')
    projected={k:sample.get(k) for k in keys}
    metrics=sample.get('metrics',{});projected['mid']=metrics.get('mid')
    context=sample.get('context',{})
    selected=('open_interest','open_interest_exchange_ms','open_interest_received_ms','mark_price','index_price','funding_rate','mark_exchange_ms','mark_received_ms','next_funding_ms')
    projected['context']={k:context.get(k) for k in selected}
    json.dumps(projected,allow_nan=False)
    return projected


def project(conn,snapshot):
    result=dict(version=VERSION,status='UNAVAILABLE',current=None,baseline=None,last_gap_ms=None,association=None)
    if conn is None:return result
    identity=snapshot['identity'];at=snapshot['as_of'];symbol=identity['symbol']
    if identity['venue']!='binance' or identity['instrument_id']!=symbol or not symbol.endswith('USDT'):return result
    errors=(sqlite3.Error,ValueError,TypeError,KeyError,OverflowError,AttributeError,zlib.error)
    try:
        current=row_at(conn,symbol,at)
        if not current:return result
        result.update(status='RECORDED',current=current)
        try:result['baseline']=row_at(conn,symbol,at-300000) if at>=300000 else None
        except errors:pass
        result['last_gap_ms']=conn.execute("SELECT MAX(started_ms) FROM gaps WHERE symbol IN (?, '*') AND started_ms<=?",(symbol,at)).fetchone()[0]
        if identity['market_type']=='usdt_perpetual':result['association']=dict(kind='EXACT_MARKET')
        elif identity['market_type']=='spot':
            mid=current['mid'];close=snapshot['candle']['close']
            finite=lambda v:isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0
            if finite(mid) and finite(close):
                basis=(mid/close-1)*10000
                if math.isfinite(basis):result['association']=dict(kind='RELATED_PERPETUAL_CONTEXT',spot_close=close,spot_close_time=snapshot['candle_close_time'],perpetual_mid=mid,basis_bps=basis)
        return result
    except errors:return dict(version=VERSION,status='UNAVAILABLE',current=None,baseline=None,last_gap_ms=None,association=None)
