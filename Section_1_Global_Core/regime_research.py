"""Bounded on-demand Regime processing; not installed in the live scheduler."""
from dataclasses import asdict
import json
from pathlib import Path
import time
from . import data_policy,regime_inputs
from .memory_storage.Storage import engine_store
from Section_5_Market_Regime.engines import regime
from Section_5_Market_Regime import config as configuration


def catch_up(symbol,interval,*,limit=200,since=0,config=None,revision='initial',now_ms=None):
    if type(limit) is not int or not 1<=limit<=200:raise ValueError('Batch limit must be 1–200')
    if type(since) is not int or since<0:raise ValueError('Invalid history start')
    cfg=config or configuration.RegimeConfig()
    now=int(time.time()*1000) if now_ms is None else now_ms
    with data_policy.locked(timeout=2):
        if not data_policy.enabled(symbol,interval):return dict(symbol=symbol,timeframe=interval,status='paused',processed=0)
        source=None;store=None
        try:
            source=regime_inputs.open_sources()
            versions=regime_inputs.source_metadata(source,symbol,interval,revision)
            parameters=json.loads(versions['feature_parameters_json'])
            for key,expected in (('measurementERLength',cfg.er_length),('measurementRankLength',cfg.baseline_length),('measurementChangeLength',cfg.change_length)):
                if parameters[key]!=expected:raise regime_inputs.InputsUnavailable('Regime config must match Section 4 '+key)
            identity=dict(venue='binance',market_type='spot',instrument_id=symbol,symbol=symbol,timeframe=interval,
                dataset_generation=engine_store.digest(dict(raw_epoch=versions['raw_epoch'],revision=revision)))
            code=dict(regime=Path(regime.__file__).read_text(),config=Path(configuration.__file__).read_text())
            versions={**versions,'history_seed':str(since),'regime_source':engine_store.digest(code),'gateway_source':engine_store.digest(Path(regime_inputs.__file__).read_text())}
            signature=engine_store.digest(versions)
            metadata=dict(engine='REGIME',engine_version=regime.VERSION,state_schema_version=regime.VERSION,
                identity=identity,config=asdict(cfg),config_hash=cfg.fingerprint,input_signature=signature,
                source_versions=versions,history_start=since,source_archive=code,feature_parameters=parameters)
            run_id=engine_store.digest(metadata);store=engine_store.open_db();cursor,state=engine_store.load(store,run_id)
            snapshots,reason=regime_inputs.project(source,symbol,interval,max(cursor,since-1),limit,identity,signature,versions,parameters,now)
            batch=[]
            for snapshot in snapshots:
                result,state=regime.evaluate(snapshot,cfg,state);batch.append((snapshot,result))
            if batch:engine_store.commit_batch(store,metadata,cursor,batch,state)
            latest=engine_store.latest(store,run_id)
            return dict(symbol=symbol,timeframe=interval,run_id=run_id,status=reason or ('processed' if batch else 'caught up to committed feature prefix'),processed=len(batch),latest=latest)
        except regime_inputs.InputsUnavailable as error:
            return dict(symbol=symbol,timeframe=interval,status=str(error),processed=0)
        finally:
            if store:store.close()
            if source:source.close()


def diagnostics(run_id):
    conn=engine_store.open_db()
    try:
        primary={};quality={};directions={};volatility={};durations=[];duration=0;changes=0;primary_changes=0;last=None;count=0;pending=0
        for row in conn.execute('SELECT payload FROM engine_results WHERE run_id=? ORDER BY candle_time',(run_id,)):
            item=json.loads(row[0]);key=item['classification']['primary'];primary[key]=primary.get(key,0)+1
            value=item['data_quality'];quality[value]=quality.get(value,0)+1;current=item['classification']
            direction=current['direction'];directions[direction]=directions.get(direction,0)+1
            level=current['volatility_level'];volatility[level]=volatility.get(level,0)+1
            if item['confirmation']['status']=='PENDING':pending+=1
            if last is not None and current['primary']!=last['primary']:
                primary_changes+=1;durations.append(duration);duration=0
            duration+=1
            if last is not None and current!=last:changes+=1
            last=current;count+=1
        if duration:durations.append(duration)
        return dict(candles=count,primary_counts=primary,direction_counts=directions,volatility_counts=volatility,quality_counts=quality,
            classification_changes=changes,primary_changes=primary_changes,primary_changes_per_1000=1000*primary_changes/count if count else 0,
            mean_primary_duration_bars=sum(durations)/len(durations) if durations else None,pending_candles=pending)
    finally:conn.close()
