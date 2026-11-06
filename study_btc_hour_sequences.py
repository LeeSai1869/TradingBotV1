"""Full BTC 1h candidate/DI/spread/context study; row export plus offline analysis."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sqlite3
from Section_1_Global_Core import btc_hour_sequence_source
from Section_8_Decision_Engine.pivot_sequences import analyze
from study_pivot_moves import push_report


def read(path):
    data=path.read_bytes();return json.loads(gzip.decompress(data) if path.suffix=='.gz' else data)


def save(path,packet,publish):
    payload=(json.dumps(packet,separators=(',',':'),allow_nan=False)+'\n').encode()
    if path.suffix=='.gz':payload=gzip.compress(payload,mtime=0)
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.partial');temp.write_bytes(payload);temp.replace(path)
    print('Saved:',path,len(payload),'bytes',flush=True)
    if publish:push_report(path)


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
    return text.replace('__DATA__',data)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,default=Path('research_reports/BTC_1pct/BTCUSDT_1h_all-history_1pct_pivots_v1.json.gz'))
    p.add_argument('--input',type=Path,help='Existing row-level export for offline analysis, without market databases')
    p.add_argument('--output-dir',type=Path,default=Path('research_reports/BTC_1h_sequences'));p.add_argument('--push-report',action='store_true');a=p.parse_args()
    try:
        import os
        if hasattr(os,'nice'):os.nice(10)
        if a.input:source=read(a.input)
        else:
            source=btc_hour_sequence_source.export(read(a.report),progress=lambda r:print(r,flush=True))
            save(a.output_dir/'source_v1.json.gz',source,a.push_report)
        packet=analyze(source,progress=lambda r:print(r,flush=True))
        save(a.output_dir/'analysis_v1.json.gz',packet,a.push_report)
        page=a.output_dir/'analysis_v1.html';page.parent.mkdir(parents=True,exist_ok=True);page.write_text(visual(packet),encoding='utf-8')
        if a.push_report:push_report(page)
        print(json.dumps(packet['counts'],indent=2));print('Dashboard:',page)
    except (ValueError,OSError,RuntimeError,sqlite3.Error,subprocess.CalledProcessError) as error:p.exit(1,str(error)+'\n')

if __name__=='__main__':main()
