"""Full-cohort BTC candidate/DI event research. Pure; never publishes decisions."""
from bisect import bisect_left,bisect_right
from collections import Counter,defaultdict
from functools import lru_cache
import json
import math
import sys
from datetime import datetime,timezone
from . import btc_research
from .pivot_study import measure
from .rules import di_turning_point

VERSION='btc-hour-pivot-sequences-v1'
STEP=3600000
BINS=(5,10,20,35,40)


def number(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def valid(row):return row.get('feature_valid') and not row['features'].get('measurement_gap') and all(number(row['features'].get(k)) and row['features'][k]>=0 for k in ('di_plus','di_minus'))
def spread_bin(v):
    if not number(v):return 'UNAVAILABLE'
    low=0
    for edge in BINS:
        if v<edge:return f'[{low},{edge})'
        low=edge
    return '[40,+inf)'


def context(row):
    if not valid(row):return None
    p,m=row['features']['di_plus'],row['features']['di_minus'];s=abs(p-m)
    return dict(di_plus=p,di_minus=m,abs_spread=s,signed_spread=p-m,dominance=(p-m)/(p+m) if p+m>0 else None,
                dominant='PLUS' if p>m else 'MINUS' if m>p else 'BALANCED',plus_above_minus=p>m,plus_above_spread=p>s,
                minus_above_plus=m>p,minus_above_spread=m>s,spread_bin=spread_bin(s),adx=row['features'].get('adx'))


def candidate(row,side):
    kind='low' if side=='BUY' else 'high';f=row['features'];price=f.get('candidate_pivot_'+kind+'_price');stamp=f.get('candidate_pivot_'+kind+'_time')
    if (not row.get('feature_valid') or not number(price) or price<=0 or not number(stamp) or stamp<0 or int(stamp)!=stamp or stamp>row['open_time']):return None
    return dict(price=price,origin_time=int(stamp),active=f.get('candidate_pivot')==(-1 if side=='BUY' else 1))


def events(rows):
    """Reuse exact independent strategy turns; spread turns are additional events."""
    output=[[] for _ in rows];flags=[]
    for i,row in enumerate(rows):
        item=dict(di_minus_peak=None,di_plus_peak=None,spread_peak=None,di_only_buy_turn=None,di_only_sell_turn=None,production_raw=None)
        if i>=2 and all(valid(r) for r in rows[i-2:i+1]) and rows[i-2]['close_time']+1==rows[i-1]['open_time'] and rows[i-1]['close_time']+1==row['open_time']:
            three=rows[i-2:i+1];turns=btc_research.turns(*three)
            for turn in turns:output[i].append(dict(type=turn['type'],origin_time=turn['origin_time'],known_time=turn['known_time'],values=turn['values']))
            spread=[abs(r['features']['di_plus']-r['features']['di_minus']) for r in three]
            kind='PEAK' if spread[0]<spread[1]>spread[2] else 'TROUGH' if spread[0]>spread[1]<spread[2] else None
            if kind:output[i].append(dict(type='ABS_SPREAD_'+kind,origin_time=three[1]['open_time'],known_time=row['close_time']+1,values=spread))
            types={t['type'] for t in output[i]};now=context(row);peak=context(three[1])
            item.update(di_minus_peak='DI_MINUS_PEAK' in types,di_plus_peak='DI_PLUS_PEAK' in types,spread_peak='ABS_SPREAD_PEAK' in types,
                di_only_buy_turn='DI_MINUS_PEAK' in types and now['dominant']=='MINUS' and peak['dominant']=='MINUS',
                di_only_sell_turn='DI_PLUS_PEAK' in types and now['dominant']=='PLUS' and peak['dominant']=='PLUS')
            inp=[dict(**r['features'],close=r['close']) for r in three]
            item['production_raw']=di_turning_point.evaluate(inp[:2],inp[2])
        flags.append(item)
    return output,flags


def candidate_history(rows):
    episodes=[];row_episode=[None]*len(rows);observations=[];first_reference={};active_matches=defaultdict(list);active=None;previous_refs={}
    for i,row in enumerate(rows):
        contiguous=i>0 and rows[i-1]['close_time']+1==row['open_time'] and rows[i-1].get('feature_valid') and row.get('feature_valid') and not row['features'].get('measurement_gap')
        sign=row['features'].get('candidate_pivot') if row.get('feature_valid') else None
        side='BUY' if sign==-1 else 'SELL' if sign==1 else None
        if not contiguous or active is not None and active['side']!=side:
            if active:active['end_index']=i-1;active['right_censored']=not contiguous
            active=None
        if side and active is None:
            active=dict(id=len(episodes),side=side,start_index=i,end_index=None,left_censored=not contiguous,right_censored=True)
            episodes.append(active)
        if active:row_episode[i]=active['id']
        for which in ('BUY','SELL'):
            ref=candidate(row,which);old=previous_refs.get(which) if contiguous else None
            if ref:
                key=(which,ref['origin_time'])
                first_reference.setdefault(key,i)
                if ref['active'] and active:
                    if not active_matches[key] or active_matches[key][-1][0]!=active['id']:active_matches[key].append((active['id'],i,ref['price']))
                # Both stored candidate references can update on the same candle.
                changed=old is None or any(old[k]!=ref[k] for k in ('price','origin_time','active'))
                if ref['active'] or changed:

                    observations.append(dict(index=i,side=which,reference=ref,episode_id=row_episode[i] if ref['active'] else None,
                        event='STARTED' if ref['active'] and (old is None or not old['active']) else 'UPDATED' if ref['active'] and changed else 'CARRIED_FORWARD' if ref['active'] else 'INACTIVE_REFERENCE_UPDATE'))
            previous_refs[which]=ref
    if active:active['end_index']=len(rows)-1
    return episodes,row_episode,observations,first_reference,active_matches


def future(rows,index,horizon):
    """Next-open directional excursions, no position/fill/stop assumptions."""
    start=index+1
    out=dict(status='CENSORED',bars=0,complete=False,next_open=None,close_return_pct=None,max_up_pct=None,max_down_pct=None,up_1pct=None,down_1pct=None,first_target='UNAVAILABLE',gap=False)
    if start>=len(rows) or rows[index]['close_time']+1!=rows[start]['open_time']:return out
    entry=rows[start]['open'];out['next_open']=entry
    if not number(entry) or entry<=0:return out
    up=down=0.;first_up=first_down=None;previous=rows[index]['close_time'];last=None
    for r in rows[start:start+horizon]:
        values=[r[k] for k in ('open','high','low','close')]
        if r['open_time']!=previous+1 or any(not number(v) or v<=0 for v in values) or r['high']<max(values) or r['low']>min(values):out['gap']=True;break
        previous=r['close_time'];last=r;out['bars']+=1
        up=max(up,100*(r['high']/entry-1));down=max(down,100*(1-r['low']/entry))
        if first_up is None and r['high']>=entry*1.01:first_up=r['close_time']+1
        if first_down is None and r['low']<=entry*.99:first_down=r['close_time']+1
    complete=out['bars']==horizon and not out['gap']
    out.update(status='COMPLETE' if complete else 'CENSORED',complete=complete,max_up_pct=up if out['bars'] else None,max_down_pct=down if out['bars'] else None,
        close_return_pct=100*(last['close']/entry-1) if complete else None,up_1pct=True if first_up else False if complete else None,down_1pct=True if first_down else False if complete else None)
    out['first_target']='SAME_CANDLE_AMBIGUOUS' if first_up and first_down and first_up==first_down else 'UP_FIRST' if first_up and (not first_down or first_up<first_down) else 'DOWN_FIRST' if first_down else 'NEITHER' if complete else 'CENSORED'
    return out


class ContextLookup:
    def __init__(self,packet):self.history=packet.get('engine_history',{});self.coverage=Counter()
    def at(self,as_of):
        refs={}
        for key,history in self.history.items():
            frame=key.split(':')[0];step={'1h':STEP,'4h':4*STEP,'1d':24*STEP}[frame];opened=as_of//step*step-step
            p=history.get('results',{}).get(str(opened))
            if p and p.get('as_of') is not None and p['candle_close_time']<p['as_of']<=as_of:
                refs[key]=key+':'+str(opened)
            else:
                refs[key]=sys.intern('UNAVAILABLE:'+('MISSING_EXACT_CLOSED_CANDLE' if history.get('results') else history.get('status','UNAVAILABLE')))
        return refs
    def resolve(self,key,ref):
        if not ref or ref.startswith('UNAVAILABLE:'):return dict(status=ref or 'UNAVAILABLE',classification=None)
        stamp=ref.rsplit(':',1)[1];p=self.history[key]['results'][stamp]
        return dict(status=p['data_quality'],classification=p.get('classification') if p['data_quality'] in ('VALID','PARTIAL') else None,
            liquidity_observed=(p.get('measurements') or {}).get('observed') if key.endswith(':LIQUIDITY') else None)
    def labels(self,refs):
        labels={}
        fields={'REGIME':('primary','direction'),'TREND':('direction','strength_band'),'BIAS':('direction','risk'),'LIQUIDITY':('structural_side','sweep','sweep_status','book_state','derivatives_state'),'VOLATILITY':('level','state'),'SENTIMENT':('sentiment','positioning','risk')}
        for key,ref in refs.items():
            frame,engine=key.split(':');p=self.resolve(key,ref);classification=p.get('classification') or {}
            for field in fields.get(engine,()):labels[frame+':'+engine+':'+field]=classification.get(field,'UNAVAILABLE')
            if engine=='LIQUIDITY':
                observed=p.get('liquidity_observed') or {}
                labels[frame+':LIQUIDITY:observed_scope']=json.dumps(observed.get('scope'),sort_keys=True) if observed.get('scope') else 'UNAVAILABLE'
        return labels


def down_runs(rows):
    """Retain every strict down-run, including runs with no observed recovery."""
    output=[];start=None
    for i in range(1,len(rows)):
        continuous=valid(rows[i]) and valid(rows[i-1]) and rows[i-1]['close_time']+1==rows[i]['open_time']
        delta=rows[i]['features']['di_plus']-rows[i-1]['features']['di_plus'] if continuous else None
        if delta is not None and delta<0:
            if start is None:start=i
        elif start is not None:
            output.append(dict(start_index=start,end_index=i-1,declining_bars=i-start,end_reason='GAP' if delta is None else 'RECOVERED' if delta>0 else 'PLATEAU'))
            start=None
    if start is not None:output.append(dict(start_index=start,end_index=len(rows)-1,declining_bars=len(rows)-start,end_reason='END_OF_DATA'))
    return output


def dip_recoveries(rows):
    """All strict DI+ down-runs followed by an up-tick, not only successful pivots."""
    dips=[];start=None
    for i in range(1,len(rows)):
        if not valid(rows[i]) or not valid(rows[i-1]) or rows[i-1]['close_time']+1!=rows[i]['open_time']:start=None;continue
        a,b=context(rows[i-1]),context(rows[i]);delta=b['di_plus']-a['di_plus']
        if delta<0 and start is None:start=i
        elif delta>0 and start is not None:
            segment=[context(r) for r in rows[start-1:i+1]];baseline=segment[0]['di_plus'];minimum=min(v['di_plus'] for v in segment[:-1])
            initial=segment[0]['plus_above_minus'] and segment[0]['plus_above_spread']
            stayed_minus=all(v['di_plus']>=v['di_minus'] for v in segment);stayed_spread=all(v['di_plus']>=v['abs_spread'] for v in segment)
            touched=any(v['di_plus']==v['di_minus'] or v['di_plus']==v['abs_spread'] for v in segment)
            path='TOUCHED_NO_BREACH' if initial and stayed_minus and stayed_spread and touched else 'STAYED_ABOVE_BOTH' if initial and stayed_minus and stayed_spread else 'LOST_MINUS_ONLY' if initial and not stayed_minus and stayed_spread else 'LOST_BOTH' if initial and not stayed_minus and not stayed_spread else 'NOT_ABOVE_BOTH_AT_START'
            recovered=[];window_complete=(i+12<len(rows) and all(valid(r) for r in rows[i:i+13]) and all(rows[j-1]['close_time']+1==rows[j]['open_time'] for j in range(i+1,i+13)))
            for j in range(i,min(len(rows),i+13)):
                if j>i and rows[j-1]['close_time']+1!=rows[j]['open_time'] or not valid(rows[j]):window_complete=False;break
                if context(rows[j])['di_plus']>=baseline:recovered.append(j);break
            dips.append(dict(start_index=start,baseline_index=start-1,recovery_index=i,declining_bars=i-start,brief=i-start<=2,
                baseline_di_plus=baseline,minimum_di_plus=minimum,drop_points=baseline-minimum,comparison_path=path,
                regained_pre_dip_level_at=recovered[0] if recovered else None,regained_pre_dip_level_window_complete=window_complete,regained_pre_dip_level_status='REGAINED' if recovered else 'NOT_REGAINED' if window_complete else 'CENSORED'))
            start=None
        elif delta==0:start=None # plateaus are not silently treated as a strict turn
    return dips


def analyze(packet,*,progress=None):
    if packet.get('version')!='btc-hour-sequence-source-v1' or packet.get('symbol')!='BTCUSDT' or packet.get('timeframe')!='1h' or packet.get('threshold_pct')!=1:raise ValueError('Use the row-level BTC 1h sequence export')
    rows=packet['candles'];times=[r['open_time'] for r in rows];positions={t:i for i,t in enumerate(times)}
    if times!=sorted(set(times)):raise ValueError('Candles must be chronological and unique')
    turns,flags=events(rows);episodes,row_episode,observations,first_ref,matches=candidate_history(rows);lookup=ContextLookup(packet)
    @lru_cache(maxsize=16384)
    def outlook(index,horizon):return future(rows,index,horizon)
    @lru_cache(maxsize=None)
    def snapshot(index):
        r=rows[index];ctx=context(r)
        return dict(index=index,open_time=r['open_time'],known_time=r['close_time']+1,close=r['close'],di=ctx,events=flags[index],
            stored_di_spread=r['features'].get('di_spread'),archived_scores=packet.get('archived_scores',{}).get('rows',{}).get(str(r['open_time'])),
            measurements={k:r['features'].get(k) for k in ('rsi','atr','relative_volume','ema50','candidate_pivot','regime_state','trend_state','current_structure')},
            engine_refs=lookup.at(r['close_time']+1),
            latest_known_turns={kind:(indexes[bisect_right(indexes,index)-1] if bisect_right(indexes,index) else None) for kind,indexes in turn_indexes.items()})
    cases=[];grouped=defaultdict(Counter);engine_coverage=defaultdict(Counter);case_by_origin={};turn_indexes=defaultdict(list,{kind:[] for kind in ('DI_PLUS_PEAK','DI_PLUS_TROUGH','DI_MINUS_PEAK','DI_MINUS_TROUGH','ABS_SPREAD_PEAK','ABS_SPREAD_TROUGH')})
    for i,events_ in enumerate(turns):
        for e in events_:turn_indexes[e['type']].append(i)
    for serial,case in enumerate(packet['pivots']):
        p=case['pivot'];side='BUY' if case['side']=='BUY_SIDE' else 'SELL';origin=positions.get(p['origin_time']);confirmation=positions.get(p['known_time']-STEP)
        match=[m for m in matches.get((side,p['origin_time']),[]) if confirmation is not None and m[1]<=confirmation and math.isclose(m[2],p['price'],rel_tol=1e-10,abs_tol=1e-8)]
        episode=episodes[match[-1][0]] if match else None
        start=episode['start_index'] if episode else None;seen=first_ref.get((side,p['origin_time']))
        stage_indexes={'candidate_start':start,'final_extreme_first_recorded':seen,'origin_close':origin,'native_confirmation':confirmation}
        stages={k:snapshot(i) if i is not None else None for k,i in stage_indexes.items()}
        if origin is None:raise ValueError('Missing raw pivot-origin candle')
        end_time=(case.get('next_opposite') or {}).get('origin_time')
        stop=bisect_right(times,end_time) if end_time is not None else len(rows)
        verified=measure(iter(rows[origin+1:stop]),p['price'],case['side'],p['origin_time']+STEP,end_time=end_time,threshold=1.)
        if verified['status']!=case['origin']['status']:raise ValueError('Native pivot outcome differs from frozen raw sequence; regenerate the cohort')

        pressure='DI_MINUS_PEAK' if side=='BUY' else 'DI_PLUS_PEAK';begin=start if start is not None else origin;end=confirmation if confirmation is not None else origin
        interval={}
        for kind in (pressure,'ABS_SPREAD_PEAK'):
            indexes=turn_indexes[kind];interval[kind]=indexes[bisect_left(indexes,begin):bisect_right(indexes,end)] if begin is not None and end is not None else []
        di_turns=interval[pressure];sp_turns=interval['ABS_SPREAD_PEAK'];first=di_turns[0] if di_turns else None
        nearest_spread=min(sp_turns,key=lambda i:abs(i-first)) if first is not None and sp_turns else None
        record=dict(id=case['id'],side=side,origin_time=p['origin_time'],price=p['price'],native_known_time=p['known_time'],outcome=verified,
            next_opposite=case.get('next_opposite'),episode_id=episode['id'] if episode else None,left_censored_candidate=episode['left_censored'] if episode else None,
            stages=stages,candidate_observed_after_origin=(start>origin) if start is not None and origin is not None else None,
            recognition={name:dict(known_offset_hours=(snap['known_time']-p['origin_time'])/STEP,close_distance_from_eventual_extreme_pct=(snap['close']/p['price']-1)*100*(1 if side=='BUY' else -1),
                close_already_1pct_from_pivot=((snap['close']/p['price']-1)*(1 if side=='BUY' else -1)>=.01-1e-10) if snap['open_time']>=p['origin_time'] else None) for name,snap in stages.items() if snap},pressure_peaks=di_turns,spread_peaks=sp_turns,spread_peak_lag_bars=nearest_spread-first if nearest_spread is not None else None,
            pressure_peak_seen_by_origin=any(i<=origin for i in di_turns) if origin is not None and episode else None,
            spread_peak_seen_by_origin=any(i<=origin for i in sp_turns) if origin is not None and episode else None,
            first_pressure_peak=dict(snapshot=snapshot(first),recognized_before_origin=first<origin if origin is not None else None,close_distance_from_eventual_extreme_pct=(rows[first]['close']/p['price']-1)*100*(1 if side=='BUY' else -1),
                target_already_reached=bool(case['origin'].get('first_hit') and case['origin']['first_hit']['known_by']<=rows[first]['close_time']+1)) if first is not None else None)
        if origin is not None:
            c=rows[origin];edge=c['low'] if side=='BUY' else c['high']
            if not math.isclose(edge,p['price'],rel_tol=1e-10,abs_tol=1e-8):raise ValueError('Pivot does not match raw candle extreme')
        cases.append(record);case_by_origin[side,p['origin_time']]=case['id']
        year=str(datetime.fromtimestamp(p['origin_time']/1000,timezone.utc).year)
        for stage,snap in stages.items():
            di=(snap or {}).get('di') or {};ev=(snap or {}).get('events') or {}
            dimensions={'candidate_start_quality':'UNLINKED' if episode is None else 'LEFT_CENSORED' if episode['left_censored'] else 'OBSERVED_START','spread_bin':di.get('spread_bin','UNAVAILABLE'),'dominant':di.get('dominant','UNAVAILABLE'),
                'independent_pressure_peak_now':'UNAVAILABLE' if ev.get('di_minus_peak' if side=='BUY' else 'di_plus_peak') is None else str(ev.get('di_minus_peak' if side=='BUY' else 'di_plus_peak')),
                'spread_peak_now':'UNAVAILABLE' if ev.get('spread_peak') is None else str(ev.get('spread_peak')),'pressure_seen_by_origin':'UNAVAILABLE' if record['pressure_peak_seen_by_origin'] is None else str(record['pressure_peak_seen_by_origin']),
                'spread_seen_by_origin':'UNAVAILABLE' if record['spread_peak_seen_by_origin'] is None else str(record['spread_peak_seen_by_origin'])}
            if snap:
                for scope,ref in snap['engine_refs'].items():
                    state=lookup.resolve(scope,ref);coverage=engine_coverage[stage,scope];coverage['total']+=1;coverage[state['status']]+=1;coverage['classification_present']+=state['classification'] is not None
                dimensions.update(lookup.labels(snap['engine_refs']))
                dimensions['legacy_regime']=snap['measurements'].get('regime_state') or 'UNAVAILABLE'
                dimensions['legacy_trend_maturity']=snap['measurements'].get('trend_state') or 'UNAVAILABLE'
            dimensions['joint_DI_spread']=dimensions['independent_pressure_peak_now']+' / '+dimensions['spread_peak_now']+' / '+dimensions['spread_bin']
            dimensions['joint_context_DI']=' / '.join([dimensions['joint_DI_spread'],*(str(dimensions.get(k,'UNAVAILABLE')) for k in ('1h:REGIME:primary','1h:TREND:direction','1h:BIAS:direction','1h:LIQUIDITY:structural_side','4h:TREND:direction','1d:TREND:direction'))])
            for dim,label in dimensions.items():
                for period in ('ALL',year):g=grouped[side,stage,dim,str(label),period];g['n']+=1;g[case['origin']['status']]+=1
        if progress and (serial+1)%1000==0:progress(dict(stage='pivots',complete=serial+1,total=len(packet['pivots'])))
    # Explicit potential extrema that were subsequently updated away are retained.
    candidate_records=[]
    for observation in observations:
        if not observation['reference']['active']:continue
        i=observation['index'];candidate_records.append(dict(**observation,snapshot=snapshot(i),became_native_pivot=case_by_origin.get((observation['side'],observation['reference']['origin_time'])),
            future={str(h):outlook(i,h) for h in (1,3,6,12)}))
    dips=dip_recoveries(rows);dip_records=[];dip_groups=defaultdict(Counter)
    for d in dips:
        i=d['recovery_index'];out=outlook(i,12);labels=lookup.labels(snapshot(i)['engine_refs'])
        record=dict(**d,start=snapshot(d['start_index']),recovery=snapshot(i),future={str(h):outlook(i,h) for h in (1,3,6,12)})
        dip_records.append(record)
        year=str(datetime.fromtimestamp(rows[i]['open_time']/1000,timezone.utc).year)
        for dim,label in {'comparison_path':d['comparison_path'],'duration_bars':str(d['declining_bars']),'brief':str(d['brief']),
                          'path_and_duration':d['comparison_path']+' / '+str(d['declining_bars']),**labels}.items():
            for period in ('ALL',year):
                g=dip_groups[dim,str(label),period];g['n']+=1;g[out['status']]+=1;g['UP_1PCT']+=out['up_1pct'] is True;g['DOWN_1PCT']+=out['down_1pct'] is True
                g['COMPLETE_UP_1PCT']+=out['complete'] and out['up_1pct'] is True;g['COMPLETE_DOWN_1PCT']+=out['complete'] and out['down_1pct'] is True
                if out['complete']:g['close_return_sum_pct']+=out['close_return_pct']
    recoveries=[r['recovery_index'] for r in dip_records]
    for record in cases:
        if record['side']!='SELL':continue
        for anchor in ('candidate_start','origin_close'):
            snap=record['stages'][anchor]
            end=(record.get('next_opposite') or {}).get('origin_time',packet['observed_as_of'])
            # Window membership is retrospective; fixed future outcomes are separate.
            stop=bisect_right(times,end)-1
            selected=list(range(bisect_left(recoveries,snap['index']),bisect_right(recoveries,stop))) if snap else []
            fixed_stop=bisect_right(times,(snap['open_time']+12*STEP) if snap else -1)-1
            fixed=list(range(bisect_left(recoveries,snap['index']),bisect_right(recoveries,fixed_stop))) if snap else []
            record.setdefault('post_sell_recovery_ids',{})[anchor]=dict(until_next_opposite_pivot=selected,within_12_hours=fixed)
    groups=[]
    for (side,stage,dim,label,year),g in sorted(grouped.items()):
        resolved=g['HIT']+g['NO_HIT'];groups.append(dict(side=side,stage=stage,dimension=dim,label=label,year=year,**dict(g),resolved=resolved,hit_rate_pct=100*g['HIT']/resolved if resolved else None))
    down_records=[dict(**r,start_snapshot=r['start_index'],future={str(h):outlook(r['start_index'],h) for h in (1,3,6,12)}) for r in down_runs(rows)]
    candidate_groups=defaultdict(Counter)
    for r in candidate_records:
        snap=r['snapshot'];di=snap['di'] or {};ev=snap['events'];out=r['future']['12'];side=r['side']
        dimensions={'spread_bin':di.get('spread_bin','UNAVAILABLE'),'dominant':di.get('dominant','UNAVAILABLE'),
            'event_kind':r['event'],'di_peak_now':str(ev['di_minus_peak' if side=='BUY' else 'di_plus_peak']),
            'spread_peak_now':str(ev['spread_peak']),**lookup.labels(snap['engine_refs'])}
        year=str(datetime.fromtimestamp(snap['open_time']/1000,timezone.utc).year)
        for dim,label in dimensions.items():
            for period in ('ALL',year):
                g=candidate_groups[side,dim,str(label),period];g['n']+=1;g[out['status']]+=1
                favorable=out['up_1pct'] if side=='BUY' else out['down_1pct']
                g['OBSERVED_FAVORABLE_1PCT']+=favorable is True;g['COMPLETE_FAVORABLE_1PCT']+=out['complete'] and favorable is True
                if out['complete']:g['directional_close_return_sum_pct']+=out['close_return_pct']*(1 if side=='BUY' else -1)
    # Store shared snapshots once, referenced by index throughout the export.
    for r in cases:
        r['stages']={k:v['index'] if v else None for k,v in r['stages'].items()}
        if r['first_pressure_peak']:r['first_pressure_peak']['snapshot']=r['first_pressure_peak']['snapshot']['index']
    for r in candidate_records:r['snapshot']=r['snapshot']['index']
    for r in dip_records:r['start']=r['start']['index'];r['recovery']=r['recovery']['index']
    return dict(version=VERSION,source_id=packet['source_id'],symbol='BTCUSDT',timeframe='1h',observed_as_of=packet['observed_as_of'],
        definitions=dict(experimental_strategy_version=btc_research.VERSION,production_DI_rule_version=di_turning_point.VERSION,raw_rule_scope='Predicate comparison only; no position eligibility, alternation or execution',spread_bins=list(BINS),brief_dip='1 or 2 strict down-bars followed by an up-tick; all run lengths retained',
            candidate_start='First active closed-candle candidate phase observation; final-extreme update and pivot origin are separate stages',
            recovery='First strictly higher DI+ close; regain of pre-dip DI+ tracked separately up to 12 following bars',
            algebra='While DI+>DI-, abs(DI+-DI-) cannot exceed DI+. Falling below spread implies DI->2*DI+. Crossings are not independent.',
            sell='Retrospective HIGH research point, not an executed short or necessarily an actual SELL signal',
            context='Exact last-closed local/4h/daily candle from compatible versioned histories; missing remains unavailable; references resolve into source export',
            score=packet['definitions']['di_score'],industry_bias=packet['definitions']['industry_bias']),
        counts=dict(di_plus_down_runs=len(down_records),candles=len(rows),pivots=len(cases),candidate_phases=len(episodes),candidate_observations=len(candidate_records),dip_recoveries=len(dip_records),
            linked_candidate_pivots=sum(c['episode_id'] is not None for c in cases),unlinked_candidate_pivots=sum(c['episode_id'] is None for c in cases)),
        archived_score_status=packet.get('archived_scores',{}).get('status','UNAVAILABLE'),
        archived_score_coverage={key:sum(row.get(key) is not None for row in packet.get('archived_scores',{}).get('rows',{}).values()) for key in packet.get('archived_scores',{}).get('fields',[])},
        engine_coverage=[dict(stage=k[0],scope=k[1],counts=dict(v)) for k,v in sorted(engine_coverage.items())],
        groups=groups,dip_groups=[dict(dimension=k[0],label=k[1],year=k[2],**dict(v),mean_close_return_pct=v['close_return_sum_pct']/v['COMPLETE'] if v['COMPLETE'] else None) for k,v in sorted(dip_groups.items())],
        candidate_groups=[dict(side=k[0],dimension=k[1],label=k[2],year=k[3],**dict(v),mean_directional_close_return_pct=v['directional_close_return_sum_pct']/v['COMPLETE'] if v['COMPLETE'] else None) for k,v in sorted(candidate_groups.items())],
        all_di_plus_down_runs=down_records,
        context_pool={scope+':'+stamp:{key:value for key,value in value.items() if key not in ('measurements',)}|dict(liquidity_measurements={k:(value.get('measurements') or {}).get(k) for k in ('nearest_inferred_levels','observed')}) for scope,history in packet.get('engine_history',{}).items() for stamp,value in history.get('results',{}).items()},
        snapshots={str(i):snapshot(i) for i in range(len(rows))},
        cases=cases,candidate_observations=candidate_records,di_plus_recoveries=dip_records,
        all_turn_events=[dict(index=i,events=e) for i,e in enumerate(turns) if e],engine_source_status={k:v['status'] for k,v in packet.get('engine_history',{}).items()},
        interpretation='Full row-level candidate/DI sequence research, not averages or selected examples. Pivot association and next-opposite windows are retrospective labels; causal observations/fixed next-open outcomes remain separate. No position, costs, stops, trailing, short execution or trading win rate simulated. Brief-dip categories are fixed descriptive assumptions, not optimized gates. Missing features/context/archived scores stay explicit. No live logic or memory changed.')
