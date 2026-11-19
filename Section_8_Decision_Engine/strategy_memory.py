"""Paged read-only research access to stored candles, features, ADCN and engines."""
from collections import defaultdict
import json
import re
import time

from Section_1_Global_Core import regime_inputs, data_policy, intelligence_audit, analytical_history, aggregation_processor
from Section_1_Global_Core.memory_storage.Storage import adcn_store,features_store
from Section_4_Features.execution.components import current_signature
from .candle_calendar import FRAMES, end, latest_closed
from .strategy_analyzer import digest

ENGINES = analytical_history.ENGINES
CORE = {'measurement_version','measurement_config_id','measurement_gap','di_plus','di_minus','adx'}


def key(symbol,frame):
    return f'memory:{symbol}:{frame}'


def parse(value):
    parts=value.split(':')
    if len(parts)!=3 or parts[0]!='memory' or not re.fullmatch('[A-Z0-9]{2,30}USDT',parts[1]) or parts[2] not in FRAMES:
        raise ValueError('Choose a stored USDT coin and timeframe')
    return parts[1],parts[2]


def open_sources():
    c=regime_inputs.open_sources()
    if adcn_store.DB_PATH.is_file():
        c.execute('ATTACH DATABASE ? AS adcn',(adcn_store.DB_PATH.resolve().as_uri()+'?mode=ro',))
    return c


def columns(c,table='features'):
    if table=='adcn.decisions' and 'adcn' not in {r[1] for r in c.execute('PRAGMA database_list')}:
        return {}
    pragma='PRAGMA adcn.table_info(decisions)' if table=='adcn.decisions' else 'PRAGMA table_xinfo(features)'
    return {r[1]:r[2] for r in c.execute(pragma) if r[1] not in ('symbol','interval','open_time','formula_version')}


def version(c,symbol,frame):
    v=c.execute('SELECT signature,generation FROM feature_calculation_versions WHERE symbol=? AND interval=?',(symbol,frame)).fetchone()
    pending=bool(c.execute('SELECT 1 FROM feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,frame)).fetchone())
    policy=data_policy.read()
    return dict(signature=v[0] if v else None,generation=str(v[1]) if v else None,pending=pending,
                epochs=[policy['epochs'].get('symbol:'+symbol,0),policy['epochs'].get('interval:'+frame,0)])


def universe():
    c=open_sources()
    try:
        states={(s,f):t for s,f,t in c.execute('SELECT symbol,interval,last_open_time FROM feature_engine_state')}
        # Seek the composite index to the next symbol/timeframe, rather than
        # DISTINCT-scanning the entire candle archive or hiding raw-only coins.
        scopes=[];symbol=''
        while True:
            found=c.execute('SELECT symbol FROM raw.klines WHERE symbol>? ORDER BY symbol LIMIT 1',(symbol,)).fetchone()
            if not found:break
            symbol=found[0];frame=''
            while True:
                found=c.execute('SELECT interval FROM raw.klines WHERE symbol=? AND interval>? ORDER BY interval,open_time LIMIT 1',(symbol,frame)).fetchone()
                if not found:break
                frame=found[0]
                if frame in FRAMES and re.fullmatch('[A-Z0-9]{2,30}USDT',symbol):
                    scopes.append(dict(symbol=symbol,timeframe=frame,feature_through=states.get((symbol,frame))))
        return dict(symbols=sorted({p['symbol'] for p in scopes}),timeframes=[f for f in FRAMES if any(p['timeframe']==f for p in scopes)],
                    pairs=scopes,feature_columns=len(columns(c)),adcn_columns=len(columns(c,'adcn.decisions')))
    finally:c.close()


def _runs(c,symbol,frame,engine,at,feature_version):
    policy=data_policy.read();generation=aggregation_processor.generation(engine)
    result=[];status=[]
    for selector in (analytical_history.select,intelligence_audit.select_run):
        # History bindings are mutable heads, not a publication archive. A
        # refresh after the candle-page read began must not hide an existing
        # compatible prefix. Read the head as observed now; candle as_of is
        # still restricted to the frozen market cutoff by load().
        read_at=max(at,int(time.time()*1000))
        run,reason=selector(c,symbol,frame,engine,policy,generation,at=read_at)
        status.append(reason)
        if not run or run['run_id'] in {r['run_id'] for r in result}:continue
        if run['metadata'].get('source_versions',{}).get('feature_generation')!=feature_version['generation']:continue
        if feature_version['pending'] or feature_version['signature']!=current_signature():continue
        result.append(run)
    return result,' / '.join(status)


def _project(payload,paths):
    base={k:payload.get(k) for k in ('candle_open_time','candle_close_time','as_of','data_quality','classification')}
    for path in paths:
        if not path.startswith('output.'):continue
        names=path.split('.')[1:];v=payload
        for name in names:v=v.get(name) if isinstance(v,dict) else None
        dest=base
        for name in names[:-1]:dest=dest.setdefault(name,{})
        dest[names[-1]]=v
    return base


def load(symbol,frame,*,fields=None,since=None,until=None,limit=None,center=None,all_fields=False,
         all_context=False,include_pivots=False,warmup=2,now_ms=None,progress=None):
    parse(key(symbol,frame))
    now=int(time.time()*1000) if now_ms is None else now_ms
    cutoff=min(now,until) if until is not None else now
    c=open_sources()
    try:
        schema=columns(c);adcn_schema=columns(c,'adcn.decisions');v=version(c,symbol,frame)
        cap=c.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,frame)).fetchone()
        feature_cap=cap[0] if cap else -1
        first=c.execute('SELECT open_time FROM raw.klines WHERE symbol=? AND interval=? ORDER BY open_time LIMIT 1',(symbol,frame)).fetchone()
        last=c.execute('SELECT open_time,close_time FROM raw.klines WHERE symbol=? AND interval=? AND close_time<? ORDER BY open_time DESC LIMIT 1',(symbol,frame,cutoff)).fetchone()
        if not first or not last:raise ValueError(f'No closed candles are stored for {symbol} {frame}')
        cutoff=last[1]+1
        requested=set(fields or [])
        feature_fields=(set(schema) if all_fields else {f.split('.')[1] for f in requested if f.startswith('feature.')})|CORE
        if include_pivots:feature_fields|={'structure_events','structure_events_version','structure_event_status'}
        feature_fields=sorted(feature_fields&set(schema))
        adcn_fields=sorted(adcn_schema if all_fields else {f.split('.')[1] for f in requested if f.startswith('adcn.')}&set(adcn_schema))
        lower=first[0]
        if center is not None:
            r=c.execute('SELECT open_time FROM raw.klines WHERE symbol=? AND interval=? AND open_time<=? ORDER BY open_time DESC LIMIT 1 OFFSET 80',(symbol,frame,center)).fetchone()
            if r:lower=r[0]
        elif since is not None:
            r=c.execute('SELECT open_time FROM raw.klines WHERE symbol=? AND interval=? AND open_time<? ORDER BY open_time DESC LIMIT 1 OFFSET ?',(symbol,frame,since,warmup+2)).fetchone()
            if r:lower=r[0]
        elif limit:
            r=c.execute('SELECT open_time FROM raw.klines WHERE symbol=? AND interval=? AND open_time<=? ORDER BY open_time DESC LIMIT 1 OFFSET ?',(symbol,frame,last[0],limit-1)).fetchone()
            if r:lower=r[0]
        quote=lambda name:'"'+name.replace('"','""')+'"'
        select=['k.open_time','k.close_time','k.open','k.high','k.low','k.close','k.volume','f.formula_version']
        select+=[features_store.read_expression(f) for f in feature_fields]
        select+=['d.'+quote(f) for f in adcn_fields]
        join=' LEFT JOIN adcn.decisions d ON d.symbol=k.symbol AND d.interval=k.interval AND d.open_time=k.open_time' if adcn_fields else ''
        sql='SELECT '+','.join(select)+''' FROM raw.klines k LEFT JOIN features f ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time'''+join+''' WHERE k.symbol=? AND k.interval=? AND k.open_time>? AND k.open_time<=? AND k.close_time<? ORDER BY k.open_time LIMIT ?'''
        rows=[];after=lower-1;events={};current=v['signature']==current_signature() and not v['pending']
        c.rollback()
        while True:
            size=min(2048,limit-len(rows)) if limit else 2048
            if size<=0:break
            with data_policy.snapshot_guard(timeout=1):
                c.execute('BEGIN')
                try:
                    if version(c,symbol,frame)!=v:raise ValueError('Memory generation changed during the read; refresh and retry')
                    batch=c.execute(sql,(symbol,frame,after,last[0],cutoff,size)).fetchall()
                finally:c.rollback()
            for values in batch:
                f=dict(zip(feature_fields,values[8:8+len(feature_fields)]))
                valid=current and values[0]<=feature_cap and values[7]==3 and f.get('measurement_version')=='shared-v1' and bool(f.get('measurement_config_id'))
                row=dict(zip(('open_time','close_time','open','high','low','close','volume'),values[:7]))
                row.update(features=f,feature_valid=valid,adcn=dict(zip(adcn_fields,values[8+len(feature_fields):])),context={})
                rows.append(row)
                if include_pivots and valid and f.get('structure_events_version')=='structure-events-v1' and f.get('structure_event_status')=='READY':
                    from Section_1_Global_Core.pivot_research import pivot_events
                    for event in pivot_events(f.get('structure_events'),row['open_time'],row['close_time']):
                        if event['origin_time']>=lower:events[event['id']]=event
            if batch:after=batch[-1][0]
            if progress:progress(dict(stage='Reading memory candles',complete=len(rows),symbol=symbol,timeframe=frame))
            if len(batch)<size:break
        if not rows:raise ValueError('No stored candles in the requested date range')
        wanted=defaultdict(set)
        for name in requested:
            if name.startswith('context.'):
                parts=name.split('.');wanted[parts[1],parts[2]].add('.'.join(parts[3:]))
        if all_context:
            for engine in ENGINES:wanted[frame,engine].add('output')
        history={};statuses={};run_ids={}
        with intelligence_audit.reader() as engines:
            for (tf,engine),paths in wanted.items():
                scope=tf+':'+engine;item=history[scope]=dict(results={})
                if not engines:statuses[scope]='ENGINE_MEMORY_UNAVAILABLE';continue
                tf_version=version(c,symbol,tf)
                runs,statuses[scope]=_runs(engines,symbol,tf,engine,now,tf_version)
                run_ids[scope]=[run['run_id'] for run in runs]
                start=latest_closed(rows[0]['close_time']+1,tf);stop=latest_closed(rows[-1]['close_time']+1,tf)
                for run in runs:
                    cursor=start-1
                    while True:
                        batch=engines.execute('SELECT candle_time,payload FROM engine_results WHERE run_id=? AND candle_time>? AND candle_time<=? ORDER BY candle_time LIMIT 1024',(run['run_id'],cursor,stop)).fetchall()
                        engines.rollback()
                        for opened,raw in batch:
                            p=json.loads(raw);meta=run['metadata']
                            if any(p.get(k)!=meta.get(k) for k in ('identity','engine','engine_version','config_hash','input_signature')):continue
                            if p.get('mode')!='CONFIRMED' or p.get('candle_open_time')!=opened or p.get('candle_close_time')!=end(opened,tf)-1 or p.get('as_of')!=end(opened,tf) or p['as_of']>cutoff:continue
                            value={k:p.get(k) for k in ('candle_open_time','candle_close_time','as_of','data_quality','classification','measurements','strength','confidence','coverage')} if 'output' in paths else _project(p,paths)
                            item['results'].setdefault(str(opened),value)
                        if batch:cursor=batch[-1][0]
                        if len(batch)<1024:break
                if progress:progress(dict(stage='Reading stored '+scope,complete=len(item['results']),symbol=symbol,timeframe=frame))
        positions={r['open_time']:r for r in rows}
        for scope,item in history.items():
            tf,engine=scope.split(':')
            if tf==frame:
                for opened,p in item['results'].items():
                    if int(opened) in positions:positions[int(opened)]['context'][engine]=p
        if version(c,symbol,frame)!=v:raise ValueError('Memory changed during the read; refresh and retry')
        identity=dict(symbol=symbol,timeframe=frame,version=v,first=rows[0]['open_time'],last=rows[-1]['open_time'],fields=feature_fields,adcn_fields=adcn_fields,runs=run_ids)
        return dict(version='memory-candle-source-v1',symbol=symbol,timeframe=frame,source_id=digest(identity),observed_as_of=cutoff,
                    candles=rows,engine_history=history,native_pivots=sorted(events.values(),key=lambda p:(p['origin_time'],p['known_time'])),
                    exported_feature_columns=feature_fields,adcn_columns=adcn_fields,
                    memory=dict(first=first[0],last=last[0],feature_through=feature_cap,feature_current=current,context_status=statuses,engine_run_ids=run_ids,
                                feature_schema=schema,adcn_schema=adcn_schema,mode='READ_ONLY_STORED_VALUES_NO_CLASSIFIER_REPLAY'),
                    provenance='Read-only stored memory. Only requested strategy fields are loaded; incomplete historical values remain unavailable. No indicator or regime calculations are performed.')
    finally:c.close()


def metadata(symbol,frame):
    from .strategy_catalog import field_catalog
    source=load(symbol,frame,limit=64,all_fields=True,all_context=True)
    meta=field_catalog(source);meta.update(mode='memory',first=source['memory']['first'],last=source['observed_as_of'],memory=source['memory'])
    c=open_sources()
    try:meta['candles']=c.execute('SELECT COUNT(*) FROM raw.klines WHERE symbol=? AND interval=? AND close_time<?',(symbol,frame,source['observed_as_of'])).fetchone()[0]
    finally:c.close()
    for name,sql_type in source['memory']['adcn_schema'].items():
        values=[r['adcn'].get(name) for r in source['candles']];good=[v for v in values if v is not None]
        meta['fields'].append(dict(id='adcn.'+name,kind='string' if sql_type.upper()=='TEXT' else 'number',options=list(dict.fromkeys(v for v in good if isinstance(v,str)))[:30],group='Stored ADCN',sample_present=len(good),sample_total=len(values)))
    def walk(value,prefix):
        for name,v in value.items():
            if isinstance(v,dict):yield from walk(v,prefix+name+'.')
            elif v is None or type(v) in (str,bool,int,float):yield prefix+name,v
    # Peek other timeframes at their stored heads; do not load their histories
    # just to populate the editor's field picker.
    heads={}
    c=open_sources()
    try:
        frames=[r[0] for r in c.execute('SELECT interval FROM feature_engine_state WHERE symbol=?',(symbol,)) if r[0] in FRAMES]
        with intelligence_audit.reader() as engines:
            if engines:
                for tf in frames:
                    for engine in ENGINES:
                        runs,_=_runs(engines,symbol,tf,engine,int(time.time()*1000),version(c,symbol,tf))
                        c.rollback()
                        for run in reversed(runs):
                            found=engines.execute('SELECT payload FROM engine_results WHERE run_id=? ORDER BY candle_time DESC LIMIT 1',(run['run_id'],)).fetchone()
                            if found:
                                p=json.loads(found[0]);heads[tf,engine]=p;break
    finally:c.close()
    # Catalog every stored engine's scalar outputs and supported context frames.
    for tf in FRAMES:
        for engine in ENGINES:
            payloads=list(source['engine_history'].get(tf+':'+engine,{}).get('results',{}).values())
            samples=payloads[-1:] or ([heads[tf,engine]] if (tf,engine) in heads else [])
            if not samples:
                samples=[dict(classification=dict(primary=None,direction=None))] if engine=='REGIME' else [dict(classification=dict(direction=None))]
            known={f['id'] for f in meta['fields']}
            for payload in samples:
                for path,value in walk(payload.get('classification') or {},''):
                    field='context.'+tf+'.'+engine+'.'+path
                    if field not in known:
                        meta['fields'].append(dict(id=field,kind='number' if type(value) in (int,float) else 'boolean' if type(value) is bool else 'string',options=[value] if isinstance(value,str) else [],group=tf+' '+engine.title(),sample_present=int(value is not None),sample_total=1));known.add(field)
                for path,value in walk(payload,'output.'):
                    field='context.'+tf+'.'+engine+'.'+path
                    if field not in known:
                        meta['fields'].append(dict(id=field,kind='number' if type(value) in (int,float) else 'boolean' if type(value) is bool else 'string',options=[value] if isinstance(value,str) else [],group=tf+' '+engine.title()+' output',sample_present=int(value is not None),sample_total=1))
    for field in meta['fields']:
        if field['id'].startswith('feature.') and not field.get('sample_present'):
            sql_type=source['memory']['feature_schema'].get(field['id'].split('.')[1],'')
            field['kind']='string' if sql_type.upper()=='TEXT' else 'number'
    meta['note']='Reads current stored memory. All feature/ADCN columns are selectable; each replay loads only its fields. Context counts below cover the recent 64-candle preview, not all history. Missing historical outputs remain unavailable. ADCN fields are archived stored values.'
    return meta
