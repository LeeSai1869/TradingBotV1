"""Read-only frozen BTC 1h measurements and offline replay of existing Section 5 engines."""
import gzip,json,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
from Section_1_Global_Core import regime_inputs
from Section_1_Global_Core.memory_storage.Storage import engine_store
from Section_5_Market_Regime.engines import regime,trend,structure
from Section_4_Features.execution.components import desired_parameters

OUT=Path(__file__).parent
EXTRA=('di_spread','rsi','atr','relative_volume','nearest_support','nearest_resistance','natr_pct','ema50','ema200')

def export():
    modules={'STRUCTURE':structure,'TREND':trend,'REGIME':regime}
    fields=tuple(sorted(set(EXTRA).union(*(set(m.FIELDS) for m in modules.values()))))
    units={k:v for m in modules.values() for k,v in m.UNITS.items()}
    units.update({k:'research_only' for k in EXTRA if k not in units})
    source=regime_inputs.open_sources();now=int(time.time()*1000)
    try:
        metadata=regime_inputs.source_metadata(source,'BTCUSDT','1h','initial',fields)
        identity=dict(venue='binance',market_type='spot',instrument_id='BTCUSDT',symbol='BTCUSDT',timeframe='1h',dataset_generation=engine_store.digest(metadata))
        signature=engine_store.digest(dict(metadata=metadata,engines={name:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for name,m in modules.items()}))
        parameters=desired_parameters();states={name:None for name in modules};rows=[];after=-1;frozen=[]
        while True:
            snapshots,reason=regime_inputs.project(source,'BTCUSDT','1h',after,512,identity,signature,metadata,parameters,now,fields,units)
            frozen.extend((s['candle_open_time'],s['candle_close_time'],s['candle'],s['features']) for s in snapshots)
            if snapshots:after=snapshots[-1]['candle_open_time']
            print(json.dumps(dict(stage='freeze_measurements',rows=len(frozen),through=after,reason=reason)),flush=True)
            if reason or len(snapshots)<512:break
        # End database read snapshots before the longer pure-engine replay so
        # research never keeps source read locks through classifier execution.
        source.close();source=None
        for start,end,candle,f in frozen:
            s=dict(identity=identity,candle_open_time=start,candle_close_time=end,as_of=end+1,computed_at=now,closed=True,candle=candle,features=f,units=units,feature_parameters=parameters,field_validity={k:'VALID' if v is not None else 'UNAVAILABLE' for k,v in f.items()},field_available_at={k:end+1 for k in f},input_signature=signature,source_versions=metadata,quality_flags=['AVAILABILITY_RECONSTRUCTED'],provenance_mode='HISTORICAL_RECONSTRUCTION')
            results={}
            for name,m in modules.items():
                if name=='TREND':
                    dep=results['STRUCTURE'];s['dependencies']={'STRUCTURE':dep};s['dependency_refs']={'STRUCTURE':f'offline-structure:{start}'}
                    s['dependency_expectations']={'STRUCTURE':{k:dep[k] for k in ('engine_version','config_hash','input_signature')}}
                result,states[name]=m.evaluate(s,previous_state=states[name]);results[name]=result
            rows.append(dict(open_time=start,close_time=end,**candle,features={k:f.get(k) for k in EXTRA+('di_plus','di_minus','adx','ema50_slope_atr','measurement_gap','measurement_contiguous_bars','measurement_version')},context={name:{k:r[k] for k in ('classification','data_quality','coverage','confirmation','config_hash','engine_version')} for name,r in results.items()}))
            if len(rows)%10000==0:print(json.dumps(dict(stage='offline_classification',rows=len(rows))),flush=True)
        packet=dict(version='btc-di-spread-reversal-source-v1',observed_as_of=now,source_signature=signature,source_metadata=metadata,parameters=parameters,engines={name:dict(version=m.VERSION,source_sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()) for name,m in modules.items()},rows=rows,stop_reason=reason,provenance='Read-only stored current-generation spot measurements. Section 5 STRUCTURE -> TREND and REGIME reconstructed offline using current source definitions, original event lineage, sequential state and close-time information only. Not original live publication. No production classifications or decisions written.')
        encoded=json.dumps(packet,separators=(',',':'),allow_nan=False).encode();(OUT/'source.json.gz').write_bytes(gzip.compress(encoded,mtime=0))
        print(json.dumps(dict(candles=len(rows),first=rows[0]['open_time'] if rows else None,last=after,source_sha256=hashlib.sha256(encoded).hexdigest(),indicator_parameters={k:v for k,v in parameters.items() if 'rsi' in k.lower() or 'di' in k.lower() or 'adx' in k.lower()})),flush=True)
    finally:
        if source:source.close()
if __name__=='__main__':export()
