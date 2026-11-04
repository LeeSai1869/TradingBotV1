"""Bounded public-result indexing and as-of aggregation, separate from engines."""
from dataclasses import asdict
from datetime import datetime,timezone
from functools import lru_cache
import calendar
import json
from pathlib import Path
import time
from . import data_policy,aggregation_store,regime_inputs
from .memory_storage.Storage import engine_store
from Section_5_Market_Regime import aggregation
from Section_5_Market_Regime.aggregation_config import AggregationConfig

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'Section_5_Market_Regime/contracts/registry.json'


def registry():return {item['id']:item for item in json.loads(REGISTRY.read_text())['engines'] if item['status']=='RUNNER_CONNECTED'}


@lru_cache(maxsize=128)
def _file_digest(entries):return engine_store.digest({path:Path(path).read_text() for path,_,_ in entries})


def generation(engine):
    entries=registry();seen=set();visiting=set();paths={ROOT/'Section_1_Global_Core/regime_inputs.py'}
    def add(name):
        if name in visiting:raise ValueError('Cyclic analytical dependency registry')
        if name in seen:return
        if name not in entries:raise ValueError('Engine not runner-connected')
        visiting.add(name);entry=entries[name];paths.add(ROOT/(entry['proposed_module'].replace('.','/')+'.py'))
        if name=='REGIME':paths.add(ROOT/'Section_5_Market_Regime/config.py')
        elif name!='STRUCTURE':paths.add(ROOT/('Section_5_Market_Regime/engines/'+name.lower()+'_config.py'))
        if name=='SENTIMENT':paths.add(ROOT/'Section_1_Global_Core/sentiment_external.py')
        if name=='BIAS':paths.add(ROOT/'Section_1_Global_Core/bias_processor.py')
        if name in ('LIQUIDITY','SENTIMENT'):paths.add(ROOT/('Section_1_Global_Core/'+name.lower()+'_inputs.py'))
        for child in entry['dependencies']:add(child)
        visiting.remove(name);seen.add(name)
    add(engine)
    return _file_digest(tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in sorted(paths)))


def advance(boundary,interval):
    count=int(interval[:-1]);unit=interval[-1]
    if count<=0:raise ValueError('Invalid interval')
    if unit=='M':
        date=datetime.fromtimestamp(boundary/1000,timezone.utc);month=date.year*12+date.month-1+count;year,m=divmod(month,12)
        return int(date.replace(year=year,month=m+1,day=min(date.day,calendar.monthrange(year,m+1)[1])).timestamp()*1000)
    units={'s':1000,'m':60000,'h':3600000,'d':86400000,'w':604800000}
    return boundary+count*units[unit]


def observe(symbol,interval,engine,row,*,now_ms=None):
    """Index only default normal-runner publications, never select arbitrary runs."""
    now=int(time.time()*1000) if now_ms is None else now_ms
    conn=aggregation_store.open_db()
    try:
        latest=row.get('latest');run_id=row.get('run_id') if latest else None
        metadata=None;scope=None
        if run_id:
            stored=conn.execute('SELECT metadata FROM engine_runs WHERE run_id=?',(run_id,)).fetchone()
            if not stored:raise ValueError('Unknown engine run')
            meta=json.loads(stored[0])
            if meta['engine']!=engine or meta['identity']['symbol']!=symbol or meta['identity']['timeframe']!=interval or latest['input_signature']!=meta['input_signature']:raise ValueError('Mismatched publication binding')
            if now<latest['available_at']:raise ValueError('Cannot index a future publication')
            metadata={key:meta[key] for key in ('identity','engine_version','config_hash','input_signature')}
            metadata['raw_epoch']=json.loads(meta['source_versions']['raw_epoch']);metadata['feature_generation']=meta['source_versions']['feature_generation']
            metadata['revision']=meta['source_versions']['operator_revision']
        else:metadata=dict(reason=row.get('status','No committed output'))
        gen=generation(engine)
        with conn:
            previous=conn.execute('SELECT known_ms,generation,run_id,metadata FROM mtf_bindings WHERE symbol=? AND engine=? AND timeframe=? ORDER BY known_ms DESC,id DESC LIMIT 1',(symbol,engine,interval)).fetchone()
            if previous and now<previous[0]:raise ValueError('Aggregation observation clock moved backwards')
            encoded=engine_store.encode(metadata)
            if not previous or tuple(previous[1:])!=(gen,run_id,encoded):
                conn.execute('INSERT INTO mtf_bindings(symbol,timeframe,engine,known_ms,generation,run_id,metadata) VALUES (?,?,?,?,?,?,?)',(symbol,interval,engine,now,gen,run_id,encoded))
            if run_id:aggregation_store.source(conn,latest,run_id,now)
    finally:conn.close()


def refresh(symbol,engine,*,intervals=None,config=None,as_of=None,now_ms=None,force=False,deadline=None):
    cfg=config or AggregationConfig();now=int(time.time()*1000) if now_ms is None else now_ms;at=now if as_of is None else as_of
    if engine not in registry():raise ValueError('Unknown connected engine')
    if type(at) is not int or not 0<=at<=now:raise ValueError('Invalid as-of time')
    requested=set(data_policy.INTERVALS if intervals is None else intervals)
    if not requested<=set(data_policy.INTERVALS):raise ValueError('Unregistered timeframe')
    with data_policy.locked(timeout=.02):
        policy=data_policy.read();gen=generation(engine);conn=aggregation_store.open_db();source=None
        try:
            from .Symbols import symbols
            active_symbol=symbol not in policy['paused_coins'] and symbols.is_active(symbol)
            slots=[]
            try:source=regime_inputs.open_sources()
            except regime_inputs.InputsUnavailable:pass
            # Existing feature versions guard against old source generations; no
            # indicator processing or historical engine scan occurs here.
            from Section_4_Features.execution.components import current_signature
            desired=current_signature() if source else None
            for interval in data_policy.INTERVALS:
                if deadline is not None and time.monotonic()>=deadline:return dict(processed=0,status='Aggregation yielded to runner budget')
                enabled=active_symbol and interval in requested and policy['timeframes'].get(interval,'active')=='active'
                slot=dict(timeframe=interval,active=enabled,duration_ms=advance(at,interval)-at,result=None,result_ref=None,reason='DISABLED' if not enabled else 'MISSING')
                slots.append(slot)
                if not enabled:continue
                # Simulation explicitly uses today's compatible generation, not
                # a false claim that its reconstructed rows were published then.
                head_at=at if cfg.availability=='ACTUAL' else now
                head=conn.execute('SELECT generation,run_id,metadata FROM mtf_bindings WHERE symbol=? AND engine=? AND timeframe=? AND known_ms<=? ORDER BY known_ms DESC,id DESC LIMIT 1',(symbol,engine,interval,head_at)).fetchone()
                if not head:continue
                head_gen,run_id,encoded=head;meta=json.loads(encoded)
                if head_gen!=gen:slot['reason']='INCOMPATIBLE_PRODUCER_GENERATION';continue
                if not run_id:slot['reason']='ENGINE_UNAVAILABLE: '+meta['reason'];continue
                epoch=[policy['epochs'].get('symbol:'+symbol,0),policy['epochs'].get('interval:'+interval,0)]
                if meta['raw_epoch']!=epoch or meta['revision']!='initial':slot['reason']='INCOMPATIBLE_DATA_GENERATION';continue
                if source is None:slot['reason']='SOURCE_CHECKPOINT_UNAVAILABLE';continue
                version=source.execute('SELECT signature,generation FROM feature_calculation_versions WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                pending=source.execute('SELECT 1 FROM feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                if not version or version[0]!=desired or str(version[1])!=meta['feature_generation'] or pending:slot['reason']='SOURCE_REPLAY_PENDING_OR_CHANGED';continue
                if cfg.availability=='ACTUAL':
                    record=conn.execute('SELECT ref,payload FROM mtf_sources WHERE run_id=? AND observed_ms<=? ORDER BY observed_ms DESC,candle_time DESC LIMIT 1',(run_id,at)).fetchone()
                else:
                    # Index-bounded lookup: only one source candle can span at.
                    rows=conn.execute('SELECT payload FROM engine_results WHERE run_id=? AND candle_time<? ORDER BY candle_time DESC LIMIT 2',(run_id,at)).fetchall()
                    value=next((json.loads(row[0]) for row in rows if json.loads(row[0])['as_of']<=at),None)
                    if value:
                        ref=run_id+':'+str(value['candle_open_time'])+':'+engine_store.digest(engine_store.stable_result(value))
                        projected=aggregation_store.project_result(value)
                        record=(ref,engine_store.encode(projected))
                    else:record=None
                if not record:slot['reason']='NOT_YET_INDEXED_OR_AVAILABLE';continue
                result=json.loads(record[1])
                if cfg.availability=='ACTUAL':
                    cursor=conn.execute('SELECT cursor FROM engine_runs WHERE run_id=?',(run_id,)).fetchone()[0]
                    if cursor>result['candle_open_time']:
                        tip=conn.execute('SELECT payload FROM engine_results WHERE run_id=? AND candle_time=?',(run_id,cursor)).fetchone()
                        if tip and json.loads(tip[0])['available_at']<=at:
                            slot['reason']='NEWER_COMMITTED_CHECKPOINT_NOT_INDEXED';continue
                slot.update(result=result,result_ref=record[0],reason=None,scope=result.get('aggregation_scope'),fresh_until=advance(result['candle_close_time']+1,interval)+cfg.freshness_grace_ms,
                    expected={key:meta[key] for key in ('engine_version','config_hash','input_signature')})
                slot['expected']['dataset_generation']=meta['identity']['dataset_generation']
            identity=dict(venue='binance',market_type='spot',instrument_id=symbol,symbol=symbol,dataset_generation=engine_store.digest(dict(symbol_epoch=policy['epochs'].get('symbol:'+symbol,0),revision='initial')))
            code={name:(ROOT/name).read_text() for name in ('Section_5_Market_Regime/aggregation.py','Section_5_Market_Regime/aggregation_config.py','Section_1_Global_Core/aggregation_processor.py','Section_1_Global_Core/aggregation_store.py')}
            producer=dict(base=gen,aggregator=engine_store.digest(code),data_epochs={slot['timeframe']:policy['epochs'].get('interval:'+slot['timeframe'],0) for slot in slots if slot['active']})
            snapshot=dict(identity=identity,engine=engine,as_of=at,computed_at=now,timeframes=slots,producer_generation=producer)
            result=aggregation.evaluate(snapshot,cfg)
            metadata=dict(identity=identity,engine=engine,query_mode='LIVE' if as_of is None else 'AS_OF',timeframes=[(slot['timeframe'],slot['active']) for slot in slots],config=asdict(cfg),config_hash=cfg.fingerprint,aggregator_version=aggregation.VERSION,source_archive=code,producer=producer)
            if deadline is not None and time.monotonic()>=deadline:return dict(processed=0,status='Aggregation yielded to runner budget')
            with conn:result_id,inserted=aggregation_store.persist(conn,snapshot,result,metadata,force=force)
            return dict(processed=int(inserted),status='aggregation saved' if inserted else 'unchanged input set',result_id=result_id,latest=result)
        finally:
            if source:source.close()
            conn.close()
