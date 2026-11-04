"""Core-owned Bias input join: existing same-candle public results, no reprocessing."""
from dataclasses import asdict
import json
from pathlib import Path
import time
from . import aggregation_processor,aggregation_store,data_policy,regime_inputs
from .memory_storage.Storage import engine_store
from Section_5_Market_Regime.engines import bias
from Section_5_Market_Regime.engines.bias_config import BiasConfig


def catch_up(symbol,interval,*,limit=200,since=0,config=None,revision='initial',now_ms=None,lock_timeout=2):
    if type(limit) is not int or not 1<=limit<=200:raise ValueError('Batch limit must be 1–200')
    if since is not None and (type(since) is not int or since<0):raise ValueError('Invalid history start')
    cfg=config or BiasConfig()
    if not isinstance(cfg,BiasConfig):raise TypeError('Use BiasConfig')
    now=int(time.time()*1000) if now_ms is None else now_ms
    def empty(reason):return dict(symbol=symbol,timeframe=interval,status=reason,processed=0,dependency_processed=0)
    with data_policy.locked(timeout=lock_timeout):
        if not data_policy.enabled(symbol,interval):return empty('paused')
        source=None;store=None
        try:
            source=regime_inputs.open_sources();store=aggregation_store.open_db()
            versions=regime_inputs.source_metadata(source,symbol,interval,revision,bias.FIELDS)
            parameters=json.loads(versions['feature_parameters_json']);epochs=json.loads(versions['raw_epoch'])
            bindings={};common_seed=0
            for name in bias.DEPENDENCIES:
                head=store.execute('SELECT generation,run_id,metadata FROM mtf_bindings WHERE symbol=? AND timeframe=? AND engine=? AND known_ms<=? ORDER BY known_ms DESC,id DESC LIMIT 1',(symbol,interval,name,now)).fetchone()
                if not head or not head['run_id']:return empty('Waiting for indexed '+name+' publication')
                if head['generation']!=aggregation_processor.generation(name):return empty('Waiting for current '+name+' producer generation')
                metadata=json.loads(head['metadata'])
                if metadata['raw_epoch']!=epochs or metadata['feature_generation']!=versions['feature_generation'] or metadata['revision']!=revision:return empty('Waiting for compatible '+name+' data generation')
                run=store.execute('SELECT metadata FROM engine_runs WHERE run_id=?',(head['run_id'],)).fetchone()
                if not run:return empty('Waiting for committed '+name+' run')
                child_meta=json.loads(run[0]);common_seed=max(common_seed,child_meta['history_start'])
                if child_meta['engine_version']!=bias.DEPENDENCIES[name]:return empty('Unsupported '+name+' public version')
                bindings[name]=dict(run_id=head['run_id'],generation=head['generation'],expected={k:child_meta[k] for k in ('engine_version','config_hash','input_signature')})
            identity=dict(venue='binance',market_type='spot',instrument_id=symbol,symbol=symbol,timeframe=interval,
                dataset_generation=engine_store.digest(dict(raw_epoch=versions['raw_epoch'],revision=revision)))
            versions={**versions,'bias_dependencies':engine_store.digest(bindings)}
            from Section_5_Market_Regime.engines import bias_config
            code=dict(engine=Path(bias.__file__).read_text(),config=Path(bias_config.__file__).read_text(),input_adapter=Path(__file__).read_text())
            requested=since
            if since is None:
                latest=source.execute('SELECT open_time FROM raw.klines WHERE symbol=? AND interval=? AND close_time<? ORDER BY open_time DESC LIMIT 1',(symbol,interval,now)).fetchone()
                cap=source.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                if latest and (not cap or cap[0]<latest[0]):return empty('Waiting for the latest closed candle feature checkpoint')
                seed_key=engine_store.digest(dict(symbol=symbol,timeframe=interval,versions=versions,code=engine_store.digest(code),config=cfg.fingerprint))
                saved=store.execute('SELECT candle_time FROM engine_live_seeds WHERE seed_key=?',(seed_key,)).fetchone()
                if saved:since=saved[0]
                else:
                    rows=source.execute("SELECT k.open_time FROM raw.klines k JOIN features f USING(symbol,interval,open_time) WHERE k.symbol=? AND k.interval=? AND k.close_time<? AND k.open_time<=? AND f.measurement_version='shared-v1' ORDER BY k.open_time DESC LIMIT 32",(symbol,interval,now,cap[0] if cap else -1)).fetchall()
                    if not rows:return empty('Waiting for recent committed measurements')
                    since=max(rows[-1][0],common_seed)
                    with store:store.execute('INSERT OR IGNORE INTO engine_live_seeds VALUES (?,?)',(seed_key,since))
            else:since=max(since,common_seed)
            versions={**versions,'history_seed':str(since),'regime_source':engine_store.digest(code),'gateway_source':engine_store.digest(Path(regime_inputs.__file__).read_text())}
            signature=engine_store.digest(versions)
            metadata=dict(engine='BIAS',engine_version=bias.VERSION,state_schema_version=bias.VERSION,identity=identity,config=asdict(cfg),config_hash=cfg.fingerprint,input_signature=signature,
                source_versions=versions,history_start=since,source_archive=code,feature_parameters=parameters)
            run_id=engine_store.digest(metadata);cursor,state=engine_store.load(store,run_id)
            snapshots,reason=regime_inputs.project(source,symbol,interval,max(cursor,since-1),limit,identity,signature,versions,parameters,now,bias.FIELDS,bias.UNITS)
            batch=[]
            for snapshot in snapshots:
                snapshot.pop('candle',None)  # Bias consumes public outputs, not raw OHLC.
                snapshot.update(dependencies={},dependency_expectations={},dependency_refs={})
                for name,binding in bindings.items():
                    row=store.execute('SELECT payload FROM engine_results WHERE run_id=? AND candle_time=?',(binding['run_id'],snapshot['candle_open_time'])).fetchone()
                    if not row:reason='Waiting for same-candle '+name+' checkpoint';break
                    result=json.loads(row[0])
                    if result['available_at']>now:reason='Waiting for '+name+' publication time';break
                    fields=('contract_version','engine','engine_version','identity','mode','candle_open_time','candle_close_time','as_of','available_at','classification','strength','coverage','confidence','confirmation','data_quality','config_hash','input_signature','provenance')
                    projected={key:result[key] for key in fields}
                    measurements=result.get('measurements',{})
                    if name=='LIQUIDITY':
                        observed=measurements.get('observed')
                        projected['measurements']=dict(observed={key:observed.get(key) for key in ('scope','association','flow_60s')} if isinstance(observed,dict) else None,evidence_contributions={'flow':measurements.get('evidence_contributions',{}).get('flow')})
                    elif name=='SENTIMENT':projected['measurements']={'scope':measurements.get('scope')}
                    elif name=='VOLATILITY':projected['measurements']={'dimension_confirmation':measurements.get('dimension_confirmation',{})}
                    snapshot['dependencies'][name]=projected;snapshot['dependency_expectations'][name]=binding['expected']
                    snapshot['dependency_refs'][name]=binding['run_id']+':'+str(result['candle_open_time'])+':'+engine_store.digest(engine_store.stable_result(result))
                if len(snapshot['dependencies'])!=len(bias.DEPENDENCIES):break
                result,state=bias.evaluate(snapshot,cfg,state);batch.append((snapshot,result))
            if batch:engine_store.commit_batch(store,metadata,cursor,batch,state)
            status=reason or ('processed' if batch else 'caught up to common committed dependency prefix')
            if requested is not None and requested<common_seed:status+='; starts at common recorded dependency seed'
            return dict(symbol=symbol,timeframe=interval,run_id=run_id,status=status,processed=len(batch),dependency_processed=0,latest=engine_store.latest(store,run_id))
        except regime_inputs.InputsUnavailable as error:return empty(str(error))
        finally:
            if source:source.close()
            if store:store.close()
