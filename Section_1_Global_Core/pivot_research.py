"""Read-only full-history pivot cohort and on-demand full-feature case windows."""
import json
import math
import re
import time
from . import data_policy,regime_inputs
from .memory_storage.Storage import engine_store
from Section_8_Decision_Engine.pivot_study import VERSION,measure,summarize

TIMEFRAMES=('1m','5m','15m','30m','1h')
FIELDS=('structure_events','structure_events_version','structure_event_status',
        'measurement_version','measurement_config_id','measurement_gap')


def validate(symbol,interval):
    if not isinstance(symbol,str) or not re.fullmatch('[A-Z0-9]{2,30}USDT',symbol) or interval not in TIMEFRAMES:
        raise ValueError('Choose a USDT symbol and 1m, 5m, 15m, 30m or 1h')


def metadata(conn,symbol,interval):
    columns=[row[1] for row in conn.execute('PRAGMA table_info(features)')]
    if not set(FIELDS)<=set(columns):raise regime_inputs.InputsUnavailable('Pivot event columns are unavailable')
    from Section_4_Features.execution.components import catalog
    feature_catalog=catalog()
    calculated=tuple(field for field in columns if field in feature_catalog.export_inverse and feature_catalog.export_inverse[field] in feature_catalog.final)
    source=regime_inputs.source_metadata(conn,symbol,interval,'initial',calculated)
    source['feature_schema_id']=engine_store.digest(columns)
    cap=conn.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
    if not cap:raise regime_inputs.InputsUnavailable('No committed feature prefix')
    return source,cap[0]


def pivot_events(raw,open_time,close_time):
    try:events=json.loads(raw or '[]')
    except (TypeError,ValueError):return []
    if not isinstance(events,list) or len(events)>64:return []
    return [e for e in events if isinstance(e,dict) and e.get('type') in ('PIVOT_LOW','PIVOT_HIGH')
            and isinstance(e.get('id'),str) and re.fullmatch('[a-f0-9]{64}',e['id'])
            and type(e.get('origin_time')) is int and 0<=e['origin_time']<open_time
            and e.get('known_time')==close_time+1 and e.get('confirmation_time')==open_time and isinstance(e.get('price'),(float,int))
            and not isinstance(e['price'],bool) and math.isfinite(e['price']) and e['price']>0]


def raw_path(conn,symbol,interval,start,cap,bound,end=None,bars=None):
    sql='SELECT open_time,close_time,open,high,low,close FROM raw.klines WHERE symbol=? AND interval=? AND open_time>=? AND open_time<=? AND close_time<?'
    args=[symbol,interval,start,cap,bound]
    if end is not None:sql+=' AND open_time<=?';args.append(end)
    sql+=' ORDER BY open_time'
    if bars is not None:sql+=' LIMIT ?';args.append(bars)
    for row in conn.execute(sql,args):yield dict(zip(('open_time','close_time','open','high','low','close'),row))


def scan(symbol='BTCUSDT',interval='15m',*,since=0,until=None,horizon=None,threshold=2.,now_ms=None,progress=None):
    validate(symbol,interval)
    now=int(time.time()*1000) if now_ms is None else now_ms
    bound=min(now,until) if until is not None else now
    if type(since) is not int or since<0 or since>=bound:raise ValueError('Invalid study period')
    if horizon is not None and (type(horizon) is not int or not 1<=horizon<=1000):raise ValueError('Horizon must be 1..1000 bars or next opposite pivot')
    if not isinstance(threshold,(int,float)) or not math.isfinite(threshold) or not 0<threshold<=100:raise ValueError('Invalid move threshold')
    conn=None
    try:
        with data_policy.snapshot_guard(timeout=1):
            conn=regime_inputs.open_sources();source,cap=metadata(conn,symbol,interval)
            last_close=conn.execute('SELECT MAX(close_time) FROM raw.klines WHERE symbol=? AND interval=? AND open_time<=? AND close_time<?',(symbol,interval,cap,bound)).fetchone()[0]
            if last_close is None or since>=last_close+1:raise regime_inputs.InputsUnavailable('No committed candle coverage in the requested period')
            bound=min(bound,last_close+1)
            pivots={};bad_rows=0;event_rows=0
            query='''SELECT k.open_time,k.close_time,f.formula_version,f.measurement_version,f.measurement_config_id,
                f.structure_events,f.structure_events_version,f.structure_event_status FROM features f JOIN raw.klines k
                ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time
                WHERE f.symbol=? AND f.interval=? AND f.open_time<=? AND k.close_time<?
                AND f.structure_events IS NOT NULL AND f.structure_events!='[]' ORDER BY f.open_time'''
            for row in conn.execute(query,(symbol,interval,cap,bound)):
                event_rows+=1
                if progress and event_rows%10000==0:progress(dict(stage='event_rows',complete=event_rows))
                if row[2]!=3 or row[3]!='shared-v1' or not row[4] or row[6]!='structure-events-v1' or row[7]!='READY':
                    bad_rows+=1;continue
                for event in pivot_events(row[5],row[0],row[1]):pivots[event['id']]=event
            ordered=sorted(pivots.values(),key=lambda e:(e['origin_time'],e['known_time'],e['id']))
            next_opposite={};nearest={}
            for event in reversed(ordered):
                next_opposite[event['id']]=nearest.get('PIVOT_HIGH' if event['type']=='PIVOT_LOW' else 'PIVOT_LOW')
                nearest[event['type']]=event
            cases=[];missing_origins=0
            for index,pivot in enumerate(ordered):
                if progress and index%500==0:progress(dict(stage='pivot_outcomes',complete=index,total=len(ordered)))
                if pivot['origin_time']<since:continue
                origin=conn.execute('SELECT close_time FROM raw.klines WHERE symbol=? AND interval=? AND open_time=?',(symbol,interval,pivot['origin_time'])).fetchone()
                if not origin:missing_origins+=1;continue
                side='BUY_SIDE' if pivot['type']=='PIVOT_LOW' else 'SELL_SIDE'
                opposite=next_opposite[pivot['id']]
                end=opposite['origin_time'] if horizon is None and opposite else None
                # A missing next opposite pivot is a censored swing; inspect
                # observed remaining history, never call it a completed failure.
                origin_move=measure(raw_path(conn,symbol,interval,origin[0]+1,cap,bound,end,horizon),pivot['price'],side,origin[0]+1,bars=horizon,end_time=end,threshold=threshold)
                if end is not None and end<pivot['known_time']:
                    after=dict(status='NO_POST_CONFIRMATION_WINDOW',reference=None,first_hit=None)
                else:
                    iterator=iter(raw_path(conn,symbol,interval,pivot['known_time'],cap,bound,end,horizon))
                    first=next(iterator,None)
                    if first is None or first['open_time']!=pivot['known_time']:
                        after=dict(status='CENSORED',reference=None,first_hit=None)
                    else:
                        from itertools import chain
                        after=measure(chain([first],iterator),first['open'],side,pivot['known_time'],bars=horizon,end_time=end,threshold=threshold)
                cases.append(dict(id=pivot['id'],side=side,pivot=pivot,origin=origin_move,after_known=after,
                                  next_opposite=opposite,origin_hit_by_confirmation=bool(origin_move['first_hit'] and origin_move['first_hit']['known_by']<=pivot['known_time'])))
            coverage=conn.execute('SELECT MIN(open_time),MAX(open_time),COUNT(*) FROM raw.klines WHERE symbol=? AND interval=? AND open_time<=? AND close_time<?',(symbol,interval,cap,bound)).fetchone()
            return dict(version=VERSION,status='READY',symbol=symbol,timeframe=interval,source=source,source_id=engine_store.digest(source),
                        requested_since=since,requested_until=until,observed_as_of=bound,coverage=dict(first=coverage[0],last=coverage[1],candles=coverage[2]),
                        config=dict(threshold_pct=threshold,horizon_bars=horizon,window='NEXT_OPPOSITE_PIVOT' if horizon is None else 'FIXED_BARS'),
                        summary=summarize(cases),cases=cases,warnings=dict(invalid_event_rows=bad_rows,missing_origin_candles=missing_origins),
                        interpretation='Retrospective outcome selection; known times are reconstructed close-time knowledge, not actual publication times. Targets use candle high/low touches, not close-only moves. Not a strategy backtest. SELL_SIDE means decline after a high, not short profit. OHLC gives no intrabar ordering. Associations do not establish cause. No production logic changed.')
    finally:
        if conn:conn.close()


def case_context(symbol,interval,pivot_id,known_time,*,source_id,before=12,after=24,as_of=None):
    validate(symbol,interval)
    if not isinstance(pivot_id,str) or not re.fullmatch('[a-f0-9]{64}',pivot_id) or type(known_time) is not int or not 1<=known_time<=9223372036854775807:raise ValueError('Invalid pivot identity')
    if type(before) is not int or type(after) is not int or not 0<=before<=100 or not 0<=after<=100:raise ValueError('Choose 0..100 context bars')
    conn=None
    try:
        with data_policy.snapshot_guard(timeout=1):
            conn=regime_inputs.open_sources();source,cap=metadata(conn,symbol,interval)
            if engine_store.digest(source)!=source_id:raise regime_inputs.InputsUnavailable('Feature generation/config differs from the report; regenerate the cohort')
            row=conn.execute('''SELECT k.open_time,k.close_time,f.structure_events,f.formula_version,f.measurement_version,f.measurement_config_id,f.structure_events_version,f.structure_event_status FROM features f JOIN raw.klines k ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time
                WHERE f.symbol=? AND f.interval=? AND f.open_time=? AND k.close_time=? AND k.open_time<=?''',(symbol,interval,known_time-{'1m':60000,'5m':300000,'15m':900000,'30m':1800000,'1h':3600000}[interval],known_time-1,cap)).fetchone()
            if row and (row[3]!=3 or row[4]!='shared-v1' or not row[5] or row[6]!='structure-events-v1' or row[7]!='READY'):
                raise regime_inputs.InputsUnavailable('Pivot source row is incompatible')
            pivot=next((e for e in pivot_events(row[2],row[0],row[1]) if e['id']==pivot_id),None) if row else None
            if not pivot:raise regime_inputs.InputsUnavailable('Pivot event is not available in this source generation')
            now=int(time.time()*1000)
            if as_of is not None:
                if type(as_of) is not int or as_of<known_time:raise ValueError('Invalid context cutoff')
                now=min(now,as_of)
            times=set()
            for anchor in (pivot['origin_time'],row[0]):
                for direction,count,comparison in [('DESC',before+1,'<='),('ASC',after,'>')]:
                    query=f'SELECT open_time FROM raw.klines WHERE symbol=? AND interval=? AND open_time{comparison}? AND open_time<=? AND close_time<? ORDER BY open_time {direction} LIMIT ?'
                    times.update(r[0] for r in conn.execute(query,(symbol,interval,anchor,cap,now,count)))
            bars=[]
            if times:
                sql='''SELECT k.open_time AS raw_open_time,k.close_time AS raw_close_time,k.open AS raw_open,k.high AS raw_high,k.low AS raw_low,k.close AS raw_close,k.volume AS raw_volume,f.* FROM raw.klines k LEFT JOIN features f ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time WHERE k.symbol=? AND k.interval=? AND k.open_time IN ('''+','.join('?' for _ in times)+') ORDER BY k.open_time'
                cursor=conn.execute(sql,[symbol,interval,*sorted(times)]);names=[d[0] for d in cursor.description]
                for values in cursor:
                    record=dict(zip(names,values));client={key:record.pop('raw_'+key) for key in ('open_time','close_time','open','high','low','close','volume')}
                    invalid=[key for key,value in record.items() if isinstance(value,float) and not math.isfinite(value)]
                    for key in invalid:record[key]=None
                    bars.append(dict(client=client,features=record,nonfinite_fields=invalid,
                                     relative_to_origin=(client['open_time']-pivot['origin_time']),
                                     feature_status='VALID' if record.get('formula_version')==3 and record.get('measurement_version')=='shared-v1' and record.get('measurement_config_id') else 'UNAVAILABLE_OR_INCOMPATIBLE',
                                     availability='DETECTION_CANDLE' if client['open_time']==pivot['confirmation_time'] else 'POST_CONFIRMATION' if client['open_time']>=pivot['known_time'] else 'BEFORE_CONFIRMATION'))
            return dict(version=VERSION,status='READY',symbol=symbol,timeframe=interval,pivot=pivot,source_id=source_id,bars=bars,
                        note='All stored feature columns; missing values remain null. Post-event bars are descriptive evidence, not inputs to a past prediction.')
    finally:
        if conn:conn.close()
