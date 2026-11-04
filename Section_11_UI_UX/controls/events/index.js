// Manual, bounded research view. No chart overlays, decision changes or poller.
function el(tag,text,parent){const node=document.createElement(tag);node.textContent=text;parent?.append(node);return node;}
const utc=value=>value==null?'Unknown':new Date(value).toISOString().replace('T',' ').slice(0,19)+' UTC';
export function mountEvents(parent){
    const section=el('section','',parent);el('h3','Historical events',section);
    el('p','Research only. Candidates can move or clear without becoming confirmed swings. Knowledge times are reconstructed candle closes.',section);
    const form=el('form','',section),controls=el('div','',form);controls.style.display='flex';controls.style.flexWrap='wrap';controls.style.gap='8px';
    const label=(text)=>el('label',text+' ',controls);
    const symbol=el('input','',label('Event symbol'));symbol.value=window.DataCache?.symbol||document.getElementById('symbol')?.value||'BTCUSDT';symbol.size=12;symbol.setAttribute('aria-label','Event symbol');
    const tf=el('select','',label('Event timeframe'));tf.setAttribute('aria-label','Event timeframe');
    for(const value of ['1m','5m','15m','30m','1h']){const option=el('option',value,tf);option.value=value;}
    tf.value=['1m','5m','15m','30m','1h'].includes(window.DataCache?.timeframe)?window.DataCache.timeframe:'5m';
    const limit=el('select','',label('Candles'));limit.setAttribute('aria-label','Event candles');
    for(const value of [100,250,500,1000]){const option=el('option',String(value),limit);option.value=String(value);}limit.value='250';
    const filter=el('select','',label('Stage'));filter.setAttribute('aria-label','Event stage');
    for(const value of ['ALL','CANDIDATE','CONFIRMED','REFERENCE']){const option=el('option',value,filter);option.value=value;}
    const before=el('input','',label('Before (UTC)'));before.type='datetime-local';before.setAttribute('aria-label','Events before UTC');
    const load=el('button','Load events',controls);load.type='submit';
    const older=el('button','Older events',controls);older.type='button';older.disabled=true;
    const info=el('p','Choose a symbol/timeframe and load a bounded window.',section);info.setAttribute('role','status');
    const definitions=el('details','',section);el('summary','Event catalogue',definitions);const catalogue=el('div','',definitions);
    const scroll=el('div','',section);scroll.style.overflow='auto';scroll.style.maxHeight='520px';
    const table=el('table','',scroll);table.setAttribute('aria-label','Historical events');let packet=null,busy=false;
    function render(){
        table.replaceChildren();if(!packet)return;
        const head=el('tr','',el('thead','',table));for(const value of ['Known at close','Event','Stage','Value','Qualified','Origin','Inspect'])el('th',value,head);
        const body=el('tbody','',table);const rows=packet.events.filter(event=>filter.value==='ALL'||event.stage===filter.value);
        for(const event of [...rows].reverse()){
            const row=el('tr','',body);el('td',utc(event.known_time),row);
            el('td',event.type.replaceAll('_',' ')+(event.channel?' · '+event.channel:''),row);el('td',event.stage,row);
            el('td',event.value==null?'—':String(Number(event.value.toPrecision(8))),row);el('td',typeof event.details.qualified==='boolean'?(event.details.qualified?'Yes':'No'):'—',row);el('td',utc(event.origin_time),row);
            const cell=el('td','',row);const jump=el('button','Chart',cell);jump.type='button';jump.title='Jump to the observation candle; the event is known at its close';
            jump.onclick=()=>{
                const reference={symbol:event.symbol,interval:event.timeframe,bar_time:event.observed_open};
                if(window.openAlertChart)Promise.resolve(window.openAlertChart(reference)).catch(error=>info.textContent=error.message);
                else window.location.assign('/?'+new URLSearchParams({symbol:event.symbol,interval:event.timeframe,at:String(event.observed_open)}));
            };
            const detail=el('details','',cell);el('summary','Evidence',detail);el('pre',JSON.stringify(event,null,2),detail);
        }
        if(!rows.length){const cell=el('td','No matching events in this loaded window.',el('tr','',body));cell.colSpan=7;}
        info.textContent=packet.status!=='READY'?(packet.reason||'Sources unavailable'):`${packet.symbol} ${packet.timeframe} · ${packet.scanned} candles inspected · ${rows.length} displayed events · current committed feature generation. ${packet.events_trimmed?'Response capped; use Older events. ':''}${packet.warnings?.map(note=>note.message).join('; ')||''}`;
    }
    async function fetchWindow(bound){
        if(busy)return;busy=true;load.disabled=true;older.disabled=true;for(const node of [symbol,tf,limit,before,filter])node.disabled=true;info.textContent='Reading committed history…';
        try{
            const query=new URLSearchParams({symbol:symbol.value.trim().toUpperCase(),interval:tf.value,limit:limit.value});if(bound!=null)query.set('before',String(bound));
            const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);let response;
            try{response=await fetch('/api/events/history?'+query,{cache:'no-store',signal:controller.signal});packet=await response.json();}finally{clearTimeout(timer);}
            if(!response.ok)throw Error(packet.error||'Event history request failed');
            catalogue.replaceChildren();for(const [type,definition] of Object.entries(packet.catalog.events))el('p',`${type} · ${definition.stage}: ${definition.description}`,catalogue);
            if(packet.source_identity)el('pre',JSON.stringify(packet.source_identity,null,2),catalogue);
            render();older.disabled=!packet.has_more||packet.next_before==null;
        }catch(error){packet=null;table.replaceChildren();info.textContent=error.name==='AbortError'?'Event request timed out; try a smaller window.':error.message;}
        finally{busy=false;load.disabled=false;for(const node of [symbol,tf,limit,before,filter])node.disabled=false;}
    }
    form.onsubmit=event=>{event.preventDefault();const bound=before.value?Date.parse(before.value+'Z'):null;if(bound!==null&&!Number.isFinite(bound)){info.textContent='Choose a valid UTC date';return;}void fetchWindow(bound);};
    older.onclick=()=>void fetchWindow(packet?.next_before);filter.onchange=render;
    for(const control of [symbol,tf,limit,before])control.addEventListener('change',()=>{packet=null;older.disabled=true;table.replaceChildren();info.textContent='Selection changed. Load events for the new selection.';});
}
