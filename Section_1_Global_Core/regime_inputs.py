"""Public Core snapshot gateway for the first independent analytical engine.

Reads a bounded raw/feature projection under the existing policy guard. No
indicator calculations or classifiers are implemented in this adapter.
"""
import sqlite3
import math
from . import data_policy
from .memory_storage.Storage import features_store,klines_store,engine_store
from Section_5_Market_Regime.engines.regime import FIELDS,UNITS

class InputsUnavailable(RuntimeError):pass


def source_metadata(conn,symbol,interval,revision):
    from Section_4_Features.execution.components import current_signature,catalog,desired_parameters
    if not symbol.endswith('USDT'):raise InputsUnavailable('Current adapter supports Binance USDT spot candles only')
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'features','feature_calculation_versions','feature_engine_state','feature_replay_jobs'}<=tables:raise InputsUnavailable('Waiting for committed Section 4 measurements')
    version=conn.execute('SELECT signature,generation FROM feature_calculation_versions WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
    if not version or version[0]!=current_signature():raise InputsUnavailable('Section 4 formula/config replay is incomplete')
    if conn.execute('SELECT 1 FROM feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval)).fetchone():raise InputsUnavailable('Waiting for bounded feature replay to finish')
    epochs=data_policy.read()['epochs'];raw_epoch=[epochs.get('symbol:'+symbol,0),epochs.get('interval:'+interval,0)]
    c=catalog();selected={c.final[c.export_inverse[field]] for field in FIELDS if field in c.export_inverse}
    while True:
        expanded=selected|{dependency for uid in selected for group in c.requires[uid].values() for dependency in group}|{dependency for uid in selected for dependency in c.fallback[uid]}
        if expanded==selected:break
        selected=expanded
    parameters=desired_parameters();used={key for uid in selected for key in c.by_id[uid].reads if key in parameters}
    projection=engine_store.digest(dict(sources={uid:c.source[uid] for uid in sorted(selected)},parameters={key:parameters[key] for key in sorted(used)}))
    return dict(feature_signature=projection,feature_generation=str(version[1]),raw_epoch=engine_store.encode(raw_epoch),operator_revision=revision,
        feature_parameters_json=engine_store.encode({key:parameters[key] for key in sorted(used)}))


def open_sources():
    if not features_store.DB_PATH.is_file() or not klines_store.DB_PATH.is_file():raise InputsUnavailable('Candle/feature database is not available')
    conn=sqlite3.connect(features_store.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
    try:
        conn.execute('ATTACH DATABASE ? AS raw',(klines_store.DB_PATH.resolve().as_uri()+'?mode=ro',))
        conn.execute('BEGIN')
        return conn
    except BaseException:conn.close();raise


def project(conn,symbol,interval,after,limit,identity,signature,source_versions,feature_parameters,now):
    existing={r[1] for r in conn.execute('PRAGMA table_info(features)')}
    if not set(FIELDS)<=existing:raise InputsUnavailable('Section 4 shared columns are not present')
    cap=conn.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
    if not cap:return [],'No committed feature prefix'
    sql='''SELECT k.open_time,k.close_time,k.open,k.high,k.low,k.close,
        f.open_time,f.formula_version,'''+','.join('f.'+field for field in FIELDS)+'''
        FROM raw.klines k LEFT JOIN features f ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time
        WHERE k.symbol=? AND k.interval=? AND k.open_time>? AND k.open_time<=? AND k.close_time<?
        ORDER BY k.open_time LIMIT ?'''
    rows=conn.execute(sql,(symbol,interval,after,cap[0],now,limit)).fetchall();result=[];reason=''
    for row in rows:
        if row[6] is None or row[7]!=3:reason='Missing feature row in committed history';break
        features=dict(zip(FIELDS,row[8:]))
        if features['measurement_version']!='shared-v1' or not features['measurement_config_id']:
            reason='Shared measurements are not replayed at '+str(row[0]);break
        for field in ('natr_baseline_degenerate','zero_price_movement','directional_movement_zero','measurement_gap'):
            if features[field] is not None:features[field]=bool(features[field]) if features[field] in (0,1) else None
        for field in ('natr_baseline_count','measurement_contiguous_bars'):
            if features[field] is not None:
                value=features[field];features[field]=int(value) if isinstance(value,(int,float)) and math.isfinite(value) and value>=0 and int(value)==value else None
        result.append(dict(identity=identity,candle_open_time=row[0],candle_close_time=row[1],as_of=row[1]+1,computed_at=now,closed=True,
            candle=dict(zip(('open','high','low','close'),row[2:6])),features=features,units=UNITS.copy(),feature_parameters=feature_parameters,
            field_validity={key:'VALID' if value is not None else 'UNAVAILABLE' for key,value in features.items()},
            field_available_at={key:row[1]+1 for key in FIELDS},input_signature=signature,source_versions=source_versions,
            quality_flags=['AVAILABILITY_RECONSTRUCTED'],provenance_mode='HISTORICAL_RECONSTRUCTION',
            market_metadata=dict(quote='USDT',calendar='24/7 UTC',candle_convention='unadjusted Binance spot klines')))
    return result,reason
