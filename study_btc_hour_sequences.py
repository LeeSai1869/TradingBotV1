"""Full BTC 1h candidate/DI/spread/context study; row export plus offline analysis."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sqlite3
import math
from collections import Counter
from datetime import datetime,timezone
from Section_1_Global_Core import btc_hour_sequence_source
from Section_8_Decision_Engine.pivot_sequences import analyze
from study_pivot_moves import push_report


def default_combination_filters():
    """Fixed descriptive gates, specified before inspecting combination outcomes."""
    filters=[]
    for side,dominant,direction in (('BUY','MINUS','BULLISH'),('SELL','PLUS','BEARISH')):
        conditions=[
            dict(name='DI spread',all=[dict(field='di.abs_spread',min=10)]),
            dict(name='DI dominance',all=[dict(field='di.dominant',eq=dominant)]),
            dict(name='Local Trend',all=[dict(field='1h:TREND:direction',eq=direction)]),
            dict(name='Last-closed 4h and daily Trend',all=[dict(field=f'{frame}:TREND:direction',eq=direction) for frame in ('4h','1d')])]
        filters.append(dict(id=side.lower()+'_context_4',side=side,conditions=conditions))
        filters.append(dict(id=side.lower()+'_context_5',side=side,conditions=conditions+[
            dict(name='Local Regime',all=[dict(field='1h:REGIME:primary',eq='TRENDING')])]))
    return filters


def validate_combination_filters(filters):
    if not isinstance(filters,list) or not filters:raise ValueError('Combination filters must be a nonempty JSON list')
    ids=set()
    for spec in filters:
        if not isinstance(spec,dict) or not isinstance(spec.get('id'),str) or not spec['id'] or spec['id'] in ids:
            raise ValueError('Combination filter ids must be unique nonempty strings')
        ids.add(spec['id'])
        if spec.get('side') not in ('BUY','SELL'):raise ValueError('Combination filter side must be BUY or SELL')
        conditions=spec.get('conditions')
        if not isinstance(conditions,list) or len(conditions) not in (4,5):raise ValueError('Combine exactly 4 or 5 named conditions')
        names=set()
        for condition in conditions:
            if not isinstance(condition,dict) or not isinstance(condition.get('name'),str) or not condition['name'] or condition['name'] in names:
                raise ValueError('Condition names must be unique nonempty strings')
            names.add(condition['name'])
            terms=condition.get('all')
            if not isinstance(terms,list) or not terms:raise ValueError('Each condition needs a nonempty all list of predicates')
            for term in terms:
                if not isinstance(term,dict):raise ValueError('Each predicate must be an object')
                field=term.get('field','')
                parts=field.split(':') if isinstance(field,str) else []
                if field not in ('di.abs_spread','di.dominant') and not (len(parts)==3 and parts[0] in ('1h','4h','1d') and parts[1] in ('REGIME','TREND') and parts[2] in ('primary','direction','strength_band')):
                    raise ValueError('Unsupported combination field: '+str(field))
                ops=set(term)-{'field'}
                if not ops or ops-{'eq','in','min','max'}:raise ValueError('Use eq, in, min (inclusive) or max (exclusive) predicates')
                if field=='di.abs_spread' and ops-{'min','max'} or field!='di.abs_spread' and ops-{'eq','in'}:
                    raise ValueError('Use numeric bounds for spread and eq/in for classifications')
                if 'in' in term and (not isinstance(term['in'],list) or not term['in'] or any(not isinstance(v,str) for v in term['in'])):
                    raise ValueError('in requires a nonempty string list')
                if 'eq' in term and not isinstance(term['eq'],str):raise ValueError('eq requires a string')
                for op in ('min','max'):
                    if op in term and (field!='di.abs_spread' or not isinstance(term[op],(int,float)) or isinstance(term[op],bool) or not math.isfinite(term[op])):
                        raise ValueError('Finite numeric bounds apply only to di.abs_spread')
                if 'min' in term and 'max' in term and term['min']>=term['max']:raise ValueError('min must be below max')
    return filters


def combination_value(packet,snapshot,field):
    """Never substitute stale, forming, future, legacy or neutral engine context."""
    if snapshot is None:return None,'MISSING_STAGE'
    if field.startswith('di.'):
        value=(snapshot.get('di') or {}).get(field[3:])
        valid=(isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0) if field=='di.abs_spread' else value in ('PLUS','MINUS','BALANCED')
        return (value,None) if valid else (None,'MISSING_DI')
    frame,engine,name=field.split(':');scope=frame+':'+engine
    ref=snapshot.get('engine_refs',{}).get(scope)
    payload=packet.get('context_pool',{}).get(ref)
    if not payload:return None,ref if ref and ref.startswith('UNAVAILABLE:') else 'MISSING_CONTEXT'
    step={'1h':3600000,'4h':14400000,'1d':86400000}[frame]
    known=snapshot['known_time'];opened=known//step*step-step
    if (ref!=scope+':'+str(opened) or payload.get('candle_open_time')!=opened
        or payload.get('candle_close_time')!=opened+step-1 or payload.get('as_of')!=opened+step):
        return None,'NOT_EXACT_LAST_CLOSED'
    if payload.get('data_quality') not in ('VALID','PARTIAL'):return None,'QUALITY:'+str(payload.get('data_quality'))
    value=(payload.get('classification') or {}).get(name)
    if not isinstance(value,str) or not value or value in ('UNKNOWN','UNAVAILABLE'):return None,'MISSING_CLASSIFICATION'
    return value,None


def combination_state(packet,snapshot,spec):
    missing={};matched=True
    for condition in spec['conditions']:
        for term in condition['all']:
            value,reason=combination_value(packet,snapshot,term['field'])
            if reason:missing[term['field']]=reason;continue
            matched &= (('eq' not in term or value==term['eq']) and ('in' not in term or value in term['in'])
                and ('min' not in term or value>=term['min']) and ('max' not in term or value<term['max']))
    # Evaluate every required field even if an earlier predicate fails.
    return ('MISSING' if missing else 'MATCHED' if matched else 'NOT_MATCHED'),missing


def combination_analysis(packet,filters=None):
    """Separate research dimension: full denominators, matched coverage and UTC years."""
    filters=validate_combination_filters(default_combination_filters() if filters is None else filters)
    snapshots=packet['snapshots'];years=sorted({str(datetime.fromtimestamp(s['known_time']/1000,timezone.utc).year) for s in snapshots.values()})
    records=[]
    for case in packet['cases']:
        for stage,index in case['stages'].items():
            snap=snapshots.get(str(index)) if index is not None else None
            records.append(('native_pivot',stage,case['side'],case['id'],snap,case['outcome'],case['origin_time']+3600000))
    for row in packet['candidate_observations']:
        snap=snapshots[str(row['snapshot'])]
        records.append(('candidate_next_open_12h','active_candidate',row['side'],f"{row['side']}:{row['index']}",snap,row['future']['12'],snap['known_time']))
    stages=[('native_pivot',stage) for stage in ('candidate_start','final_extreme_first_recorded','origin_close','native_confirmation')]+[('candidate_next_open_12h','active_candidate')]
    groups={};memberships=[]
    for spec in filters:
        for cohort,stage in stages:
            for year in ['ALL',*years]:
                groups[spec['id'],cohort,stage,year]=dict(dimension='combination_filter',filter_id=spec['id'],side=spec['side'],cohort=cohort,stage=stage,year=year,
                    n=0,eligible=0,missing_excluded=0,not_matched=0,matched_n=0,missing_by_field=Counter(),missing_reasons=Counter(),
                    baseline=Counter(),eligible_baseline=Counter(),matched=Counter(),not_matched_outcomes=Counter(),first_matched_time=None,last_matched_time=None)
        selected=[]
        for cohort,stage,side,identity,snap,out,fallback in records:
            if side!=spec['side']:continue
            state,missing=combination_state(packet,snap,spec)
            known=snap['known_time'] if snap else fallback
            year=str(datetime.fromtimestamp(known/1000,timezone.utc).year)
            if state=='MATCHED':selected.append(dict(cohort=cohort,stage=stage,id=identity,known_time=known))
            for period in ('ALL',year):
                group=groups[spec['id'],cohort,stage,period];group['n']+=1
                def count(bucket):
                    bucket['n']+=1;bucket[out['status']]+=1
                    if cohort=='candidate_next_open_12h' and out['complete']:
                        bucket['directional_close_return_sum_pct']+=out['close_return_pct']*(1 if side=='BUY' else -1)
                        bucket['favorable_1pct']+=out['up_1pct' if side=='BUY' else 'down_1pct'] is True
                count(group['baseline'])
                if missing:
                    group['missing_excluded']+=1;group['missing_by_field'].update(missing.keys())
                    group['missing_reasons'].update(field+':'+reason for field,reason in missing.items())
                    continue
                group['eligible']+=1;count(group['eligible_baseline'])
                if state=='NOT_MATCHED':group['not_matched']+=1;count(group['not_matched_outcomes']);continue
                group['matched_n']+=1;count(group['matched'])
                group['first_matched_time']=known if group['first_matched_time'] is None else min(known,group['first_matched_time'])
                group['last_matched_time']=known if group['last_matched_time'] is None else max(known,group['last_matched_time'])
        memberships.append(dict(filter_id=spec['id'],records=sorted(selected,key=lambda r:(r['known_time'],r['cohort'],r['stage'],r['id']))))
    for group in groups.values():
        for key in ('baseline','eligible_baseline','matched','not_matched_outcomes'):
            b=group[key]
            for status in ('n','HIT','NO_HIT','CENSORED','COMPLETE'):b.setdefault(status,0)
            resolved=b['HIT']+b['NO_HIT'];b['resolved']=resolved
            b['hit_rate_pct']=100*b['HIT']/resolved if resolved else None
            b['mean_directional_close_return_pct']=b.get('directional_close_return_sum_pct',0)/b['COMPLETE'] if b['COMPLETE'] else None
    return dict(version='btc-hour-combinations-v1',source_id=packet['source_id'],filters=filters,groups=list(groups.values()),memberships=memberships,
        definitions=dict(condition='AND across 4–5 named conditions; each all list is also an explicit AND, not an independent vote',
            missing='Any unavailable required field excludes the row even when another predicate fails; field/reason counts overlap',
            chronology='UTC calendar years at stage knowledge time, candidates at observation close; missing native stages use origin close only for exclusion accounting. Descriptive inspected slices, not untouched holdouts',
            context='Exact last-closed 1h/4h/daily versioned context only; VALID/PARTIAL classifications accepted, UNKNOWN excluded. Reconstructed close-time knowledge, not proof of live publication',
            baseline='Unfiltered cohort and same-required-data eligible cohort are both retained; censored outcomes never enter resolved/complete denominators',
            outcomes='Native pivots are retrospective swing labels. Candidate observations use next-open 12h gross directional movement; overlapping windows, no fees or position simulation',
            defaults='Spread >=10 and pressure-side DI dominance; local Trend and both 4h/daily Trend align with research direction. Five-condition version additionally requires local Regime TRENDING. Fixed descriptive assumptions, no optimization'))


def read(path):
    data=path.read_bytes();return json.loads(gzip.decompress(data) if path.suffix=='.gz' else data)


def save(path,packet,publish):
    payload=(json.dumps(packet,separators=(',',':'),allow_nan=False)+'\n').encode()
    if path.suffix=='.gz':payload=gzip.compress(payload,mtime=0)
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.partial');temp.write_bytes(payload);temp.replace(path)
    print('Saved:',path,len(payload),'bytes',flush=True)
    if publish:push_report(path)


def combination_visual(study):
    data=json.dumps(study,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>BTC 1h combination filters</title><style>body{font:15px system-ui;background:#121b28;color:#e1e7ef;margin:16px;overflow-wrap:anywhere}select{padding:6px;max-width:100%}table{border-collapse:collapse;width:100%}td,th{padding:6px;border-bottom:1px solid #405067;text-align:left}.scroll{overflow:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>
<h1>BTC 1h combination filters</h1><p>Separate comparison dimension: <strong>combination_filter</strong>. AND across four or five named conditions; inspect every predicate below. Missing required context excludes an observation, never fills it with neutral values. Counts by missing field overlap.</p>
<p>Native pivots are retrospective swing labels. Candidate results are next-open 12-hour gross directional movement, with overlapping observations and no fees or position simulation. UTC year slices are descriptive, already inspected data, not untouched holdouts.</p>
<label>Side <select id="combo-side"><option>BUY</option><option>SELL</option></select></label>
<label>Cohort <select id="combo-cohort"><option value="native_pivot">Native pivots</option><option value="candidate_next_open_12h">All active candidate observations</option></select></label>
<label>Stage <select id="combo-stage"><option>candidate_start</option><option>final_extreme_first_recorded</option><option>origin_close</option><option>native_confirmation</option></select></label>
<label>UTC year <select id="combo-year"></select></label>
<div class="scroll"><table id="combo-results"></table></div>
<h2>Chronological results</h2><p>Same fixed definitions in every year, including years with zero eligible or matched samples. Rates use resolved native outcomes; means use complete candidate windows.</p>
<div class="scroll"><table id="combo-chronology"></table></div>
<details><summary>Definitions, exclusions and chronological matched observation IDs</summary><pre id="combo-detail"></pre></details>
<script>const d=__COMBINATION_DATA__,by=id=>document.getElementById(id),side=by('combo-side'),cohort=by('combo-cohort'),stage=by('combo-stage'),year=by('combo-year');
const el=(tag,text,parent)=>{const n=document.createElement(tag);n.textContent=text;parent.append(n);return n};
[...new Set(d.groups.map(g=>g.year))].sort((a,b)=>a==='ALL'?-1:b==='ALL'?1:a.localeCompare(b)).forEach(v=>el('option',v,year).value=v);
const fmt=v=>v===null||v===undefined?'unavailable':v.toFixed(3)+'%';
function table(id,rows){const t=by(id);t.replaceChildren();const h=el('tr','',t);['UTC year','Filter','N','Missing excluded','Eligible','Matched','Not matched','Matched resolved/complete','Matched censored','Matched rate/mean','Eligible baseline rate/mean','Unfiltered baseline rate/mean'].forEach(v=>el('th',v,h));for(const g of rows){const tr=el('tr','',t),native=g.cohort==='native_pivot',metric=b=>fmt(b[native?'hit_rate_pct':'mean_directional_close_return_pct']);[g.year,g.filter_id,g.n,g.missing_excluded,g.eligible,g.matched_n,g.not_matched,native?g.matched.resolved:g.matched.COMPLETE,g.matched.CENSORED,metric(g.matched),metric(g.eligible_baseline),metric(g.baseline)].forEach(v=>el('td',v,tr));}}
function render(){stage.disabled=cohort.value!=='native_pivot';const rows=d.groups.filter(g=>g.side===side.value&&g.cohort===cohort.value&&g.stage===(stage.disabled?'active_candidate':stage.value));table('combo-results',rows.filter(g=>g.year===year.value));table('combo-chronology',rows.filter(g=>g.year!=='ALL').sort((a,b)=>a.year.localeCompare(b.year)||a.filter_id.localeCompare(b.filter_id)));by('combo-detail').textContent=JSON.stringify({definitions:d.definitions,filters:d.filters.filter(f=>f.side===side.value),selected_rows:rows.filter(g=>g.year===year.value),matched_observations:d.memberships.filter(m=>d.filters.some(f=>f.id===m.filter_id&&f.side===side.value)).map(m=>({...m,records:m.records.filter(r=>r.cohort===cohort.value&&r.stage===(stage.disabled?'active_candidate':stage.value)&&(year.value==='ALL'||new Date(r.known_time).getUTCFullYear().toString()===year.value))}))},null,2);}
[side,cohort,stage,year].forEach(n=>n.onchange=render);render();</script></html>'''.replace('__COMBINATION_DATA__',data)


def visual(packet):
    """Full-cohort summary plus every pivot index; no selected-example substitute."""
    import html
    groups=[g for g in packet['groups'] if g['year']=='ALL']
    cases=[]
    for case in packet['cases']:
        stages={}
        for name,index in case['stages'].items():
            if index is None:continue
            snap=packet['snapshots'][str(index)]
            stages[name]=dict(index=index,known_time=snap['known_time'],close=snap['close'],
                di={k:snap['di'][k] for k in ('di_plus','di_minus','abs_spread','dominant','spread_bin','adx')} if snap['di'] else None,
                events={k:snap['events'][k] for k in ('di_minus_peak','di_plus_peak','spread_peak','di_only_buy_turn','di_only_sell_turn')},
                archived_scores=snap['archived_scores'])
            stages[name]['engine_refs']={k:('UNAVAILABLE' if v.startswith('UNAVAILABLE:') else v) for k,v in snap['engine_refs'].items() if k in ('1h:REGIME','1h:TREND','1h:BIAS','1h:LIQUIDITY','4h:TREND','1d:TREND')}
        cases.append(dict(id=case['id'],side=case['side'],origin_time=case['origin_time'],price=case['price'],outcome=case['outcome']['status'],stages=stages,
            recognition=case['recognition'],pressure_peak_seen_by_origin=case['pressure_peak_seen_by_origin'],spread_peak_seen_by_origin=case['spread_peak_seen_by_origin'],
            pressure_peaks=case['pressure_peaks'],spread_peaks=case['spread_peaks'],spread_peak_lag_bars=case['spread_peak_lag_bars'],post_sell_recovery_ids=case.get('post_sell_recovery_ids')))
    # The per-stage references resolve into the separate row-source engine pool.
    timeline=[[s['known_time'],s['close'],*((s['di'] or {}).get(k) for k in ('di_plus','di_minus','abs_spread'))] for _,s in sorted(packet['snapshots'].items(),key=lambda item:int(item[0]))]
    data=json.dumps(dict(timeline=timeline,context_pool=packet.get('context_pool',{}),groups=groups,cases=cases,counts=packet['counts'],dip_groups=[g for g in packet['dip_groups'] if g['year']=='ALL'],candidate_groups=[g for g in packet['candidate_groups'] if g['year']=='ALL']),separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    text='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>BTC 1h event sequences</title>
<style>body{font:15px system-ui;background:#121b28;color:#e1e7ef;max-width:1250px;margin:auto;padding:16px;overflow-wrap:anywhere}select,button{padding:7px;max-width:100%}table{border-collapse:collapse;width:100%;margin:16px 0}td,th{padding:6px;border-bottom:1px solid #405067;text-align:left}.scroll{overflow:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere}svg{width:100%;height:auto;background:#1a2739;margin:8px 0}details{margin:14px 0}meter{width:90px}</style>
<h1>BTC 1h — candidate, DI and spread sequences</h1><p id="counts"></p><p>All exported pivots; LOW = BUY research point, HIGH = SELL research point. Native outcomes are retrospective, not trading win rates. Candidate start, final extreme and confirmation are separate. Timestamp display: Pakistan time. The JSON contains all candidate updates, all DI+ dip recoveries and full event timelines.</p>
<label>Side <select id="side"><option value="BUY">BUY / lows</option><option value="SELL">SELL / highs</option></select></label>
<label>Stage <select id="stage"><option>candidate_start</option><option>final_extreme_first_recorded</option><option>origin_close</option><option>native_confirmation</option></select></label>
<label>Compare <select id="dimension"></select></label><div class="scroll"><table id="groups"></table></div>
<details><summary>All DI+ down-run/recovery groups (not conditioned on hindsight pivots)</summary><div class="scroll"><table id="dips"></table></div></details>
<details><summary>All candidate observations, including abandoned extrema</summary><p>Next-open outcomes over 12 hours. These are separate from retrospective native-pivot outcomes. No fees, positions or fills simulated.</p><div class="scroll"><table id="candidate_groups"></table></div></details>
<h2>Every pivot</h2><button id="prev">Previous 50</button> <button id="next">Next 50</button><span id="page"></span><div class="scroll"><table id="cases"></table></div><div id="detail"></div>
<script>const d=__DATA__,side=document.querySelector('#side'),stage=document.querySelector('#stage'),dim=document.querySelector('#dimension');let page=0;const el=(tag,text,parent)=>{let n=document.createElement(tag);n.textContent=text;parent.append(n);return n};const stamp=v=>v===null||v===undefined?'unavailable':new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Karachi',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(v))+' PKT';
document.querySelector('#counts').textContent=JSON.stringify(d.counts);[...new Set(d.groups.map(g=>g.dimension))].sort().forEach(k=>{el('option',k,dim).value=k});dim.value='spread_bin';
function draw(c,parent){let begin=Math.max(0,(c.stages.candidate_start?.index??c.stages.origin_close?.index??0)-2),end=Math.min(d.timeline.length-1,Math.max(c.stages.native_confirmation?.index??0,(c.stages.origin_close?.index??0)+6));let rows=d.timeline.slice(begin,end+1);for(let fields of [[1],[2,3,4]]){let svg=document.createElementNS('http://www.w3.org/2000/svg','svg');parent.append(svg);svg.setAttribute('viewBox','0 0 1000 300');let vals=rows.flatMap(r=>fields.map(k=>r[k])).filter(v=>v!==null&&Number.isFinite(v));if(!vals.length)continue;let lo=Math.min(...vals),hi=Math.max(...vals);if(lo===hi){lo--;hi++}let pad=(hi-lo)*.1;lo-=pad;hi+=pad;let node=(tag,a,text)=>{let n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(a).forEach(([k,v])=>n.setAttribute(k,v));if(text!==undefined)n.textContent=text;svg.append(n);return n},x=i=>65+i/Math.max(1,rows.length-1)*900,y=v=>260-(v-lo)/(hi-lo)*220;fields.forEach((k,j)=>{let path='';rows.forEach((r,i)=>{if(r[k]===null)return;path+=((i&&rows[i-1][k]!==null)?'L':'M')+x(i)+','+y(r[k])+' '});node('path',{d:path,fill:'none',stroke:['#55cba2','#f07b82','#e8c46a'][j],'stroke-width':2});node('text',{x:80+160*j,y:22,fill:['#55cba2','#f07b82','#e8c46a'][j]},['','Close price','DI+','DI-','Abs spread'][k])});for(let label of ['candidate_start','origin_close','native_confirmation']){let stage=c.stages[label];if(!stage)continue;let i=stage.index-begin;if(i<0||i>=rows.length)continue;node('line',{x1:x(i),x2:x(i),y1:40,y2:260,stroke:label==='origin_close'?'#b69ae8':'#a1aab6','stroke-dasharray':'4 4'});node('text',{x:x(i)+3,y:label==='origin_close'?55:75,fill:'#ddd','font-size':11},label)}for(let i of [0,rows.length-1])node('text',{x:i?690:60,y:285,fill:'#ddd','font-size':12},stamp(rows[i][0]));for(let n=0;n<4;n++){let v=lo+(hi-lo)*n/3;node('text',{x:2,y:y(v)+4,fill:'#ddd','font-size':11},v.toPrecision(4))}}}
function render(){let table=document.querySelector('#groups');table.replaceChildren();let head=el('tr','',table);['Condition','All','HIT','NO_HIT','Censored','Resolved hit rate'].forEach(k=>el('th',k,head));d.groups.filter(g=>g.side===side.value&&g.stage===stage.value&&g.dimension===dim.value).forEach(g=>{let tr=el('tr','',table);[g.label,g.n,g.HIT||0,g.NO_HIT||0,g.CENSORED||0,g.hit_rate_pct===null?'unavailable':g.hit_rate_pct.toFixed(2)+'%'].forEach(v=>el('td',v,tr))});let rows=d.cases.filter(c=>c.side===side.value),t=document.querySelector('#cases');t.replaceChildren();let h=el('tr','',t);['Origin','Price','Outcome','Candidate observed','DI / spread at candidate','Inspect'].forEach(k=>el('th',k,h));rows.slice(page*50,page*50+50).forEach(c=>{let tr=el('tr','',t),s=c.stages.candidate_start;[stamp(c.origin_time),c.price,c.outcome,stamp(s?.known_time),s?.di?JSON.stringify(s.di):'unavailable'].forEach(v=>el('td',v,tr));el('button','Inspect',el('td','',tr)).onclick=()=>{let detail=document.querySelector('#detail');detail.replaceChildren();el('h3',c.id,detail);draw(c,detail);let shown=JSON.parse(JSON.stringify(c));Object.values(shown.stages).forEach(s=>{s.engine_context=Object.fromEntries(Object.entries(s.engine_refs).map(([k,v])=>[k,d.context_pool[v]||'UNAVAILABLE']))});el('pre',JSON.stringify(shown,null,2),detail)}});document.querySelector('#prev').disabled=page===0;document.querySelector('#next').disabled=(page+1)*50>=rows.length;document.querySelector('#page').textContent=` ${rows.length} pivots, page ${page+1}`;}
side.onchange=()=>{page=0;render()};stage.onchange=dim.onchange=render;document.querySelector('#prev').onclick=()=>{page--;render()};document.querySelector('#next').onclick=()=>{page++;render()};let dt=document.querySelector('#dips'),dh=el('tr','',dt);['Dimension','Group','N','Complete','Up 1% observed','Down 1% observed'].forEach(k=>el('th',k,dh));d.dip_groups.forEach(g=>{let tr=el('tr','',dt);[g.dimension,g.label,g.n,g.COMPLETE||0,g.UP_1PCT||0,g.DOWN_1PCT||0].forEach(v=>el('td',v,tr))});let ct=document.querySelector('#candidate_groups'),ch=el('tr','',ct);['Side','Dimension','Group','N','Complete','Favorable 1% in complete windows','Mean directional close return'].forEach(k=>el('th',k,ch));d.candidate_groups.forEach(g=>{let tr=el('tr','',ct);[g.side,g.dimension,g.label,g.n,g.COMPLETE||0,g.COMPLETE_FAVORABLE_1PCT||0,g.mean_directional_close_return_pct===null?'unavailable':g.mean_directional_close_return_pct.toFixed(3)+'%'].forEach(v=>el('td',v,tr))});render();</script>'''
    page=text.replace('__DATA__',data)
    if 'combination_study' in packet:
        frame='<h2>Combination filtering — separate comparison dimension</h2><iframe title="Combination filters" style="width:100%;height:900px;border:0" srcdoc="'+html.escape(combination_visual(packet['combination_study']),quote=True)+'"></iframe>'
        page=page.replace('<h2>Every pivot</h2>',frame+'<h2>Every pivot</h2>')
    return page


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,default=Path('research_reports/BTC_1pct/BTCUSDT_1h_all-history_1pct_pivots_v1.json.gz'))
    inputs=p.add_mutually_exclusive_group()
    inputs.add_argument('--input',type=Path,help='Existing row-level export for offline analysis, without market databases')
    inputs.add_argument('--analysis-input',type=Path,help='Reuse an existing analysis export; write only separate combination artifacts')
    p.add_argument('--combination-filters',type=Path,help='JSON list of named four/five-condition filters; default fixed descriptive combinations')
    p.add_argument('--output-dir',type=Path,default=Path('research_reports/BTC_1h_sequences'));p.add_argument('--push-report',action='store_true');a=p.parse_args()
    try:
        import os
        if hasattr(os,'nice'):os.nice(10)
        filters=validate_combination_filters(read(a.combination_filters) if a.combination_filters else default_combination_filters())
        if a.analysis_input:
            packet=read(a.analysis_input)
            if packet.get('version')!='btc-hour-pivot-sequences-v1' or packet.get('symbol')!='BTCUSDT' or packet.get('timeframe')!='1h':
                raise ValueError('Use a BTC 1h sequence analysis export')
        else:
            if a.input:source=read(a.input)
            else:
                source=btc_hour_sequence_source.export(read(a.report),progress=lambda r:print(r,flush=True))
                save(a.output_dir/'source_v1.json.gz',source,a.push_report)
            packet=analyze(source,progress=lambda r:print(r,flush=True))
        packet['combination_study']=combination_analysis(packet,filters)
        save(a.output_dir/'combinations_v1.json',packet['combination_study'],a.push_report)
        page=a.output_dir/'combinations_v1.html';page.parent.mkdir(parents=True,exist_ok=True);page.write_text(combination_visual(packet['combination_study']),encoding='utf-8')
        if not a.analysis_input:
            save(a.output_dir/'analysis_v1.json.gz',packet,a.push_report)
            full_page=a.output_dir/'analysis_v1.html';full_page.write_text(visual(packet),encoding='utf-8')
            if a.push_report:
                compressed=full_page.with_suffix('.html.gz');compressed.write_bytes(gzip.compress(full_page.read_bytes(),mtime=0));push_report(compressed)
        if a.push_report:
            push_report(page)
        print(json.dumps(packet['counts'],indent=2));print('Dashboard:',page)
    except (ValueError,OSError,RuntimeError,sqlite3.Error,subprocess.CalledProcessError) as error:p.exit(1,str(error)+'\n')

if __name__=='__main__':main()
