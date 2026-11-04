"""Core-owned bounded analytical processing for runner and research commands."""
from dataclasses import asdict
import json
from pathlib import Path
import time
from . import data_policy,regime_inputs
from .memory_storage.Storage import engine_store
from Section_5_Market_Regime.engines import regime
from Section_5_Market_Regime import config as configuration


def catch_up(symbol,interval,*,limit=200,since=0,config=None,revision='initial',now_ms=None,lock_timeout=2,engine_name='REGIME'):
    if engine_name=='BIAS':
        from . import bias_processor
        return bias_processor.catch_up(symbol,interval,limit=limit,since=since,config=config,revision=revision,now_ms=now_ms,lock_timeout=lock_timeout)
    if type(limit) is not int or not 1<=limit<=200:raise ValueError('Batch limit must be 1–200')
    if since is not None and (type(since) is not int or since<0):raise ValueError('Invalid history start')
    from Section_5_Market_Regime.engines import structure,trend,trend_config,momentum,momentum_config,volatility,volatility_config,participation,participation_config,phase,phase_config,liquidity,liquidity_config,sentiment,sentiment_config
    if engine_name not in ('REGIME','STRUCTURE','TREND','MOMENTUM','VOLATILITY','PARTICIPATION','PHASE','LIQUIDITY','SENTIMENT'):raise ValueError('Unknown analytical engine')
    module={'REGIME':regime,'STRUCTURE':structure,'TREND':trend,'MOMENTUM':momentum,'VOLATILITY':volatility,'PARTICIPATION':participation,'PHASE':phase,'LIQUIDITY':liquidity,'SENTIMENT':sentiment}[engine_name]
    cfg=config or (sentiment_config.SentimentConfig() if engine_name=='SENTIMENT' else liquidity_config.LiquidityConfig() if engine_name=='LIQUIDITY' else phase_config.PhaseConfig() if engine_name=='PHASE' else participation_config.ParticipationConfig() if engine_name=='PARTICIPATION' else trend_config.TrendConfig() if engine_name=='TREND' else momentum_config.MomentumConfig() if engine_name=='MOMENTUM' else volatility_config.VolatilityConfig() if engine_name=='VOLATILITY' else configuration.RegimeConfig())
    cfg_values=structure.CONFIG if engine_name=='STRUCTURE' else asdict(cfg)
    cfg_hash=structure.CONFIG_HASH if engine_name=='STRUCTURE' else cfg.fingerprint
    dependency_processed=0
    if engine_name=='TREND' and limit<2:return dict(symbol=symbol,timeframe=interval,status='Trend requires a budget of at least two rows for dependency work',processed=0)
    if engine_name=='PHASE' and limit<5:return dict(symbol=symbol,timeframe=interval,status='Phase requires a budget of at least five rows for dependency work',processed=0)
    now=int(time.time()*1000) if now_ms is None else now_ms
    with data_policy.locked(timeout=lock_timeout):
        if not data_policy.enabled(symbol,interval):return dict(symbol=symbol,timeframe=interval,status='paused',processed=0)
        source=None;store=None;observation_reader=None;observations=None
        try:
            source=regime_inputs.open_sources()
            versions=regime_inputs.source_metadata(source,symbol,interval,revision,module.FIELDS)
            parameters=json.loads(versions['feature_parameters_json'])
            if engine_name=='REGIME':
                for key,expected in (('measurementERLength',cfg.er_length),('measurementRankLength',cfg.baseline_length),('measurementChangeLength',cfg.change_length)):
                    if parameters[key]!=expected:raise regime_inputs.InputsUnavailable('Regime config must match Section 4 '+key)
            if engine_name=='MOMENTUM' and parameters['measurementMomentumLength']!=cfg.momentum_length:raise regime_inputs.InputsUnavailable('Momentum config must match Section 4 measurementMomentumLength')
            if engine_name=='VOLATILITY':
                for key,expected in (('measurementRankLength',cfg.baseline_length),('measurementChangeLength',cfg.change_length),('measurementReturnLength',cfg.return_length)):
                    if parameters[key]!=expected:raise regime_inputs.InputsUnavailable('Volatility config must match Section 4 '+key)
            if engine_name=='TREND':
                for key,expected in (('measurementERLength',cfg.er_length),('measurementSlopeLength',cfg.slope_length),('measurementReturnLength',cfg.consistency_length)):
                    if parameters[key]!=expected:raise regime_inputs.InputsUnavailable('Trend config must match Section 4 '+key)
                dependency_versions=regime_inputs.source_metadata(source,symbol,interval,revision,structure.FIELDS)
                versions={**versions,'structure_dependency':engine_store.digest(dict(sources=dependency_versions,code=Path(structure.__file__).read_text(),config=structure.CONFIG_HASH))}
            if engine_name=='PHASE':
                for key,expected in (('rangeLookback',cfg.range_length),('measurementERLength',cfg.er_length),('measurementChangeLength',cfg.change_length)):
                    if parameters[key]!=expected:raise regime_inputs.InputsUnavailable('Phase config must match Section 4 '+key)
                # Include direct and transitive dependency implementations/configs
                # in the parent generation; actual result references stay per-row.
                dependencies={}
                for name,child,child_config in (('TREND',trend,trend_config),('STRUCTURE',structure,None),('PARTICIPATION',participation,participation_config)):
                    dependencies[name]=dict(sources=regime_inputs.source_metadata(source,symbol,interval,revision,child.FIELDS),code=Path(child.__file__).read_text(),config=Path(child_config.__file__).read_text() if child_config else structure.CONFIG_HASH)
                versions={**versions,'phase_dependencies':engine_store.digest(dependencies)}
            if engine_name=='LIQUIDITY':
                if parameters['liquidityLookback']!=cfg.liquidity_length:raise regime_inputs.InputsUnavailable('Liquidity config must match Section 4 liquidityLookback')
            identity=dict(venue='binance',market_type='spot',instrument_id=symbol,symbol=symbol,timeframe=interval,
                dataset_generation=engine_store.digest(dict(raw_epoch=versions['raw_epoch'],revision=revision)))
            code=dict(engine=Path(module.__file__).read_text(),config=Path(configuration.__file__).read_text() if engine_name=='REGIME' else Path(trend_config.__file__).read_text() if engine_name=='TREND' else Path(momentum_config.__file__).read_text() if engine_name=='MOMENTUM' else Path(volatility_config.__file__).read_text() if engine_name=='VOLATILITY' else Path(participation_config.__file__).read_text() if engine_name=='PARTICIPATION' else Path(phase_config.__file__).read_text() if engine_name=='PHASE' else Path(liquidity_config.__file__).read_text() if engine_name=='LIQUIDITY' else Path(sentiment_config.__file__).read_text() if engine_name=='SENTIMENT' else '')
            if engine_name=='LIQUIDITY':
                from . import liquidity_inputs
                code['observations']=Path(liquidity_inputs.__file__).read_text()
                observation_reader=liquidity_inputs.reader();observations=observation_reader.__enter__()
            if engine_name=='SENTIMENT':
                from . import sentiment_inputs
                code['observations']=Path(sentiment_inputs.__file__).read_text()
                observation_reader=sentiment_inputs.reader();observations=observation_reader.__enter__()
            store=engine_store.open_db()
            if since is None:
                cap=source.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                latest_closed=source.execute('SELECT open_time FROM raw.klines WHERE symbol=? AND interval=? AND close_time<? ORDER BY open_time DESC LIMIT 1',(symbol,interval,now)).fetchone()
                if latest_closed and (not cap or cap[0]<latest_closed[0]):raise regime_inputs.InputsUnavailable('Waiting for the latest closed candle feature checkpoint')
                seed_key=engine_store.digest(dict(symbol=symbol,timeframe=interval,versions=versions,code=engine_store.digest(code),config=cfg_hash))
                saved=store.execute('SELECT candle_time FROM engine_live_seeds WHERE seed_key=?',(seed_key,)).fetchone()
                if saved:since=saved[0]
                else:
                    rows=source.execute("SELECT k.open_time FROM raw.klines k JOIN features f USING(symbol,interval,open_time) WHERE k.symbol=? AND k.interval=? AND k.close_time<? AND k.open_time<=(SELECT last_open_time FROM feature_engine_state WHERE symbol=k.symbol AND interval=k.interval) AND f.measurement_version='shared-v1' ORDER BY k.open_time DESC LIMIT 32",(symbol,interval,now)).fetchall()
                    if not rows:raise regime_inputs.InputsUnavailable('Waiting for recent committed measurements')
                    since=rows[-1][0]
                    with store:store.execute('INSERT OR IGNORE INTO engine_live_seeds VALUES (?,?)',(seed_key,since))
            versions={**versions,'history_seed':str(since),'regime_source':engine_store.digest(code),'gateway_source':engine_store.digest(Path(regime_inputs.__file__).read_text())}
            signature=engine_store.digest(versions)
            metadata=dict(engine=engine_name,engine_version=module.VERSION,state_schema_version=module.VERSION,
                identity=identity,config=cfg_values,config_hash=cfg_hash,input_signature=signature,
                source_versions=versions,history_start=since,source_archive=code,feature_parameters=parameters)
            run_id=engine_store.digest(metadata);cursor,state=engine_store.load(store,run_id)
            snapshots,reason=regime_inputs.project(source,symbol,interval,max(cursor,since-1),limit//5 if engine_name=='PHASE' else limit//2 if engine_name=='TREND' else limit,identity,signature,versions,parameters,now,module.FIELDS,module.UNITS)
            dependency_run=None
            if engine_name=='TREND' and snapshots:
                dependency=catch_up(symbol,interval,limit=limit//2,since=since,revision=revision,now_ms=now,lock_timeout=lock_timeout,engine_name='STRUCTURE')
                dependency_processed=dependency['processed'];dependency_run=dependency.get('run_id')
                if not dependency_run:return dict(symbol=symbol,timeframe=interval,status='Waiting for Structure: '+dependency['status'],processed=0,dependency_processed=dependency_processed)
            phase_runs={}
            if engine_name=='PHASE' and snapshots:
                quantum=limit//5
                # Includes Trend's nested Structure work. All child rows count
                # against this same turn, rather than tripling runner budgets.
                for name,quota in (('STRUCTURE',quantum),('TREND',2*quantum),('PARTICIPATION',quantum)):
                    child=catch_up(symbol,interval,limit=quota,since=since,revision=revision,now_ms=now,lock_timeout=lock_timeout,engine_name=name)
                    dependency_processed+=child['processed']+child.get('dependency_processed',0)
                    if not child.get('run_id'):
                        return dict(symbol=symbol,timeframe=interval,status='Waiting for '+name+': '+child['status'],processed=0,dependency_processed=dependency_processed)
                    phase_runs[name]=child['run_id']
            batch=[]
            for snapshot in snapshots:
                if engine_name=='TREND':
                    record=store.execute('SELECT payload FROM engine_results WHERE run_id=? AND candle_time=?',(dependency_run,snapshot['candle_open_time'])).fetchone()
                    if not record:reason='Waiting for same-candle Structure checkpoint';break
                    dependency_result=json.loads(record[0])
                    fields=('engine','engine_version','identity','mode','candle_open_time','candle_close_time','as_of','available_at','classification','coverage','data_quality','config_hash','input_signature','provenance')
                    snapshot['dependencies']={'STRUCTURE':{key:dependency_result[key] for key in fields}}
                    dependency_metadata=json.loads(store.execute('SELECT metadata FROM engine_runs WHERE run_id=?',(dependency_run,)).fetchone()[0])
                    snapshot['dependency_expectations']={'STRUCTURE':{key:dependency_metadata[key] for key in ('engine_version','config_hash','input_signature')}}
                    snapshot['dependency_refs']={'STRUCTURE':dependency_run+':'+str(snapshot['candle_open_time'])+':'+engine_store.digest(engine_store.stable_result(dependency_result))}

                if engine_name=='PHASE':
                    snapshot.update(dependencies={},dependency_expectations={},dependency_refs={})
                    for name,child_run in phase_runs.items():
                        record=store.execute('SELECT payload FROM engine_results WHERE run_id=? AND candle_time=?',(child_run,snapshot['candle_open_time'])).fetchone()
                        if not record:
                            reason='Waiting for same-candle '+name+' checkpoint'
                            break
                        child_result=json.loads(record[0])
                        fields=('engine','engine_version','identity','mode','candle_open_time','candle_close_time','as_of','available_at','classification','strength','confirmation','coverage','data_quality','config_hash','input_signature','provenance')
                        projection={key:child_result[key] for key in fields}
                        if name=='STRUCTURE':projection['measurements']={'new_events':child_result['measurements']['new_events']}
                        snapshot['dependencies'][name]=projection
                        child_metadata=json.loads(store.execute('SELECT metadata FROM engine_runs WHERE run_id=?',(child_run,)).fetchone()[0])
                        snapshot['dependency_expectations'][name]={key:child_metadata[key] for key in ('engine_version','config_hash','input_signature')}
                        snapshot['dependency_refs'][name]=child_run+':'+str(snapshot['candle_open_time'])+':'+engine_store.digest(engine_store.stable_result(child_result))
                    if len(snapshot['dependencies'])!=len(phase.DEPENDENCIES):break

                if engine_name=='LIQUIDITY':snapshot['observations']=liquidity_inputs.project(observations,snapshot,cfg)
                if engine_name=='SENTIMENT':snapshot['sentiment_sources']=sentiment_inputs.project(observations,snapshot)
                result,state=module.evaluate(snapshot,None if engine_name=='STRUCTURE' else cfg,state);batch.append((snapshot,result))
            if batch:engine_store.commit_batch(store,metadata,cursor,batch,state)
            latest=engine_store.latest(store,run_id)
            return dict(symbol=symbol,timeframe=interval,run_id=run_id,status=reason or ('processed' if batch else 'caught up to committed feature prefix'),processed=len(batch),dependency_processed=dependency_processed,latest=latest)
        except regime_inputs.InputsUnavailable as error:
            return dict(symbol=symbol,timeframe=interval,status=str(error),processed=0,dependency_processed=dependency_processed)
        finally:
            if store:store.close()
            if source:source.close()
            if observation_reader:observation_reader.__exit__(None,None,None)


def diagnostics(run_id):
    conn=engine_store.open_db()
    try:
        primary={};quality={};directions={};volatility={};durations=[];duration=0;changes=0;primary_changes=0;last=None;count=0;pending=0;phase_development={};phase_events={};liquidity_dimensions={};liquidity_events={};sentiment_dimensions={};sentiment_events={}
        for row in conn.execute('SELECT payload FROM engine_results WHERE run_id=? ORDER BY candle_time',(run_id,)):
            item=json.loads(row[0]);key=item['classification'].get('primary',item['classification'].get('active_structure',item['classification'].get('direction',item['classification'].get('level',item['classification'].get('activity',item['classification'].get('phase','UNKNOWN'))))));primary[key]=primary.get(key,0)+1
            value=item['data_quality'];quality[value]=quality.get(value,0)+1;current=item['classification']
            if 'direction' in current:
                direction=current['direction'];directions[direction]=directions.get(direction,0)+1
            level=current.get('volatility_level',current.get('level',item['classification'].get('activity',item['classification'].get('phase','UNKNOWN'))));volatility[level]=volatility.get(level,0)+1
            if item['engine']=='LIQUIDITY':
                for dimension,value in current.items():
                    counts=liquidity_dimensions.setdefault(dimension,{})
                    counts[value]=counts.get(value,0)+1
                for event in item['measurements']['new_events']:
                    kind=event['type'];liquidity_events[kind]=liquidity_events.get(kind,0)+1
            if item['engine']=='SENTIMENT':
                for dimension,value in current.items():
                    counts=sentiment_dimensions.setdefault(dimension,{})
                    counts[value]=counts.get(value,0)+1
                for event in item['measurements']['new_events']:
                    kind=event['type'];sentiment_events[kind]=sentiment_events.get(kind,0)+1
            if item['engine']=='PHASE':
                development=current['development'];phase_development[development]=phase_development.get(development,0)+1
                for event in item['measurements']['new_events']:
                    kind=event['type'];phase_events[kind]=phase_events.get(kind,0)+1
            if item['confirmation']['status']=='PENDING':pending+=1
            if last is not None and current.get('primary',current.get('active_structure',current.get('direction',current.get('level',current.get('activity',current.get('phase'))))))!=last.get('primary',last.get('active_structure',last.get('direction',last.get('level',last.get('activity',last.get('phase')))))):
                primary_changes+=1;durations.append(duration);duration=0
            duration+=1
            if last is not None and current!=last:changes+=1
            last=current;count+=1
        if duration:durations.append(duration)
        report=dict(candles=count,primary_counts=primary,direction_counts=directions,volatility_counts=volatility,quality_counts=quality,
            classification_changes=changes,primary_changes=primary_changes,primary_changes_per_1000=1000*primary_changes/count if count else 0,
            mean_primary_duration_bars=sum(durations)/len(durations) if durations else None,pending_candles=pending)
        if last is not None and 'primary' not in last:
            for key in ('primary_counts','primary_changes','primary_changes_per_1000','mean_primary_duration_bars'):
                report[key.replace('primary','phase' if item['engine']=='PHASE' else 'activity' if item['engine']=='PARTICIPATION' else 'level' if item['engine']=='VOLATILITY' else 'structure' if 'active_structure' in last else 'momentum' if item['engine']=='MOMENTUM' else 'bias' if item['engine']=='BIAS' else 'trend')]=report.pop(key)
        if last is not None and item['engine'] in ('VOLATILITY','PARTICIPATION','PHASE','LIQUIDITY','SENTIMENT'):report.pop('direction_counts',None)
        if last is not None and item['engine'] in ('PARTICIPATION','PHASE','LIQUIDITY','SENTIMENT','BIAS'):report.pop('volatility_counts',None)
        if last is not None and item['engine']=='PHASE':report.update(development_counts=phase_development,event_counts=phase_events)
        if last is not None and item['engine']=='LIQUIDITY':
            for key in ('trend_counts','trend_changes','trend_changes_per_1000','mean_trend_duration_bars','direction_counts','volatility_counts'):report.pop(key,None)
            report.update(dimension_counts=liquidity_dimensions,event_counts=liquidity_events)
        if last is not None and item['engine']=='SENTIMENT':
            for key in ('trend_counts','trend_changes','trend_changes_per_1000','mean_trend_duration_bars','direction_counts','volatility_counts'):report.pop(key,None)
            report.update(dimension_counts=sentiment_dimensions,event_counts=sentiment_events)
        return report
    finally:conn.close()
