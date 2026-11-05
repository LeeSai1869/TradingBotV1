"""Compare every pivot's stored features before/on/after its origin at a 1% benchmark."""
import argparse
import gzip
import json
from pathlib import Path
import sqlite3
import subprocess
from Section_1_Global_Core import pivot_feature_comparison as research,regime_inputs,data_policy
from study_pivot_moves import push_report


def visual(packet):
    import html
    # Global curves only in the portable viewer; annual diagnostics remain in JSON.
    curves={name:[g for g in groups if g['year']=='ALL'] for name,groups in packet['features'].items()}
    data=json.dumps(dict(offsets=packet['offsets'],features=curves),separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    title=html.escape(packet['symbol']+' '+packet['timeframe']+' · every pivot · 1% benchmark')
    template='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Pivot feature comparison</title>
<style>body{font:16px system-ui;background:#101722;color:#e5e7eb;max-width:1150px;margin:auto;padding:20px}select{max-width:100%;padding:8px}svg{width:100%;height:auto;background:#182233}p{line-height:1.5}table{border-collapse:collapse}td,th{padding:6px;border-bottom:1px solid #49515f}</style>
<h1>__TITLE__</h1><p>__COUNT__ pivots. Low = BUY research point; high = SELL research point. Blue: 1% HIT. Orange: complete NO_HIT. Missing/censored cases remain separate in JSON.</p>
<p>This is retrospective research. Offset 0 is the actual pivot candle, scored using its close. Positive offsets contain later information. They are not inputs to a prediction at the pivot. Means can hide multiple patterns; no rules are automatically selected.</p>
<label>Feature <select id="feature"></select></label> <label>Side <select id="side"><option>BUY_SIDE</option><option>SELL_SIDE</option></select></label><p id="note"></p><svg id="plot" viewBox="0 0 1050 420" aria-label="Mean feature trajectory around every pivot"></svg><div id="counts"></div>
<script>const d=__DATA__;const f=document.querySelector('#feature'),s=document.querySelector('#side'),plot=document.querySelector('#plot'),note=document.querySelector('#note');
Object.keys(d.features).sort().forEach(k=>{let o=document.createElement('option');o.value=o.textContent=k;f.append(o)});if(d.features.di_minus)f.value='di_minus';
const node=(tag,attrs,text)=>{let n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));if(text!==undefined)n.textContent=text;plot.append(n);return n};
function render(){plot.replaceChildren();let groups=(d.features[f.value]||[]).filter(g=>g.side===s.value&&['HIT','NO_HIT'].includes(g.outcome));let vals=groups.flatMap(g=>g.mean).filter(v=>v!==null&&Number.isFinite(v));note.textContent=groups.map(g=>`${g.outcome}: ${g.pivots} pivots`).join(' · ')+' · available observations vary at each offset';if(!vals.length){note.textContent+=' · no usable values';return}let lo=Math.min(...vals),hi=Math.max(...vals);if(lo===hi){lo-=1;hi+=1}let pad=(hi-lo)*.1;lo-=pad;hi+=pad;const x=i=>65+i/Math.max(1,d.offsets.length-1)*920,y=v=>355-(v-lo)/(hi-lo)*290;
for(let i=0;i<5;i++){let v=lo+(hi-lo)*i/4;node('line',{x1:65,x2:985,y1:y(v),y2:y(v),stroke:'#384353'});node('text',{x:3,y:y(v)+4,fill:'#d0d7e0','font-size':12},v.toPrecision(4))}d.offsets.forEach((offset,i)=>{if(offset===0||i===0||i===d.offsets.length-1||offset%6===0)node('text',{x:x(i)-8,y:380,fill:'#d0d7e0','font-size':13},String(offset))});let zero=d.offsets.indexOf(0);if(zero>=0)node('line',{x1:x(zero),x2:x(zero),y1:50,y2:355,stroke:'#d8b75c','stroke-dasharray':'6 4'});
for(let g of groups){let color=g.outcome==='HIT'?'#65b8ff':'#f4a65d',path='';g.mean.forEach((v,i)=>{if(v===null){path+=' ';return}let previous=i>0&&g.mean[i-1]!==null;path+=(previous?'L':'M')+x(i)+','+y(v)+' ';let circle=node('circle',{cx:x(i),cy:y(v),r:3,fill:color});let t=document.createElementNS('http://www.w3.org/2000/svg','title');t.textContent=`offset ${d.offsets[i]}: mean ${v}, n=${g.count[i]}`;circle.append(t)});node('path',{d:path,fill:'none',stroke:color,'stroke-width':2})}node('text',{x:390,y:410,fill:'#d0d7e0'},'Candle offset from actual pivot origin');}
f.onchange=s.onchange=render;render();</script>'''
    return template.replace('__TITLE__',title).replace('__COUNT__',str(packet['pivots'])).replace('__DATA__',data)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--before-bars',type=int,default=12);p.add_argument('--after-bars',type=int,default=24);p.add_argument('--batch-size',type=int,default=24)
    p.add_argument('--push-report',action='store_true');args=p.parse_args()
    try:
        import numpy
        import os
        if hasattr(os,'nice'):os.nice(10)
        data=args.report.read_bytes();report=json.loads(gzip.decompress(data) if args.report.suffix=='.gz' else data)
        with data_policy.snapshot_guard(timeout=1):
            conn=regime_inputs.open_sources()
            try:
                from Section_1_Global_Core import intelligence_audit,pivot_context_audit
                with intelligence_audit.reader() as engines:
                    reader=pivot_context_audit.LocalReader(conn,engines,report)
                    packet=research.compare(conn,report,before=args.before_bars,after=args.after_bars,batch_size=args.batch_size,context_reader=reader,progress=lambda row:print(row,flush=True))
            finally:conn.close()
        data=(json.dumps(packet,separators=(',',':'),allow_nan=False)+'\n').encode();page=visual(packet)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        if args.output.suffix=='.gz':data=gzip.compress(data,mtime=0)
        temp=args.output.with_name(args.output.name+'.partial');temp.write_bytes(data);temp.replace(args.output)
        print('Saved:',args.output,dict(pivots=packet['pivots'],numeric_features=len(packet['features']),origin_outcomes=packet['origin_outcomes']),flush=True)
        if args.push_report:push_report(args.output)
        page_path=args.output.with_suffix('').with_suffix('.html') if args.output.suffix=='.gz' else args.output.with_suffix('.html')
        page_path.write_text(page,encoding='utf-8')
        if args.push_report:push_report(page_path)
        print('Visual comparison:',page_path)
    except ImportError:p.exit(1,'Install optional research dependencies: python3 -m pip install -r requirements-research.txt\n')
    except (ValueError,OSError,RuntimeError,sqlite3.Error,subprocess.CalledProcessError) as error:p.exit(1,str(error)+'\n')

if __name__=='__main__':main()
