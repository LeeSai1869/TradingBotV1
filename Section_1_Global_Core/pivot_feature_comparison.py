"""All-pivot feature trajectories from existing measurements; bounded numeric batches.

NumPy is an optional research dependency, imported only when running the study.
No live engine, score, feature formula or memory checkpoint is changed.
"""
from collections import Counter
from datetime import datetime,timezone
import json
import math
from . import pivot_research

VERSION='all-pivot-features-v1'
CATEGORIES=('regime_state','trend_state','current_structure','current_swing_direction','swing_direction','transition_state','energy_state','control_state')
EXCLUDE={'open_time','formula_version'}


def outcomes(report,threshold=1.):
    """Relabel observed extrema without inventing the first-touch timestamp."""
    if report.get('version')!='pivot-moves-v1' or report.get('config',{}).get('horizon_bars') is not None:raise ValueError('Requires next-opposite-pivot study v1')
    if not 0<threshold<=100:raise ValueError('Invalid benchmark')
    result={}
    for case in report['cases']:
        move=case['origin'];maximum=move.get('max_favorable_pct')
        status='HIT' if isinstance(maximum,(int,float)) and math.isfinite(maximum) and maximum>=threshold-1e-10 else 'NO_HIT' if move.get('complete') else 'CENSORED'
        result[case['id']]=status
    if len(result)!=len(report['cases']):raise ValueError('Duplicate pivot IDs')
    return result


def memberships(cases,labels):
    groups={}
    for index,case in enumerate(cases):
        side=case['side'];outcome=labels[case['id']]
        year=str(datetime.fromtimestamp(case['pivot']['origin_time']/1000,timezone.utc).year)
        for period in ('ALL',year):groups.setdefault((side,outcome,period),[]).append(index)
    return groups


def exact_indices(times,origins,offsets,step):
    import numpy as np
    targets=np.asarray(origins,dtype=np.int64)[:,None]+np.asarray(offsets,dtype=np.int64)[None,:]*step
    idx=np.searchsorted(times,targets);bounded=np.minimum(idx,max(0,len(times)-1))
    valid=(idx<len(times)) & (times[bounded]==targets) if len(times) else np.zeros(idx.shape,dtype=bool)
    return bounded.astype(np.int32),valid


def aggregate(values,indices,valid,groups):
    """Population moments per offset; missing cells never become zero evidence."""
    import numpy as np
    output=[]
    for key,members in sorted(groups.items()):
        rows=np.asarray(members,dtype=np.int32);counts=[];means=[];stds=[];mins=[];maxs=[]
        for offset in range(indices.shape[1]):
            v=values[indices[rows,offset]].copy();v[~valid[rows,offset]]=np.nan
            good=np.isfinite(v);count=good.sum(axis=0);safe=np.where(good,v,0.)
            mean=np.divide(safe.sum(axis=0),count,out=np.full(values.shape[1],np.nan),where=count>0)
            # Center before squaring, avoiding cancellation for large price/time fields.
            delta=np.where(good,v-mean,0.);variance=np.divide((delta*delta).sum(axis=0),count,out=np.full(values.shape[1],np.nan),where=count>0)
            counts.append(count.tolist());means.append(mean.tolist());stds.append(np.sqrt(variance).tolist())
            mins.append(np.where(count>0,np.where(good,v,np.inf).min(axis=0),np.nan).tolist())
            maxs.append(np.where(count>0,np.where(good,v,-np.inf).max(axis=0),np.nan).tolist())
        output.append(dict(side=key[0],outcome=key[1],year=key[2],pivots=len(members),count=counts,mean=means,stddev=stds,minimum=mins,maximum=maxs))
    return output


def derived(source,report,times):
    import numpy as np
    fields=('open','high','low','close','volume','atr','di_plus','di_minus')
    sql='''SELECT k.open_time,k.open,k.high,k.low,k.close,k.volume,f.atr,f.di_plus,f.di_minus,f.formula_version,f.measurement_version,f.measurement_config_id
        FROM raw.klines k LEFT JOIN features f ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time
        WHERE k.symbol=? AND k.interval=? AND k.open_time<=? AND k.close_time<? ORDER BY k.open_time'''
    rows=source.execute(sql,(report['symbol'],report['timeframe'],report['coverage']['last'],report['observed_as_of']))
    data=np.full((len(times),len(fields)),np.nan)
    for i,row in enumerate(rows):
        data[i,:5]=[v if isinstance(v,(int,float)) else np.nan for v in row[1:6]]
        if row[9]==3 and row[10]=='shared-v1' and row[11]:data[i,5:]=[v if isinstance(v,(int,float)) else np.nan for v in row[6:9]]
    o,h,l,c,volume,atr,plus,minus=data.T;span=h-l
    divide=lambda n,d:np.divide(n,d,out=np.full(len(times),np.nan),where=np.isfinite(d)&(d>0))
    result=dict(raw_open=o,raw_high=h,raw_low=l,raw_close=c,raw_volume=volume,
        candle_body_fraction=divide(abs(c-o),span),lower_wick_fraction=divide(np.minimum(o,c)-l,span),
        upper_wick_fraction=divide(h-np.maximum(o,c),span),close_position=divide(c-l,span),
        range_in_atr=divide(span,atr),atr_pct_of_close=100*divide(atr,c),body_in_atr=divide(abs(c-o),atr),
        candle_return_pct=100*divide(c-o,o),di_absolute_spread=abs(plus-minus))
    both=np.isfinite(plus)&np.isfinite(minus)
    result['di_plus_dominant']=np.where(both,(plus>minus).astype(float),np.nan)
    step=pivot_research.DURATIONS[report['timeframe']]
    for name,v in (('di_plus',plus),('di_minus',minus)):
        contiguous=(times[1:-1]-times[:-2]==step)&(times[2:]-times[1:-1]==step)
        known=contiguous&np.isfinite(v[:-2])&np.isfinite(v[1:-1])&np.isfinite(v[2:])
        for label,condition in (('peak', (v[:-2]<v[1:-1])&(v[1:-1]>v[2:])),('trough',(v[:-2]>v[1:-1])&(v[1:-1]<v[2:]))):
            event=np.full(len(times),np.nan);event[2:]=np.where(known,condition.astype(float),np.nan)
            result[name+'_'+label+'_confirmed_at_close']=event
    return result


def compare(source,report,*,before=12,after=24,batch_size=24,progress=None,context_reader=None):
    import numpy as np
    if not 0<=before<=100 or not 0<=after<=100 or not 1<=batch_size<=64:raise ValueError('Invalid window/batch size')
    if report.get('symbol')!='BTCUSDT':raise ValueError('This research contract is BTCUSDT only')
    if report['config']['threshold_pct']!=1.:raise ValueError('Generate the source study with --threshold-pct 1')
    metadata,cap=pivot_research.metadata(source,report['symbol'],report['timeframe'])
    from .memory_storage.Storage import engine_store
    if engine_store.digest(metadata)!=report['source_id'] or cap<report['coverage']['last']:raise ValueError('Source generation/config/prefix differs from the study')
    offsets=list(range(-before,after+1));cases=report['cases'];labels=outcomes(report,1.)
    if len(cases)!=report['summary']['pivots']:raise ValueError('Inconsistent pivot count')
    times=np.asarray([r[0] for r in source.execute('SELECT open_time FROM raw.klines WHERE symbol=? AND interval=? AND open_time<=? AND close_time<? ORDER BY open_time',(report['symbol'],report['timeframe'],report['coverage']['last'],report['observed_as_of']))],dtype=np.int64)
    if not len(times):raise ValueError('No candles in frozen source coverage')
    origins=[c['pivot']['origin_time'] for c in cases]
    idx,valid=exact_indices(times,origins,offsets,pivot_research.DURATIONS[report['timeframe']]);groups=memberships(cases,labels)
    schema=list(source.execute('PRAGMA table_info(features)'))
    numeric=[r[1] for r in schema if r[1] not in EXCLUDE and any(t in r[2].upper() for t in ('INT','REAL','FLOAT','DOUBLE','NUMERIC'))]
    features={};categories={};existing={r[1] for r in schema}
    def store(names,values):
        for group in aggregate(values,idx,valid,groups):
            for j,name in enumerate(names):
                features.setdefault(name,[]).append({k:v for k,v in group.items() if k not in ('count','mean','stddev','minimum','maximum')}|
                    {key:[None if not math.isfinite(row[j]) else row[j] for row in group[key]] for key in ('count','mean','stddev','minimum','maximum')})
    for begin in range(0,len(numeric),batch_size):
        names=numeric[begin:begin+batch_size];quoted=','.join('f."'+n.replace('"','""')+'"' for n in names)
        sql='''SELECT '''+quoted+''',f.formula_version,f.measurement_version,f.measurement_config_id FROM raw.klines k LEFT JOIN features f
          ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time WHERE k.symbol=? AND k.interval=? AND k.open_time<=? AND k.close_time<? ORDER BY k.open_time'''
        values=np.full((len(times),len(names)),np.nan)
        for i,row in enumerate(source.execute(sql,(report['symbol'],report['timeframe'],report['coverage']['last'],report['observed_as_of']))):
            if row[-3]==3 and row[-2]=='shared-v1' and row[-1]:values[i]=[v if isinstance(v,(int,float)) and math.isfinite(v) else np.nan for v in row[:-3]]
        store(names,values)
        if progress:progress(dict(stage='numeric_features',complete=min(begin+batch_size,len(numeric)),total=len(numeric),pivots=len(cases)))
    extras=derived(source,report,times)
    store(list(extras),np.column_stack(list(extras.values())))
    for field in CATEGORIES:
        if field not in existing:continue
        values=[r[0] if r[1]==3 and r[2]=='shared-v1' and r[3] else None for r in source.execute(f'''SELECT f.{field},f.formula_version,f.measurement_version,f.measurement_config_id FROM raw.klines k LEFT JOIN features f ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time WHERE k.symbol=? AND k.interval=? AND k.open_time<=? AND k.close_time<? ORDER BY k.open_time''',(report['symbol'],report['timeframe'],report['coverage']['last'],report['observed_as_of']))]
        categories[field]=[]
        for key,members in sorted(groups.items()):
            if key[2]!='ALL':continue
            counts=[dict(Counter(str(values[idx[i,j]]) if valid[i,j] and values[idx[i,j]] is not None else 'UNAVAILABLE' for i in members)) for j in range(len(offsets))]
            categories[field].append(dict(side=key[0],outcome=key[1],pivots=len(members),counts=counts))
    engine_counts=Counter()
    if context_reader:
        step=pivot_research.DURATIONS[report['timeframe']]
        for i,case in enumerate(cases):
            for stage,as_of in (('BEFORE_ORIGIN',case['pivot']['origin_time']),('ORIGIN_CLOSE',case['pivot']['origin_time']+step)):
                for frame,engines in context_reader.context(as_of).items():
                    for name,value in engines.items():
                        classification=json.dumps(value.get('classification'),sort_keys=True,separators=(',',':'))
                        engine_counts[case['side'],labels[case['id']],stage,frame,name,value['status'],classification]+=1
            if progress and (i+1)%1000==0:progress(dict(stage='engine_context',complete=i+1,total=len(cases)))
    engine_context=dict(source_status=context_reader.run_status if context_reader else {'all':'NOT_REQUESTED'},groups=[dict(side=k[0],outcome=k[1],stage=k[2],timeframe=k[3],engine=k[4],status=k[5],classification=json.loads(k[6]),count=n) for k,n in sorted(engine_counts.items())])
    timing=[]
    zero=offsets.index(0);origin_index=idx[:,zero];origin_present=valid[:,zero]
    pivot_prices=np.asarray([c['pivot']['price'] for c in cases],dtype=float)
    directions=np.asarray([1. if c['side']=='BUY_SIDE' else -1. for c in cases])
    origin_close_move=directions*(extras['raw_close'][origin_index]/pivot_prices-1)*100
    origin_edge=np.where(directions>0,extras['raw_low'][origin_index],extras['raw_high'][origin_index])
    matches=origin_present & np.isclose(origin_edge,pivot_prices,rtol=1e-10,atol=1e-8)
    for key,members in sorted(groups.items()):
        if key[2]!='ALL':continue
        chosen=[cases[i] for i in members];step=pivot_research.DURATIONS[report['timeframe']]
        timing.append(dict(side=key[0],outcome=key[1],pivots=len(chosen),
            confirmation_delay_bars=dict(Counter((c['pivot']['known_time']-c['pivot']['origin_time'])//step for c in chosen)),
            first_hit_bars=dict(Counter(c['origin']['first_hit']['bars'] for c in chosen if c['origin'].get('first_hit'))),
            hit_by_confirmation=sum(bool(c.get('origin_hit_by_confirmation')) for c in chosen),
            origin_price_matches_raw=int(matches[members].sum()),
            origin_close_already_moved_1pct=int((origin_present[members] & (origin_close_move[members]>=1.-1e-10)).sum()),
            origin_close_move_mean_pct=float(np.nanmean(origin_close_move[members])) if np.isfinite(origin_close_move[members]).any() else None))
    return dict(version=VERSION,symbol=report['symbol'],timeframe=report['timeframe'],source_id=report['source_id'],threshold_pct=1.,
        coverage=report['coverage'],pivots=len(cases),offsets=offsets,origin_outcomes=dict(Counter(labels.values())),
        missing_exact_offset_rows=int((~valid).sum()),engine_context=engine_context,timing=timing,features=features,categorical_features=categories,
        not_profiled_columns=[r[1] for r in schema if r[1] not in numeric and r[1] not in CATEGORIES],
        unit_notes={'atr_percent':'Legacy stored ATR/close fraction; the name does not imply multiplication by 100','atr_pct_of_close':'Derived 100*ATR/close percentage points'},
        schema=dict(numeric=numeric,derived=list(extras),categorical=list(categories)),
        interpretation='Every source pivot, LOW=BUY research point, HIGH=SELL research point; 1% observed move on candles after origin until next opposite pivot. Same-origin close recovery is a separate timing diagnostic; the origin candle high/low order is unknown. Origin-relative retrospective comparisons, not signals or trading profits. Offset 0 uses the pivot candle close; positive offsets are LATER evidence and cannot explain an earlier prediction. Negative offsets use their own closes. Exact missing candles/invalid features remain unavailable. All numeric stored columns are profiled in bounded batches; selected low-cardinality strings are counted; IDs/event payloads are listed but not averaged. Means are descriptive, not an optimized rule. Annual groups expose some period confounding, not causal control or out-of-sample validation. Independent Section 5 context is not inferred from legacy categorical labels. Structure inputs remain subject to the staged defect review. No production memory or rules changed.')
