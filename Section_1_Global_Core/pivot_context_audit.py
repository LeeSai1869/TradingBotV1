"""Read-only pivot-conditioned evidence audit; never a trade backtest."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from functools import lru_cache
import json
import math
import time
from . import pivot_research,regime_inputs,intelligence_audit,aggregation_processor,data_policy
from .memory_storage.Storage import engine_store
from Section_9_Confidence_Engine import engine as confidence
from Section_10_Opportunity_Engine import engine as opportunity

VERSION='pivot-context-audit-v1'
DURATIONS={'1m':60000,'5m':300000,'15m':900000,'30m':1800000,'1h':3600000,'4h':14400000,'1d':86400000}
FIELDS=tuple(sorted(set(confidence.FIELDS)|set(opportunity.FIELDS)|{'formula_version','measurement_version','measurement_config_id','regime_state','trend_state','di_signed_spread','candidate_pivot'}))


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)


def closed_open(as_of,frame):
    """Latest fully closed UTC interval; never the enclosing forming HTF bar."""
    step=DURATIONS[frame]
    return as_of//step*step-step


def unavailable(reason):return dict(status=reason,classification=None)


def engine_point(conn,run,frame,as_of):
    if not run:return unavailable('UNAVAILABLE')
    opened=closed_open(as_of,frame)
    row=conn.execute('SELECT payload FROM engine_results WHERE run_id=? AND candle_time=?',(run['run_id'],opened)).fetchone()
    if not row:return unavailable('MISSING_EXACT_CLOSED_CANDLE')
    p=json.loads(row[0]);meta=run['metadata']
    if any(p.get(k)!=meta.get(k) for k in ('identity','engine','engine_version','config_hash','input_signature')):
        return unavailable('RUN_BINDING_MISMATCH')
    if (p.get('mode')!='CONFIRMED' or p.get('candle_open_time')!=opened or p.get('candle_close_time')!=opened+DURATIONS[frame]-1
        or type(p.get('as_of')) is not int or not p['candle_close_time']<p['as_of']<=as_of):return unavailable('INVALID_AS_OF')
    quality=p.get('data_quality')
    return dict(status=quality,classification=p.get('classification') if quality in ('VALID','PARTIAL') else None,
                candle_open_time=opened,as_of=p['as_of'],available_at=p.get('available_at'),confidence=p.get('confidence'),
                coverage=p.get('coverage'),run_id=run['run_id'],engine_version=p.get('engine_version'),
                quality_flags=p.get('quality_flags'),availability='HISTORICAL_RECONSTRUCTION_NOT_ACTUAL_PUBLICATION')


def select_history_run(conn,symbol,frame,name,policy,generation,*,at):
    """Research may use a compatible committed prefix while its live head waits."""
    run,status=intelligence_audit.select_run(conn,symbol,frame,name,policy,generation,at=at)
    if run or not status.startswith('ENGINE_WAITING:'):return run,status
    epoch=[policy['epochs'].get('symbol:'+symbol,0),policy['epochs'].get('interval:'+frame,0)]
    query="""SELECT b.run_id,b.metadata,r.metadata,r.cursor FROM mtf_bindings b JOIN engine_runs r ON r.run_id=b.run_id
        WHERE b.symbol=? AND b.timeframe=? AND b.engine=? AND b.generation=? AND b.known_ms<=?
        ORDER BY b.known_ms DESC,b.id DESC"""
    for row in conn.execute(query,(symbol,frame,name,generation,at)):
        binding=json.loads(row[1]);metadata=json.loads(row[2])
        if binding.get('raw_epoch')!=epoch or binding.get('revision')!='initial':continue
        if any(binding.get(k)!=metadata.get(k) for k in ('identity','engine_version','config_hash','input_signature')):continue
        identity=metadata.get('identity',{})
        if metadata.get('engine')!=name or identity.get('symbol')!=symbol or identity.get('timeframe')!=frame:continue
        return dict(run_id=row[0],metadata=metadata,cursor=row[3]),'COMMITTED_PREFIX; '+status
    return None,status


class LocalReader:
    """Existing snapshots only; missing engine histories never start a replay."""
    def __init__(self,source,engines,report):
        self.source=source;self.engines=engines;self.report=report;self.symbol=report['symbol'];self.frame=report['timeframe']
        self.runs={};self.run_status={};now=int(time.time()*1000);policy=data_policy.read()
        existing={r[1] for r in source.execute('PRAGMA table_info(features)')};self.fields=[f for f in FIELDS if f in existing]
        self.generations={}
        if engines:
            for frame in dict.fromkeys((self.frame,'4h','1d')):
                for name in ('REGIME','TREND'):
                    run,status=select_history_run(engines,self.symbol,frame,name,policy,aggregation_processor.generation(name),at=now)
                    if run:
                        try:
                            generation=regime_inputs.source_metadata(source,self.symbol,frame,'initial',())['feature_generation']
                            if run['metadata']['source_versions']['feature_generation']!=generation:run=None;status='FEATURE_GENERATION_MISMATCH'
                        except regime_inputs.InputsUnavailable as error:run=None;status=str(error)
                    self.runs[frame,name]=run;self.run_status[frame+':'+name]=status

    @lru_cache(maxsize=4096)
    def point(self,opened):
        sql='SELECT k.open_time,k.close_time,k.open,k.high,k.low,k.close,'+','.join('f.'+f for f in self.fields)+''' FROM raw.klines k JOIN features f
            ON f.symbol=k.symbol AND f.interval=k.interval AND f.open_time=k.open_time
            WHERE k.symbol=? AND k.interval=? AND k.open_time=?'''
        row=self.source.execute(sql,(self.symbol,self.frame,opened)).fetchone()
        if not row:return None
        return dict(client=dict(zip(('open_time','close_time','open','high','low','close'),row[:6])),features=dict(zip(self.fields,row[6:])))

    @lru_cache(maxsize=8192)
    def context(self,as_of):
        return {frame:{name:engine_point(self.engines,self.runs.get((frame,name)),frame,as_of) for name in ('REGIME','TREND')}
                for frame in dict.fromkeys((self.frame,'4h','1d'))}

    def path(self,case):
        end=(case.get('next_opposite') or {}).get('origin_time');start=case['pivot']['known_time']
        return list(pivot_research.raw_path(self.source,self.symbol,self.frame,start,self.report['coverage']['last'],self.report['observed_as_of'],end))


class EmbeddedReader:
    def __init__(self,report):
        self.report=report;self.run_status={'all':'NOT_EMBEDDED_IN_SOURCE_REPORT'};self.rows={}
        for packet in report.get('contexts',{}).values():
            for row in packet['bars']:
                opened=row['client']['open_time']
                if opened in self.rows and any(self.rows[opened][k]!=row[k] for k in ('client','features')):raise ValueError('Conflicting embedded context rows')
                self.rows[opened]=row
    def point(self,opened):return self.rows.get(opened)
    def context(self,as_of):return {f:{n:unavailable('NOT_EMBEDDED_IN_SOURCE_REPORT') for n in ('REGIME','TREND')} for f in dict.fromkeys((self.report['timeframe'],'4h','1d'))}
    def path(self,case):
        end=(case.get('next_opposite') or {}).get('origin_time');start=case['pivot']['known_time']
        return [r['client'] for t,r in sorted(self.rows.items()) if start<=t<self.report['observed_as_of'] and (end is None or t<=end)]


def band_outcome(area,rows,start,end,step,*,direction=None):
    """OHLC interval touch, not a reversal prediction or an executed fill."""
    expected=start;gap=False;first=None;gap_crossings=0;previous=None;rejection=None;breakthrough=None
    for row in rows:
        opened=row['open_time']
        if end is not None and opened>end:break
        if opened!=expected:gap=True
        expected=opened+step
        if previous is not None and (previous<area['low'] and row['open']>area['high'] or previous>area['high'] and row['open']<area['low']):gap_crossings+=1
        if first is not None and direction in ('support','resistance'):
            # Begin on the FOLLOWING candle: OHLC cannot order moves inside the touch candle.
            reject=(row['high']/area['high']-1)*100 if direction=='support' else (1-row['low']/area['low'])*100
            breach=(1-row['low']/area['low'])*100 if direction=='support' else (row['high']/area['high']-1)*100
            rejection=max(rejection or 0.,reject,0.);breakthrough=max(breakthrough or 0.,breach,0.)
        if first is None and row['high']>=area['low'] and row['low']<=area['high']:
            first=dict(open_time=opened,known_by=row['close_time']+1)
        previous=row['close']
    complete=end is not None and end>=start and bool(rows) and expected==end+step and not gap
    return dict(status='TOUCHED' if first else 'NO_TOUCH' if complete else 'CENSORED',first_touch=first,complete_window=complete,gap=gap,gap_crossings=gap_crossings,post_touch_max_rejection_pct=rejection,post_touch_max_breakthrough_pct=breakthrough,reaction_basis='Candle AFTER touch onward; band edges, not executable returns')


def alignment(context,frame):
    directions=[((context[f]['TREND'].get('classification') or {}).get('direction')) for f in dict.fromkeys((frame,'4h','1d'))]
    if any(d not in ('BULLISH','BEARISH','NEUTRAL') for d in directions):return 'UNKNOWN'
    if len(set(directions))==1:return 'ALIGNED_'+directions[0]
    if len(directions)==3 and directions[1]==directions[2] and directions[0] in ('BULLISH','BEARISH') and directions[1] in ('BULLISH','BEARISH'):return 'LOCAL_COUNTERTREND'
    return 'CONFLICTED'


def audit_case(case,reader,frame,*,saved=None):
    step=DURATIONS[frame];known=case['pivot']['known_time'];opened=known-step
    row=reader.point(opened);previous=reader.point(opened-step)
    out=dict(id=case['id'],side=case['side'],origin_time=case['pivot']['origin_time'],known_time=known,
             year=datetime.fromtimestamp(known/1000,timezone.utc).year,origin_status=case['origin']['status'],
             after_known=case['after_known'],context_before_origin=reader.context(case['pivot']['origin_time']),context_at_recognition=reader.context(known),
             confidence=None,opportunity=None,status='FEATURES_UNAVAILABLE')
    out['alignment']=alignment(out['context_at_recognition'],frame)
    if not row:return out
    f=row['features'];client=row['client']
    if client.get('close_time',opened+step-1)+1!=known or f.get('formula_version')!=3 or f.get('measurement_version')!='shared-v1' or not f.get('measurement_config_id'):return out
    if previous and previous['client'].get('close_time',opened-1)!=opened-1:previous=None
    prior={**previous['features'],'close':previous['client']['close']} if previous else None
    older=reader.point(opened-2*step)
    sequence={}
    for key in ('di_plus','di_minus'):
        values=[record['features'].get(key) if record else None for record in (older,previous,row)]
        complete=all(finite(v) for v in values)
        sequence[key]=dict(values=values,event='PEAK_CONFIRMED' if complete and values[0]<values[1]>values[2] else 'TROUGH_CONFIRMED' if complete and values[0]>values[1]<values[2] else 'NO_TURN' if complete else 'UNAVAILABLE')
    plus,minus=f.get('di_plus'),f.get('di_minus')
    out['di_sequence']=sequence
    out['measurements']={k:f.get(k) for k in ('adx','rsi','atr','relative_volume','candidate_pivot')}
    out['measurements']['dominance']='PLUS' if finite(plus) and finite(minus) and plus>minus else 'MINUS' if finite(plus) and finite(minus) and minus>plus else 'BALANCED' if finite(plus) and finite(minus) else 'UNKNOWN'
    out['measurements']['absolute_spread']=abs(plus-minus) if finite(plus) and finite(minus) else None
    conf=saved['confidence'] if saved else confidence.evaluate(client['close'],f,previous=prior,candle=client)
    side='buy' if case['side']=='BUY_SIDE' else 'sell'
    chosen=conf['reversal'] if conf[side+'_mode']=='reversal' else conf['continuation']
    out['confidence']=dict(score=conf[side+'_score'],status=conf[side+'_status'],mode=conf[side+'_mode'],coverage=sum(g['weight']*g['coverage'] for g in chosen['groups'])/100,groups=chosen['groups'],
                           continuation_score=conf['continuation'][side+'_score'],reversal_score=conf['reversal'][side+'_score'])
    without_structure={**f,'current_structure':None,'bullish_structure_active':None,'bearish_structure_active':None}
    neutral=confidence.evaluate(client['close'],without_structure,previous=prior,candle=client)
    out['confidence']['score_without_structure']=neutral[side+'_score'] if not saved else None
    out['confidence']['structure_sensitivity_points']=round(conf[side+'_score']-neutral[side+'_score'],4) if not saved and finite(conf[side+'_score']) and finite(neutral[side+'_score']) else None
    packet=saved['opportunity'] if saved else opportunity.evaluate(client['close'],f,candle=client,timeframe=frame,as_of_ms=known)
    out.update(status='READY',anchor_price=client['close'],legacy_regime=f.get('regime_state'),legacy_trend_maturity=f.get('trend_state'))
    start=known;end=(case.get('next_opposite') or {}).get('origin_time');path=reader.path(case) if end is None or end>=start else []
    areas=[]
    for direction,bands in packet.get('areas',{}).items():
        for i,band in enumerate(bands,1):
            outcome=band_outcome(band,path,start,end,step,direction=direction) if end is None or end>=start else dict(status='NO_POST_CONFIRMATION_WINDOW',complete_window=False)
            areas.append(dict(direction=direction,layer=i,low=band['low'],high=band['high'],modeled=band['modeled'],families=band['families'],distance_pct=min(abs(band['low']-client['close']),abs(band['high']-client['close']))/client['close']*100,outcome=outcome))
    out['opportunity']=dict(status=packet['status'],areas=areas,scope='PERSISTED_DECISION_SNAPSHOT' if saved else 'SCALAR_POINT_RECONSTRUCTION_NO_PERSISTED_ZONE_INVENTORY',anchor=client['close'],
                            audit_reasons=dict(Counter(x['reason'] for x in packet.get('audit',[]))))
    return out


def summarize(rows,frame):
    groups=defaultdict(Counter);areas=defaultdict(Counter);coverage=Counter()
    for row in rows:
        coverage[row['status']]+=1;coverage['confidence:'+((row.get('confidence') or {}).get('status','unavailable'))]+=1;outcome=row['after_known']['status'];c=row.get('confidence')
        cls=lambda f,n,k:((row['context_at_recognition'][f][n].get('classification') or {}).get(k,'UNKNOWN'))
        labels={'all':'ALL','legacy_regime':row.get('legacy_regime') or 'UNKNOWN','local_regime':cls(frame,'REGIME','primary'),
                'local_trend':cls(frame,'TREND','direction'),'4h_regime':cls('4h','REGIME','primary'),'4h_trend':cls('4h','TREND','direction'),
                '1d_regime':cls('1d','REGIME','primary'),'1d_trend':cls('1d','TREND','direction'),'alignment':row['alignment']}
        di=row.get('di_sequence',{})
        labels['di_events']=' / '.join((di.get(k) or {}).get('event','UNAVAILABLE') for k in ('di_plus','di_minus'))
        labels['di_events_by_regime']=labels['local_regime']+' / '+labels['local_trend']+' / '+labels['di_events']
        labels['regime_trend_htf']=' / '.join(labels[k] for k in ('local_regime','local_trend','4h_regime','4h_trend','1d_regime','1d_trend'))
        if c and c['status']=='ready' and finite(c['score']) and 0<=c['score']<=100:
            bucket=min(9,int(c['score']//10));labels['confidence']=f'{bucket*10:02d}–{bucket*10+10:02d}';labels['confidence_mode']=c['mode']
            labels['confidence_by_regime']=labels['local_regime']+' / '+c['mode']+' / '+labels['confidence']
        else:labels['confidence']='UNAVAILABLE_OR_INSUFFICIENT'
        for dimension,label in labels.items():
            for period in ('ALL',str(row['year'])):
                g=groups[row['side'],period,dimension,label];g['n']+=1;g[outcome]+=1
        for area in (row.get('opportunity') or {}).get('areas',[]):
            key=(row['side'],area['direction'],area['layer'],area['modeled']);g=areas[key];g['n']+=1;g[area['outcome']['status']]+=1
    output=[]
    for (side,year,dimension,label),counts in sorted(groups.items()):
        decisive=counts['HIT']+counts['NO_HIT']
        output.append(dict(side=side,year=year,dimension=dimension,label=label,**dict(counts),resolved=decisive,hit_rate_pct=100*counts['HIT']/decisive if decisive else None))
    bands=[]
    for (side,direction,layer,modeled),counts in sorted(areas.items()):
        resolved=counts['TOUCHED']+counts['NO_TOUCH']
        bands.append(dict(side=side,direction=direction,layer=layer,modeled=modeled,**dict(counts),resolved=resolved,touch_rate_pct=100*counts['TOUCHED']/resolved if resolved else None))
    return dict(coverage=dict(coverage),groups=output,opportunity_areas=bands)


def validate_report(report):
    if report.get('version')!='pivot-moves-v1' or report.get('config',{}).get('horizon_bars') is not None:raise ValueError('Requires next-opposite-pivot report v1')
    if report.get('timeframe') not in pivot_research.TIMEFRAMES:raise ValueError('Unsupported pivot timeframe')
    if len(report['cases'])!=report['summary']['pivots']:raise ValueError('Inconsistent source case count')


def audit(report,reader,*,embedded_only=False,max_cases=None,progress=None):
    validate_report(report)
    cases=report['cases']
    if embedded_only:cases=[c for c in cases if c['id'] in report.get('contexts',{})]
    if max_cases is not None:cases=cases[:max_cases]
    rows=[]
    for i,case in enumerate(cases):
        rows.append(audit_case(case,reader,report['timeframe']))
        if progress and (i+1)%500==0:progress(i+1,len(cases))
    return dict(version=VERSION,source_id=report['source_id'],symbol=report['symbol'],timeframe=report['timeframe'],source_pivots=len(report['cases']),
                cohort='SELECTED_EMBEDDED_EXAMPLES' if embedded_only else 'FULL_PIVOT_COHORT' if len(cases)==len(report['cases']) else 'TRUNCATED_PREFIX',
                threshold_pct=report['config'].get('threshold_pct',2.),models=dict(confidence=confidence.VERSION,opportunity=opportunity.VERSION),engine_history_status=reader.run_status,
                interpretation='Pivot-conditioned descriptive audit, not actual BUY/SELL signal accuracy, calibrated probability, profit or fills. Scores use the recognition candle close; outcomes start at next open. SELL_SIDE measures declines for spot exit/rebuy research. Censoring is reported, not counted as failure. Regime/trend are reconstructed current-version histories, not proof of actual historical publication. Opportunity uses scalar features, not the persisted chart inventory. Touch does not prove rejection. Overlapping cases are dependent. No live rules or feature formulas changed.',
                summary=summarize(rows,report['timeframe']),cases=rows)


def audit_saved_decisions(report,reader,conn,*,max_cases=None,progress=None):
    """Audit immutable current-epoch snapshots without rebuilding ADCN or inventory."""
    from bisect import bisect_left
    from .decision_evidence import epoch_key
    from Section_8_Decision_Engine.pivot_study import measure
    validate_report(report)
    step=DURATIONS[report['timeframe']];start=report.get('requested_since',0);stop=report['observed_as_of']
    sides={'BUY':'BUY_SIDE','SELL':'SELL_SIDE'};pivots={}
    for side,kind in (('BUY','PIVOT_HIGH'),('SELL','PIVOT_LOW')):
        events={c['pivot']['origin_time']:c['pivot'] for c in report['cases'] if c['pivot']['type']==kind}
        pivots[side]=sorted(events.items())
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} if conn else set()
    times={side:[t for t,_ in events] for side,events in pivots.items()}
    epoch=epoch_key(report['symbol'],report['timeframe']);rows=[];excluded=Counter();available=0;decisions=None
    if 'decisions' in tables:
        decisions=conn.execute("SELECT COUNT(*) FROM decisions WHERE symbol=? AND interval=? AND open_time>=? AND open_time+?<=? AND signal_type IN ('BUY','SELL')",(report['symbol'],report['timeframe'],start,step,stop)).fetchone()[0]
    if 'decision_evidence' in tables:
        sql='SELECT open_time,signal_type,payload FROM decision_evidence WHERE symbol=? AND interval=? AND epoch=? AND open_time>=? AND open_time+?<=? ORDER BY open_time,signal_type'
        for opened,side,payload in conn.execute(sql,(report['symbol'],report['timeframe'],epoch,start,step,stop)):
            available+=1
            if max_cases is not None and len(rows)>=max_cases:continue
            saved=json.loads(payload);known=opened+step;point=reader.point(opened)
            if side not in sides or saved.get('side')!=side or saved.get('open_time')!=opened or not point or saved.get('entry')!=point['client']['close']:
                excluded['INVALID_ANCHOR']+=1;continue
            conf=saved.get('confidence') or {};opp=saved.get('opportunity') or {}
            if conf.get('version')!=confidence.VERSION or opp.get('version')!=opportunity.VERSION:
                excluded['OUTDATED_OR_MISSING_MODEL']+=1;continue
            events=pivots[side];index=bisect_left(times[side],known);opposite=events[index][1] if index<len(events) else None
            case=dict(id=engine_store.digest(dict(epoch=epoch,opened=opened,side=side)),side=sides[side],
                      pivot=dict(origin_time=opened,known_time=known),next_opposite=opposite,origin=dict(status='NOT_APPLICABLE'))
            path=reader.path(case)
            case['after_known']=measure(path,path[0]['open'] if path and path[0]['open_time']==known else None,sides[side],known,
                end_time=opposite['origin_time'] if opposite else None,threshold=report['config']['threshold_pct'])
            row=audit_case(case,reader,report['timeframe'],saved=saved)
            row['saved_snapshot']=dict(storage=saved.get('storage'),available_ms=saved.get('available_ms'),scope='actual stored decision evidence; may be retrospectively reconstructed')
            rows.append(row)
            if progress and len(rows)%500==0:progress(len(rows),decisions or available)
    result=dict(version=VERSION,source_id=report['source_id'],symbol=report['symbol'],timeframe=report['timeframe'],
                source_pivots=len(report['cases']),cohort='SAVED_CURRENT_EPOCH_DECISIONS',threshold_pct=report['config'].get('threshold_pct',2.),models=dict(confidence=confidence.VERSION,opportunity=opportunity.VERSION),
                engine_history_status=reader.run_status,summary=summarize(rows,report['timeframe']),cases=rows,
                evidence_coverage=dict(current_epoch=epoch,stored_snapshots=available,stored_decision_rows=decisions,excluded=dict(excluded),truncated=max_cases is not None and available>max_cases),
                interpretation='Saved BUY/SELL evidence audit, not a position backtest or probability calibration. Scores and bands are immutable stored snapshots, including their original inventory. Outcomes begin at next candle open and end at the next opposite pivot OR report cutoff (censored). Native pivot selection/endpoints are retrospective. SELL measures spot exit/rebuy declines, not short returns. Historical reconstruction is not actual original publication. Missing snapshots and censoring are explicit; touches do not prove rejection. No production rules or feature formulas changed.')
    return result


def refresh_context(packet,report,reader,*,progress=None):
    """Retain measured outcomes/scores/bands; refresh only analytical-history joins."""
    validate_report(report)
    if (packet.get('version')!=VERSION or packet.get('source_id')!=report['source_id']
        or any(packet.get(k)!=report.get(k) for k in ('symbol','timeframe'))):raise ValueError('Context refresh requires the same source report and scope')
    for i,row in enumerate(packet['cases']):
        if not 0<=row['origin_time']<row['known_time']<=report['observed_as_of']:raise ValueError('Case times outside source cutoff')
        row['context_before_origin']=reader.context(row['origin_time'])
        row['context_at_recognition']=reader.context(row['known_time'])
        row['alignment']=alignment(row['context_at_recognition'],report['timeframe'])
        if progress and (i+1)%500==0:progress(i+1,len(packet['cases']))
    packet['engine_history_status']=reader.run_status
    packet['summary']=summarize(packet['cases'],report['timeframe'])
    packet['context_refresh']='Compatible indexed committed prefixes allowed while live head waits; original scores, areas and outcomes preserved'
    return packet
