"""Read-only, availability-aware descriptive study of committed direction states.

No optimization, decision changes, position simulation or profitability claim.
"""
from collections import Counter
import json
import math
import time
from . import aggregation_processor,data_policy,intelligence_audit,regime_inputs


def validate(horizons,cost_bps,since,until,split,max_rows,max_events,event_mode,availability,min_confidence,min_coverage):
    if not horizons or any(type(h) is not int or not 1<=h<=1000 for h in horizons):raise ValueError('Horizons must be 1–1000 bars')
    if isinstance(cost_bps,bool) or not isinstance(cost_bps,(int,float)) or not math.isfinite(cost_bps) or cost_bps<0:raise ValueError('Invalid round-trip costs')
    for value in (since,until,split):
        if value is not None and (type(value) is not int or value<0):raise ValueError('Times must be UTC milliseconds')
    if since is not None and until is not None and since>=until:raise ValueError('Since must precede until')
    if split is not None and (since is not None and split<=since or until is not None and split>=until):raise ValueError('Split must be inside the window')
    if type(max_rows) is not int or not 1<=max_rows<=1000000 or type(max_events) is not int or not 1<=max_events<=100000:raise ValueError('Invalid row/event budget')
    if event_mode not in ('TRANSITIONS','EVERY_CLOSE') or availability not in ('ACTUAL','RECONSTRUCTED_CLOSE'):raise ValueError('Invalid evaluation policy')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in (min_confidence,min_coverage)):raise ValueError('Evidence filters must be fractions')


def study(rows,source,symbol,interval,*,horizons=(1,3,6),cost_bps=12.,since=None,until=None,split=None,max_rows=100000,max_events=20000,event_mode='TRANSITIONS',availability='ACTUAL',min_confidence=0.,min_coverage=0.,now_ms=None):
    validate(horizons,cost_bps,since,until,split,max_rows,max_events,event_mode,availability,min_confidence,min_coverage)
    now=int(time.time()*1000) if now_ms is None else now_ms
    result=dict(rows_scanned=0,events=0,truncated=False,excluded={},groups=[],source_quality_counts={},sample_events=[],availability=availability)
    excluded=Counter();qualities=Counter();groups={};previous_sign=None
    for row in rows:
        if result['rows_scanned']>=max_rows:result['truncated']=True;break
        result['rows_scanned']+=1;qualities[row['data_quality']]+=1
        label=row['classification'].get('direction','UNKNOWN')
        sign=1 if label in ('BULLISH','STRONG_BULLISH') else -1 if label in ('BEARISH','STRONG_BEARISH') else 0
        if row['mode']!='CONFIRMED' or row['data_quality'] not in ('VALID','PARTIAL') or row['confirmation']['status']!='CONFIRMED' or not sign:
            previous_sign=None;excluded['UNCONFIRMED_OR_NONDIRECTIONAL']+=1;continue
        available=row['available_at'] if availability=='ACTUAL' else row['as_of']
        if type(available) is not int or type(row.get('available_at')) is not int or not row['candle_close_time']<row['as_of']<=row['available_at'] or available>now:
            previous_sign=None;excluded['INVALID_OR_FUTURE_PUBLICATION']+=1;continue
        if availability=='ACTUAL' and available>aggregation_processor.advance(row['candle_close_time']+1,interval)+30000:
            previous_sign=None;excluded['STALE_AT_PUBLICATION']+=1;continue
        changed=sign!=previous_sign;previous_sign=sign
        if since is not None and available<since or until is not None and available>=until:excluded['OUTSIDE_EVENT_WINDOW']+=1;continue
        if event_mode=='TRANSITIONS' and not changed:excluded['UNCHANGED_DIRECTION']+=1;continue
        if row['confidence']<min_confidence or row['coverage']<min_coverage:excluded['EVIDENCE_FILTER']+=1;continue
        if result['events']>=max_events:result['truncated']=True;break
        result['events']+=1
        period='earlier' if split is not None and available<split else 'later' if split is not None else 'full'
        # Actual publication inside a forming candle cannot buy at its old open.
        covering=source.execute('SELECT open_time,close_time FROM raw.klines WHERE symbol=? AND interval=? AND open_time<=? ORDER BY open_time DESC LIMIT 1',(symbol,interval,available)).fetchone()
        if not covering or not covering[0]<=available<=covering[1]+1:excluded['ENTRY_TIME_NOT_COVERED']+=1;continue
        entry_time=available if covering[0]==available else covering[1]+1
        prices=source.execute('SELECT open_time,close_time,open,close FROM raw.klines WHERE symbol=? AND interval=? AND open_time>=? AND close_time<? ORDER BY open_time LIMIT ?',(symbol,interval,entry_time,now,max(horizons))).fetchall()
        if not prices or prices[0][0]!=entry_time:excluded['ENTRY_GAP_OR_UNAVAILABLE']+=1;continue
        contiguous=[]
        for price in prices:
            if contiguous and price[0]!=contiguous[-1][1]+1:break
            if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0 for v in price[2:]):break
            contiguous.append(price)
        entry=prices[0][2]
        for h in horizons:
            if len(contiguous)<h:excluded['HORIZON_'+str(h)+'_GAP_OR_TAIL']+=1;continue
            last=contiguous[h-1];outcome_available=last[1]+1
            if until is not None and outcome_available>until:excluded['HORIZON_'+str(h)+'_END_PURGED']+=1;continue
            if period=='earlier' and outcome_available>split:excluded['HORIZON_'+str(h)+'_SPLIT_PURGED']+=1;continue
            gross=(last[3]/entry-1)*10000*sign;net=gross-cost_bps
            if not math.isfinite(gross):excluded['NONFINITE_OUTCOME']+=1;continue
            key=(period,label,h);stats=groups.setdefault(key,dict(period=period,direction=label,horizon_bars=h,observations=0,wins=0,gross_sum_bps=0.,net_sum_bps=0.))
            stats['observations']+=1;stats['wins']+=net>0;stats['gross_sum_bps']+=gross;stats['net_sum_bps']+=net
        if len(result['sample_events'])<10:result['sample_events'].append(dict(source_candle=row['candle_open_time'],classification=label,source_available=available,entry_open=entry_time,confidence=row['confidence'],coverage=row['coverage']))
    for key in sorted(groups):
        stats=groups[key];n=stats['observations'];stats.update(mean_gross_bps=stats.pop('gross_sum_bps')/n,mean_net_bps=stats.pop('net_sum_bps')/n,net_win_rate_pct=100*stats['wins']/n)
        result['groups'].append(stats)
    result.update(excluded=dict(excluded),source_quality_counts=dict(qualities))
    result['conclusion']='NO_ELIGIBLE_OUTCOMES' if not groups else 'DESCRIPTIVE_RESULTS_ONLY_NOT_A_VALIDATED_STRATEGY'
    return result


def evaluate(symbols=None,intervals=None,*,engine='BIAS',now_ms=None,**options):
    defaults=dict(horizons=(1,3,6),cost_bps=12.,since=None,until=None,split=None,max_rows=100000,max_events=20000,event_mode='TRANSITIONS',availability='ACTUAL',min_confidence=0.,min_coverage=0.)
    defaults.update(options);validate(**defaults)
    now=int(time.time()*1000) if now_ms is None else now_ms
    if engine not in aggregation_processor.registry():raise ValueError('Unknown connected engine')
    selected=sorted(set(symbols or data_policy.active_symbols()));timeframes=list(dict.fromkeys(intervals or data_policy.active_intervals()))
    if not set(timeframes)<=set(data_policy.INTERVALS):raise ValueError('Unregistered timeframe')
    report=dict(engine=engine,parameters=defaults,pairs=[],method='Directional state events; next eligible bar open; fixed-horizon closed spot-candle exits; no optimization or position simulation',
        caveats=['Scores are not win probabilities.','Transitions/every-close events and overlapping horizons are correlated.','Costs are assumed fixed round-trip bps, not observed execution fills.','Spot outcomes do not establish perpetual returns or include funding.','Reconstructed-close mode assumes causal original calculation; it is not actual publication history.','Chronological splits are descriptive; thresholds must be fixed before a genuinely untouched holdout.'])
    source=None;generation=aggregation_processor.generation(engine)
    with data_policy.snapshot_guard(timeout=1),intelligence_audit.reader() as conn:
        policy=data_policy.read()
        try:
            try:source=regime_inputs.open_sources()
            except regime_inputs.InputsUnavailable:pass
            from Section_4_Features.execution.components import current_signature
            desired=current_signature() if source else None
            for symbol in selected:
                for interval in timeframes:
                    pair=dict(symbol=symbol,timeframe=interval,status='MEMORY_UNAVAILABLE')
                    report['pairs'].append(pair)
                    if not data_policy.enabled(symbol,interval):pair['status']='DISABLED';continue
                    if conn is None or source is None:continue
                    run,status=intelligence_audit.select_run(conn,symbol,interval,engine,policy,generation,at=now)
                    if not run:pair['status']=status;continue
                    meta=run['metadata'];version=source.execute('SELECT signature,generation FROM feature_calculation_versions WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                    pending=source.execute('SELECT 1 FROM feature_replay_jobs WHERE symbol=? AND interval=?',(symbol,interval)).fetchone()
                    if not version or version[0]!=desired or str(version[1])!=meta['source_versions']['feature_generation'] or pending:pair['status']='FEATURE_REPLAY_PENDING_OR_CHANGED';continue
                    rows=(json.loads(row[0]) for row in conn.execute('SELECT payload FROM engine_results WHERE run_id=? ORDER BY candle_time',(run['run_id'],)))
                    pair.update(status='EVALUATED',run_id=run['run_id'],source_version=meta['engine_version'],source_config_hash=meta['config_hash'],source_input_signature=meta['input_signature'],
                        **study(rows,source,symbol,interval,now_ms=now,**defaults))
            return report
        finally:
            if source:source.close()
