"""Read-only row-level BTC 1h evidence for candidate/event sequence research."""
from contextlib import ExitStack
import json
import math
import sqlite3
import time
from . import data_policy,regime_inputs,pivot_research,intelligence_audit,aggregation_processor
from .pivot_context_audit import select_history_run
from .memory_storage.Storage import engine_store,adcn_store

VERSION='btc-hour-sequence-source-v1'
FRAMES=('1h','4h','1d')
FIELDS=('measurement_version','measurement_config_id','measurement_gap','candidate_pivot',
 'candidate_pivot_high_price','candidate_pivot_high_time','candidate_pivot_high_bar',
 'candidate_pivot_low_price','candidate_pivot_low_time','candidate_pivot_low_bar',
 'di_plus','di_minus','di_spread','di_direction','di_dominance','di_signed_spread','di_signed_dominance','adx',
 'rsi','atr','relative_volume','ema50','ema200','ema50_slope_atr','natr_pct','natr_percentile',
 'current_structure','current_swing_direction','regime_state','trend_state',
 'nearest_support','nearest_resistance','support_zone_low','support_zone_high','resistance_zone_low','resistance_zone_high',
 'nearest_buy_liquidity_price','nearest_sell_liquidity_price','liquidity_high_distance','liquidity_low_distance')
SCORES=('scalp_score','scalp_diplus_score','scalp_diminus_score','directional_movement_score','confluence_net_score','final_score')


def clean(value):
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    return value


def export(report,*,progress=None):
    if (report.get('version')!='pivot-moves-v1' or report.get('symbol')!='BTCUSDT' or report.get('timeframe')!='1h'
        or report['config']['threshold_pct']!=1 or report['config']['horizon_bars'] is not None):raise ValueError('Use the BTCUSDT 1h, 1%, next-opposite-pivot report')
    with ExitStack() as stack:
        stack.enter_context(data_policy.snapshot_guard(timeout=1))
        source=regime_inputs.open_sources();stack.callback(source.close)
        metadata,cap=pivot_research.metadata(source,'BTCUSDT','1h')
        if engine_store.digest(metadata)!=report['source_id'] or cap<report['coverage']['last']:raise ValueError('Feature generation/config differs from pivot report; regenerate the cohort instead of mixing generations')
        existing={r[1] for r in source.execute('PRAGMA table_info(features)')};fields=[f for f in FIELDS if f in existing]
        required=set(FIELDS[:10])|{'di_plus','di_minus','adx'}
        if not required<=set(fields):raise ValueError('Candidate/DI fields are not stored')
        sql='''SELECT k.open_time,k.close_time,k.open,k.high,k.low,k.close,k.volume,f.formula_version,'''+','.join('f.'+f for f in fields)+''' FROM raw.klines k LEFT JOIN features f
        ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time WHERE k.symbol=? AND k.interval=? AND k.open_time<=? AND k.close_time<? ORDER BY k.open_time'''
        rows=[]
        for values in source.execute(sql,('BTCUSDT','1h',report['coverage']['last'],report['observed_as_of'])):
            features=dict(zip(fields,values[8:]));valid=values[7]==3 and features.get('measurement_version')=='shared-v1' and bool(features.get('measurement_config_id'))
            rows.append(dict(**dict(zip(('open_time','close_time','open','high','low','close','volume'),values[:7])),features=clean(features),feature_valid=valid))
            if progress and len(rows)%10000==0:progress(dict(stage='candles',complete=len(rows)))
        if len(rows)!=report['coverage']['candles']:raise ValueError('Frozen candle coverage changed')
        scores={};score_status='UNAVAILABLE';score_fields=[]
        if adcn_store.DB_PATH.is_file():
            conn=sqlite3.connect(adcn_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=2);stack.callback(conn.close);conn.execute('BEGIN')
            columns={r[1] for r in conn.execute('PRAGMA table_info(decisions)')};score_fields=[k for k in SCORES if k in columns]
            if score_fields:
                for row in conn.execute('SELECT open_time,'+','.join(score_fields)+''' FROM decisions WHERE symbol=? AND interval=? AND open_time<=? ORDER BY open_time''',('BTCUSDT','1h',report['coverage']['last'])):
                    if any(v is not None for v in row[1:]):scores[str(row[0])]=clean(dict(zip(score_fields,row[1:])))
                score_status='ARCHIVED_FIELDS_ONLY_NOT_CURRENT_DI_PROBABILITY'
        engines=stack.enter_context(intelligence_audit.reader());registry=aggregation_processor.registry();history={};policy=data_policy.read();now=int(time.time()*1000)
        for frame in FRAMES:
            try:generation=regime_inputs.source_metadata(source,'BTCUSDT',frame,'initial',())['feature_generation']
            except regime_inputs.InputsUnavailable as error:generation=None;feature_error=str(error)
            for name in registry:
                key=frame+':'+name;item=dict(status='ENGINE_DATABASE_UNAVAILABLE',metadata=None,results={});history[key]=item
                if not engines:continue
                if generation is None:item['status']='FEATURES_UNAVAILABLE: '+feature_error;continue
                run,status=select_history_run(engines,'BTCUSDT',frame,name,policy,aggregation_processor.generation(name),at=now);item['status']=status
                if not run:continue
                meta=run['metadata']
                if meta['source_versions']['feature_generation']!=generation:item['status']='FEATURE_GENERATION_MISMATCH';continue
                item['metadata']=dict(meta,run_id=run['run_id'])
                step={'1h':3600000,'4h':14400000,'1d':86400000}[frame]
                for opened,payload in engines.execute('SELECT candle_time,payload FROM engine_results WHERE run_id=? AND candle_time<? ORDER BY candle_time',(run['run_id'],report['observed_as_of'])):
                    p=json.loads(payload)
                    if any(p.get(k)!=meta.get(k) for k in ('identity','engine','engine_version','config_hash','input_signature')):raise ValueError('Engine/run binding mismatch')
                    if (p.get('mode')!='CONFIRMED' or p.get('candle_open_time')!=opened or p.get('candle_close_time')!=opened+step-1
                        or p.get('as_of')!=opened+step or p['as_of']>report['observed_as_of']):continue
                    item['results'][str(opened)]=clean({k:p.get(k) for k in ('candle_open_time','candle_close_time','as_of','available_at','engine_version','classification','strength','confidence','coverage','data_quality','quality_flags','measurements','provenance')})
                if progress:progress(dict(stage='engine_history',scope=key,rows=len(item['results']),status=item['status']))
        return dict(version=VERSION,symbol='BTCUSDT',timeframe='1h',threshold_pct=1.,source_id=report['source_id'],observed_as_of=report['observed_as_of'],coverage=report['coverage'],
            source_metadata=metadata,missing_feature_columns=sorted(set(FIELDS)-existing),candles=clean(rows),pivots=report['cases'],engine_history=history,
            archived_scores=dict(status=score_status,fields=score_fields,rows=scores),
            definitions=dict(spread='abs(DI_plus-DI_minus), indicator points',signed_spread='DI_plus-DI_minus',dominance='(DI_plus-DI_minus)/(DI_plus+DI_minus), measurement not a probability',
                di_score='Raw DI values and stored archived score fields are separate; the current production DI rule does not compute a DI probability/final score',
                industry_bias='UNAVAILABLE: no sector/industry breadth feed in this export; Section5 BIAS is BTC instrument analytical bias',
                engine_availability='Current indexed compatible historical producer. Reconstructed close-time knowledge, not proof of original live publication; exact closed candles only. No current book backfill.'),
            interpretation='Complete frozen 1h closed-candle sequence with native pivots and all available versioned Section5 histories for 1h/4h/1d. Raw DI/candidate values are from stored measurements, not recreated from averaged reports. Score fields are archived/unverified and may be null. No live decisions, formulas, weights or checkpoints changed.')
