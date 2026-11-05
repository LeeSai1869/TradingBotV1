// Manual cohort inspection. Never scans history or changes strategy from the UI.
const el=(tag,text,parent)=>{const node=document.createElement(tag);node.textContent=text;parent?.append(node);return node;};
const utc=value=>Number.isFinite(value)?new Date(value).toISOString().slice(0,19).replace('T',' ')+'Z':'—';
const pct=value=>Number.isFinite(value)?value.toFixed(2)+'%':'—';
export function mountPivotResearch(parent){
    const section=el('section','',parent);el('h3','Historical pivot moves ≥2%',section);
    el('p','Load a study report generated from stored history. This selects outcomes retrospectively; it does not generate BUY/SELL signals or prove cause.',section);
    const file=el('input','',section);file.type='file';file.accept='.json,.gz';file.setAttribute('aria-label','Pivot study report');
    const controls=el('div','',section);Object.assign(controls.style,{display:'flex',gap:'6px',flexWrap:'wrap'});
    const select=(label,values)=>{const node=el('select','',el('label',label+' ',controls));node.setAttribute('aria-label',label);for(const [value,text] of values){const option=el('option',text,node);option.value=value;}return node;};
    const filter=select('Pivot outcome',[['ORIGIN_HIT','2% from pivot'],['KNOWN_HIT','2% after known'],['NO_HIT','Complete non-hits'],['ALL','All pivots']]);
    const side=select('Pivot side',[['ALL','Both sides'],['BUY_SIDE','Low → upward'],['SELL_SIDE','High → downward']]);
    const input=(name,value)=>{const node=el('input','',el('label',name+' ',controls));node.type='number';node.min=0;node.max=100;node.value=value;node.style.width='65px';node.setAttribute('aria-label',name);return node;};
    const before=input('Bars before',12),after=input('Bars after',24);
    const prev=el('button','Previous cases',controls),next=el('button','Next cases',controls);
    const info=el('p','Generate and load a pivot study report to begin.',section);info.setAttribute('role','status');
    const casesWrap=el('div','',section);casesWrap.style.overflow='auto';const casesTable=el('table','',casesWrap);casesTable.setAttribute('aria-label','Pivot move cases');
    const detail=el('div','',section);let report=null,page=0,selection=0,featureChart=null;
    const disposePlot=()=>{featureChart?.remove();featureChart=null;};
    const clearVisual=()=>window.dispatchEvent(new CustomEvent('pivot-research-case',{detail:null}));
    const matches=()=>report?.cases.filter(c=>(side.value==='ALL'||c.side===side.value)&&(filter.value==='ALL'||filter.value==='ORIGIN_HIT'&&c.origin.status==='HIT'||filter.value==='KNOWN_HIT'&&c.after_known.status==='HIT'||filter.value==='NO_HIT'&&c.origin.status==='NO_HIT'))||[];
    function render(){
        casesTable.replaceChildren();const rows=matches();const head=el('tr','',el('thead','',casesTable));for(const name of ['Pivot UTC','Side','From pivot','After known','Bars to 2%','Known UTC','Inspect'])el('th',name,head);
        const body=el('tbody','',casesTable);
        for(const item of rows.slice(page*50,page*50+50)){
            const row=el('tr','',body),p=item.pivot;
            for(const value of [utc(p.origin_time),item.side==='BUY_SIDE'?'LOW ↑':'HIGH ↓',pct(item.origin.max_favorable_pct)+' · '+item.origin.status+(item.origin.complete===false?' (partial)':''),pct(item.after_known.max_favorable_pct)+' · '+item.after_known.status,String(item.origin.first_hit?.bars??'—'),utc(p.known_time)])el('td',value,row);
            const button=el('button','Inspect pivot',el('td','',row));button.onclick=()=>void inspect(item);
        }
        prev.disabled=page===0;next.disabled=(page+1)*50>=rows.length;
        if(report)info.textContent=`${report.symbol} ${report.timeframe} · ${report.cases.length} pivots in cohort · ${rows.length} match · page ${page+1} · ${report.config.horizon_bars??'next opposite pivot'} · ${report.config.threshold_pct}% threshold. Origin selection uses hindsight; after-known outcome is separate.`;
    }
    async function inspect(item){
        const token=++selection;disposePlot();clearVisual();detail.replaceChildren();const status=el('p','Loading full feature window…',detail);
        try{
            const b=Number(before.value),a=Number(after.value);if(!Number.isInteger(b)||!Number.isInteger(a)||b<0||a<0||b>100||a>100)throw Error('Choose 0..100 context bars');
            let packet=report.contexts?.[item.id];
            if(!packet||report.context_config?.before!==b||report.context_config?.after!==a){
                const query=new URLSearchParams({symbol:report.symbol,interval:report.timeframe,id:item.id,known:String(item.pivot.known_time),source:report.source_id,before:String(b),after:String(a),as_of:String(report.observed_as_of)});
                const response=await fetch('/api/pivots/context?'+query,{cache:'no-store',signal:AbortSignal.timeout(15000)});packet=await response.json();if(!response.ok)throw Error(packet.error||'Context unavailable');
            }
            if(token!==selection)return;
            if(packet.status!=='READY')throw Error(packet.reason||'Context unavailable');
            status.textContent=`Pivot ${utc(item.pivot.origin_time)} · known ${utc(item.pivot.known_time)} · ${packet.bars.length} context candles · ${item.origin_hit_by_confirmation?'2% was already reached by confirmation.':'Compare origin and after-known outcomes.'}`;
            const actions=el('div','',detail),jump=el('button','Show pivot on chart',actions),save=el('button','Save case JSON',actions);
            jump.onclick=async()=>{
                try{if(window.openAlertChart)await window.openAlertChart({symbol:report.symbol,interval:report.timeframe,bar_time:item.pivot.origin_time});window.dispatchEvent(new CustomEvent('pivot-research-case',{detail:{...packet,case:item,threshold_pct:report.config.threshold_pct}}));}
                catch(error){status.textContent=error.message;}
            };
            save.onclick=()=>{const blob=new Blob([JSON.stringify({...packet,case:item},null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`${report.symbol}_${report.timeframe}_${item.id.slice(0,12)}_pivot.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
            const fields=[...new Set(packet.bars.flatMap(row=>Object.keys(row.features||{})))].sort();
            const label=el('label','Additional feature ',detail),choice=el('select','',label);choice.setAttribute('aria-label','Pivot feature');choice.style.maxWidth='100%';el('option','Choose any stored feature',choice).value='';for(const key of fields)el('option',key,choice).value=key;
            const plotNote=el('p','',detail),plot=el('div','',detail);plot.style.height='180px';plot.style.width='100%';plot.setAttribute('aria-label','Pivot feature plot');
            function drawPlot(){
                disposePlot();
                const keys=choice.value?[choice.value]:['di_plus','di_minus','adx'];
                plotNote.textContent=keys.join(' / ')+' · historical context';
                if(!window.LightweightCharts){plotNote.textContent+=' · chart library unavailable';return;}
                featureChart=LightweightCharts.createChart(plot,{autoSize:true,height:180,layout:{background:{color:'#151a22'},textColor:'#bfc9d7'},timeScale:{timeVisible:true,secondsVisible:false}});
                let lines=0;keys.forEach((key,index)=>{
                    const segments=[];let data=[],previous=null;
                    for(const record of packet.bars){
                        if(!Number.isFinite(record.features[key])||(previous&&record.client.open_time!==previous.close_time+1)){if(data.length)segments.push(data);data=[];}
                        if(Number.isFinite(record.features[key]))data.push({time:record.client.open_time/1000,value:record.features[key]});
                        previous=record.client;
                    }
                    if(data.length)segments.push(data);
                    segments.forEach((data,i)=>{const line=featureChart.addSeries(LightweightCharts.LineSeries,{color:['#4ecda7','#ee6c78','#e8c56b'][index%3],lineWidth:2,title:i===segments.length-1?key:'',lastValueVisible:i===segments.length-1,priceLineVisible:false});line.setData(data);lines++;});
                });
                if(!lines)plotNote.textContent='Selected feature is nonnumeric or unavailable; inspect the table below.';
                featureChart.timeScale().fitContent();
            }
            const scroll=el('div','',detail);scroll.style.overflow='auto';scroll.style.maxHeight='500px';const table=el('table','',scroll);table.setAttribute('aria-label','Pivot candle features');
            function features(){
                table.replaceChildren();const chosen=[...new Set(['di_plus','di_minus','adx','rsi','atr','current_structure','candidate_pivot',choice.value].filter(Boolean))];
                const head=el('tr','',el('thead','',table));for(const name of ['UTC','Stage','Open','High','Low','Close','Volume',...chosen,'All stored values'])el('th',name,head);
                const body=el('tbody','',table);
                for(const record of packet.bars){
                    const row=el('tr','',body);if(record.client.open_time===item.pivot.origin_time)row.style.outline='1px solid #bba0f5';
                    for(const value of [utc(record.client.open_time),record.feature_status==='VALID'?record.availability:record.feature_status,...['open','high','low','close','volume'].map(k=>record.client[k]),...chosen.map(k=>record.features[k])]){
                        const text=value==null?'—':typeof value==='object'?JSON.stringify(value):String(value),cell=el('td',text.length>90?text.slice(0,90)+'…':text,row);cell.title=text;
                    }
                    const all=el('details','',el('td','',row));el('summary','All features',all);el('pre',JSON.stringify(record.features,null,2),all);
                }
            }
            choice.onchange=()=>{features();drawPlot();};features();drawPlot();
        }catch(error){if(token===selection)status.textContent=error.message;}
    }
    file.onchange=async()=>{
        const token=++selection;disposePlot();clearVisual();detail.replaceChildren();casesTable.replaceChildren();report=null;page=0;prev.disabled=next.disabled=true;
        try{
            const chosen=file.files[0];if(!chosen)return;if(chosen.size>100*1024*1024)throw Error('Choose a report below 100 MiB');
            const stream=chosen.name.endsWith('.gz')?chosen.stream().pipeThrough(new DecompressionStream('gzip')):chosen.stream();
            const reader=stream.getReader(),chunks=[];let total=0;
            while(true){const {value,done}=await reader.read();if(done)break;total+=value.length;if(total>256*1024*1024){await reader.cancel();throw Error('Expanded report exceeds 256 MiB; export fewer embedded contexts');}chunks.push(value);}
            const packet=JSON.parse(await new Blob(chunks).text());
            if(packet.version!=='pivot-moves-v1'||!Array.isArray(packet.cases)||packet.cases.length>200000)throw Error('Choose a pivot-moves-v1 cohort report');
            if(token!==selection)return;
            report=packet;before.value=packet.context_config?.before??12;after.value=packet.context_config?.after??24;render();
        }catch(error){info.textContent=error.message;}
    };
    for(const node of [filter,side])node.onchange=()=>{page=0;render();};prev.onclick=()=>{page--;render();};next.onclick=()=>{page++;render();};prev.disabled=next.disabled=true;
}
