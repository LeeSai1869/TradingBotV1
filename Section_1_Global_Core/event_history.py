"""Read-only bounded research view of current committed features; no new runner."""
from collections import Counter
import json
import re
import time
from . import data_policy,regime_inputs
from .memory_storage.Storage import engine_store
from Section_5_Market_Regime.events import catalog


def history(symbol,interval,*,limit=250,before=None,now_ms=None):
    if not isinstance(symbol,str) or not re.fullmatch('[A-Z0-9]{2,30}USDT',symbol):raise ValueError('Choose a Binance USDT symbol')
    if interval not in catalog.TIMEFRAMES:raise ValueError('Choose 1m, 5m, 15m, 30m or 1h')
    if type(limit) is not int or not 1<=limit<=1000 or before is not None and (type(before) is not int or not 0<=before<=9223372036854775807):raise ValueError('Invalid history window')
    now=int(time.time()*1000) if now_ms is None else now_ms
    result=dict(symbol=symbol,timeframe=interval,catalog=catalog.definitions(),events=[],warnings=[],status='UNAVAILABLE',scanned=0,has_more=False,next_before=None,
                interpretation='Research observations only; candidate is not confirmed and no event is a BUY/SELL instruction.',availability='Reconstructed close-time knowledge; not actual historical publication times.')
    source=None
    with data_policy.snapshot_guard(timeout=1):
        try:
            source=regime_inputs.open_sources()
            meta=regime_inputs.source_metadata(source,symbol,interval,'initial',catalog.FIELDS)
            columns={row[1] for row in source.execute('PRAGMA table_info(features)')}
            if not set(catalog.FIELDS)<=columns:raise regime_inputs.InputsUnavailable('Event source fields are not available')
            cap=source.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
            if not cap:raise regime_inputs.InputsUnavailable('No committed feature checkpoint')
            bound=before if before is not None else now
            rows=source.execute('SELECT k.open_time,k.close_time,f.formula_version,'+','.join('f.'+field for field in catalog.FIELDS)+''' FROM raw.klines k LEFT JOIN features f ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time
                WHERE k.symbol=? AND k.interval=? AND k.open_time<? AND k.open_time<=? AND k.close_time<? AND k.close_time<? ORDER BY k.open_time DESC LIMIT ?''',(symbol,interval,bound,cap[0],now,bound,limit+1)).fetchall()
            identity=dict(venue='binance',market='spot',quote='USDT',symbol=symbol,timeframe=interval,source=meta,catalog_version=catalog.VERSION)
            identity['generation_id']=engine_store.digest(identity)
            result['source_identity']=identity
            previous=None;groups=[];warnings=Counter();has_seed=len(rows)>limit
            for index,row in enumerate(reversed(rows)):
                features=dict(zip(catalog.FIELDS,row[3:]));current=dict(open_time=row[0],close_time=row[1],features=features)
                valid=row[2]==3 and features.get('measurement_version')=='shared-v1' and bool(features.get('measurement_config_id'))
                if not valid:
                    previous=None;warnings['Missing/incompatible feature row; candidate comparisons reset']+=1
                    continue
                events,notes=catalog.project(identity,current,previous);previous=current
                if index==0 and has_seed:continue
                result['scanned']+=1;warnings.update(notes);groups.append((row[0],events))
            # Keep whole candle groups when bounding response size, preserving a
            # valid exclusive-open-time cursor for the next older page.
            chosen=[];count=0
            for group in reversed(groups):
                if chosen and count+len(group[1])>2000:break
                chosen.append(group);count+=len(group[1])
            chosen.reverse()
            result.update(status='READY',events=[event for _,events in chosen for event in events],warnings=[dict(message=key,count=value) for key,value in sorted(warnings.items())],
                has_more=has_seed or len(chosen)<len(groups),next_before=chosen[0][0] if chosen else min((r[0] for r in rows),default=None),
                window_start=chosen[0][0] if chosen else None,window_end=chosen[-1][0] if chosen else None,
                events_trimmed=len(chosen)<len(groups),seeded=has_seed)
        except regime_inputs.InputsUnavailable as error:result['reason']=str(error)
        finally:
            if source:source.close()
    return result
