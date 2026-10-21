import {getSeries} from '../../overlays/candles/index.js';
import {TOOLS,fibLevels,normalizeDrawings} from './geometry.js';
export const name='drawings';
const NS='http://www.w3.org/2000/svg';
let capture;
let chart,svg,select={value:'pointer'},hint,popup,buttons=[],drawings=[],draft=[],selected=-1,key='',drag=null,undo=[],frame=0,state,toolStatus;
const collections=new Map();
const INTERVALS=['1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h','1d','3d','1w','1M'];
let width=0,height=0,paneNode,observer,lastTimeframe='';
function schedule(){if(!frame)frame=requestAnimationFrame(()=>{frame=0;render();});}
function node(tag,attrs,parent=svg,text){const n=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;parent.append(n);return n;}
async function request(symbol,data){
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),10000);
    try{
        const response=await fetch('/api/drawings'+(data?'':'?symbol='+encodeURIComponent(symbol)),data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,symbol}),signal:controller.signal}:{cache:'no-store',signal:controller.signal});
        if(response.status===404)throw Error('Drawing service missing. Restart the updated UI server.');
        const result=await response.json();if(!response.ok){const error=Error(result.error||'Drawing memory unavailable');error.status=response.status;throw error;}return result;
    }finally{clearTimeout(timeout);}
}
let noticeTimer;
function feedback(text){clearTimeout(noticeTimer);hint.textContent=text;toolStatus.title=text;hint.hidden=text==='Select a drawing to style it.';if(text==='Drawings saved to your account.')noticeTimer=setTimeout(()=>hint.hidden=true,2500);}
async function load(current,quiet=false){
    if(current.loading)return;current.loading=true;
    try{
        const packet=await request(current.symbol);
        if(!current.ready){
            const prefix=`tradingbot.drawings.v1.${window.AppSession?.username||'user'}.${current.symbol}.`;
            let legacyKeys=[];try{legacyKeys=Object.keys(localStorage).filter(k=>k.startsWith(prefix));}catch{}
            const imported=[];
            for(const k of legacyKeys){
                const tf=k.slice(prefix.length);if(!INTERVALS.includes(tf))continue;
                let items=[];try{items=normalizeDrawings(JSON.parse(localStorage.getItem(k)||'[]'));}catch{}
                for(const d of items){
                    d.anchors=d.anchors.map(a=>{
                        const match=tf.match(/^(\d+)([mhdwM])$/),unit={m:60,h:3600,d:86400,w:604800,M:2592000};
                        let seconds=Number(match[1])*unit[match[2]];
                        if(tf==='1M'){const date=new Date(a.time*1000);const next=new Date(date);next.setUTCMonth(next.getUTCMonth()+1);seconds=(next-date)/1000;}
                        return {time:a.time+a.offset*seconds,offset:0,price:a.price};
                    });d.timeframes=[tf];imported.push(d);
                }
            }
            if(imported.length && packet.drawings.length+imported.length<=500){
                const result=await request(current.symbol,{revision:packet.revision,drawings:[...packet.drawings,...imported]});
                packet.revision=result.revision;packet.drawings.push(...imported);legacyKeys.forEach(k=>localStorage.removeItem(k));
            }
        }
        if(current.saving||current.pending||packet.revision<current.revision)return;
        if(packet.revision!==current.revision || !current.ready){
            current.revision=packet.revision;current.drawings=packet.drawings;current.ready=true;current.error=false;
            if(state===current){drawings=current.drawings;selected=-1;undo=[];popup?.close();schedule();}
        }
        if(state===current){buttons.forEach(b=>b.disabled=false);feedback('Drawings saved to your account.');}
    }catch(error){if(state===current && !quiet)feedback(error.message);}
    finally{current.loading=false;}
}
async function store(){
    const current=state;current.drawings=drawings;current.pending=JSON.parse(JSON.stringify(drawings));
    if(current.saving)return;current.saving=true;
    try{
        while(current.pending){const snapshot=current.pending;current.pending=null;
            const result=await request(current.symbol,{revision:current.revision,drawings:snapshot});current.revision=result.revision;
        }
        if(state===current){toolStatus.setAttribute('aria-label','Reload drawings');buttons.forEach(b=>b.disabled=false);feedback('Drawings saved to your account.');}
    }catch(error){current.error=true;current.conflict=error.status===409;current.pending=JSON.parse(JSON.stringify(current.drawings));if(state===current){mode();buttons.forEach(b=>b.disabled=true);toolStatus.setAttribute('aria-label',current.conflict?'Reload drawings':'Retry saving drawings');feedback(error.message+(current.conflict?' Reload drawings to use the server version.':' Drawing is unsaved. Use Retry saving drawings.'));}}
    finally{current.saving=false;}
}
function remember(){undo.push(JSON.stringify(drawings));if(undo.length>50)undo.shift();}
function mode(value='pointer'){
    select.value=value;draft=[];svg.dataset.active=String(value!=='pointer');if(capture)capture.hidden=value==='pointer';
    buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tool===value)));
    chart.applyOptions({handleScroll:value==='pointer',handleScale:value==='pointer'});
    feedback(value==='pointer'?'Select a drawing to style it.':`Click ${TOOLS[value]} ${TOOLS[value]===1?'point':'points'} on the chart. Escape cancels.`);schedule();
}
function market(){
    const cache=window.DataCache;if(!cache?.symbol)return;
    if(cache.timeframe!==lastTimeframe){lastTimeframe=cache.timeframe;selected=-1;popup?.close();if(svg)mode();}
    if(cache.symbol===key)return;
    key=cache.symbol;popup?.close();state=collections.get(key);
    if(!state){state={symbol:key,drawings:[],revision:0,ready:false};collections.set(key,state);}
    drawings=state.drawings;selected=-1;drag=null;undo=[];mode();buttons.forEach(b=>b.disabled=!state.ready||state.error);if(!state.ready)feedback('Loading account drawings…');void load(state);
}
function anchor(x,y){
    const bars=window.DataCache?.renderBars||[],logical=chart.timeScale().coordinateToLogical(x),price=getSeries()?.coordinateToPrice(y);
    if(!bars.length || logical==null || price==null || !Number.isFinite(price))return null;
    const index=Math.max(0,Math.min(bars.length-1,Math.round(logical)));
    const seconds=(bars[index].client.close_time-bars[index].open_time+1)/1000;
    return {time:bars[index].time+(logical-index)*seconds,offset:0,price};
}
function point(a){
    const bars=window.DataCache?.renderBars||[];if(!bars.length)return null;
    let lo=0,hi=bars.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(bars[mid].time<=a.time)lo=mid;else hi=mid-1;}
    const base=bars[lo],seconds=(base.client.close_time-base.open_time+1)/1000;
    const x=chart.timeScale().timeToCoordinate(base.time),y=getSeries()?.priceToCoordinate(a.price);
    return x==null || y==null?null:{x:x+((a.time-base.time)/seconds+a.offset)*chart.timeScale().options().barSpacing,y,price:a.price};
}
function stroke(a,b,parent,color='#58b9ff',hit=false,style={}){
    return node('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:hit?'transparent':color,'stroke-width':hit?12:(style.width||2),'stroke-dasharray':style.pattern==='dashed'?'8 5':style.pattern==='dotted'?'2 4':'',
        class:hit?'drawing-hit':'','pointer-events':hit?'stroke':'none'},parent);
}
function render(){
    market();svg.replaceChildren();
    const pane=chart.panes()[0];if(!pane)return;
    if(pane.getHTMLElement()!==paneNode){if(paneNode)observer.unobserve(paneNode);paneNode=pane.getHTMLElement();if(paneNode)observer.observe(paneNode);}
    width=chart.timeScale().width();height=pane.getHeight();svg.style.width=width+'px';svg.style.height=height+'px';svg.setAttribute('viewBox',`0 0 ${width} ${height}`);if(capture){capture.style.width=width+'px';capture.style.height=height+'px';}
    function paint(d,index){
        if(d.timeframes?.length && !d.timeframes.includes(window.DataCache.timeframe))return;
        const style=d.style||{},color=style.color||"#58b9ff";
        const points=d.anchors.map(point);if(points.some(p=>!p))return;
        const group=node('g',{'data-drawing':index,'data-type':d.type});
        const hit=select.value==='pointer' && index>=0;
        function segment(a,b){stroke(a,b,group,color,false,style);if(hit)stroke(a,b,group,color,true,style);}
        const [a,b]=points;
        if(d.type==='horizontal')segment({x:0,y:a.y},{x:width,y:a.y});
        else if(d.type==='line')segment(a,b);
        else if(d.type==='rectangle'){
            const corners=[a,{x:b.x,y:a.y},b,{x:a.x,y:b.y}];
            node('rect',{x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.abs(b.x-a.x),height:Math.abs(b.y-a.y),fill:color,'fill-opacity':style.fillOpacity??.1,'pointer-events':'none'},group);
            corners.forEach((p,i)=>segment(p,corners[(i+1)%4]));
        }else{
            for(let i=1;i<points.length;i++)stroke(points[i-1],points[i],group,'#718096');
            const left=Math.min(...points.map(p=>p.x)), right=Math.max(...points.map(p=>p.x))+(d.type==='extension'?120:0);
            for(const level of fibLevels(d.type,points)){
                const y=getSeries().priceToCoordinate(level.price);if(y==null)continue;
                const levelColor=color;
                segment({x:left,y},{x:right,y});
                node('text',{x:left+4,y:y-4,fill:levelColor,'font-size':10,'pointer-events':'none'},group,`${(level.ratio*100).toFixed(2)}% · ${getSeries().priceFormatter().format(level.price)}`);
            }
        }
        if(hit && index===selected && !d.locked)points.forEach((p,i)=>node('circle',{cx:p.x,cy:p.y,r:5,fill:'#111',stroke:'#fff','stroke-width':1.5,class:'drawing-handle','data-anchor':i},group));
    }
    drawings.forEach(paint);
    if(draft.length){
        const required=TOOLS[select.value];
        if(draft.length===required)paint({type:select.value,anchors:draft},-1);
        else for(const a of draft){const p=point(a);if(p)node('circle',{cx:p.x,cy:p.y,r:4,fill:'#f5c542','pointer-events':'none'});}
    }
}
function local(event){const bounds=svg.getBoundingClientRect();return {x:event.clientX-bounds.left,y:event.clientY-bounds.top};}
function edit(){
    const drawing=drawings[selected];if(!drawing)return;
    popup.replaceChildren();
    const form=document.createElement('form');popup.append(form);
    const heading=document.createElement('strong');heading.textContent='Drawing style';form.append(heading);
    function input(label,type,value,options){
        const row=document.createElement('label');row.textContent=label+' ';form.append(row);
        const control=document.createElement(type==='select'?'select':'input');control.setAttribute('aria-label',label);
        if(type==='select')for(const [v,title] of options){const o=document.createElement('option');o.value=v;o.textContent=title;control.append(o);}
        else control.type=type;
        if(type==='checkbox')control.checked=value;else control.value=value;
        row.append(control);return control;
    }
    const style=drawing.style||{};
    const color=input('Drawing color','color',style.color||'#58b9ff');
    const width=input('Drawing width','select',style.width||2,[1,2,3,4].map(n=>[n,n+' px']));
    const pattern=input('Drawing line style','select',style.pattern||'solid',[['solid','Solid'],['dashed','Dashed'],['dotted','Dotted']]);
    const opacity=input('Zone fill opacity','range',style.fillOpacity??.1);opacity.min=0;opacity.max=1;opacity.step=.05;opacity.disabled=drawing.type!=='rectangle';
    const locked=input('Lock position','checkbox',drawing.locked);
    const all=input('All timeframes','checkbox',!drawing.timeframes?.length);
    const frames=document.createElement('div');frames.className='drawing-timeframes';form.append(frames);
    const choices=INTERVALS.map(tf=>{
        const row=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.value=tf;box.checked=drawing.timeframes?.includes(tf)||false;box.setAttribute('aria-label',`Drawing timeframe ${tf}`);row.append(box,tf);frames.append(row);return box;
    });
    const sync=()=>{choices.forEach(box=>box.disabled=all.checked);};all.onchange=sync;sync();
    const status=document.createElement('p');status.setAttribute('role','status');form.append(status);
    const actions=document.createElement('div');actions.className='drawing-actions';form.append(actions);
    function action(label,fn){const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=fn;actions.append(b);}
    action('Apply drawing',()=>{
        if(!state.ready||state.error)return;
        const timeframes=all.checked?[]:choices.filter(box=>box.checked).map(box=>box.value);
        if(!all.checked&&!timeframes.length){status.textContent='Choose at least one timeframe.';return;}
        remember();drawing.style={color:color.value,width:Number(width.value),pattern:pattern.value,fillOpacity:Number(opacity.value)};drawing.locked=locked.checked;drawing.timeframes=timeframes;
        void store();popup.close();schedule();
    });
    action('Delete drawing',()=>{if(!state.ready||state.error)return;remember();drawings.splice(selected,1);selected=-1;void store();popup.close();schedule();});
    action('Close',()=>popup.close());
    form.onsubmit=event=>event.preventDefault();
    popup.onkeydown=event=>{if(event.key==='Escape'){event.stopPropagation();popup.close();}};
    if(!popup.open)popup.show();
}
export function mount(instance){
    chart=instance;
    const controls=document.createElement('div');controls.className='drawing-tools';controls.setAttribute('aria-label','Drawing tools');document.getElementById('toolbar').append(controls);
    function button(label,symbol,action){const b=document.createElement('button');b.textContent=symbol;b.setAttribute('aria-label',label);b.title=label;b.onclick=action;controls.append(b);return b;}
    for(const [value,label,icon] of [['pointer','Select drawing','↖'],['line','Trend line','╱'],['rectangle','Rectangle zone','▭'],['horizontal','Horizontal line','―'],['retracement','Fib retracement','≋'],['extension','Fib extension','↗']]){
        const b=button(label,'',()=>{popup.close();mode(select.value===value?'pointer':value);});b.dataset.tool=value;buttons.push(b);
        const iconSvg=node('svg',{viewBox:'0 0 24 24',width:18,height:18,'aria-hidden':'true'},b);
        const paths={pointer:'M5 3 L5 18 L10 13 L14 21 L17 19 L13 12 L20 12 Z',line:'M4 20 L20 4 M3 18 L6 21 M18 3 L21 6',rectangle:'M3 5 H21 V19 H3 Z',horizontal:'M2 12 H22',retracement:'M3 4 H21 M3 9 H17 M3 14 H21 M3 20 H14',extension:'M3 20 L8 12 L12 16 L19 4 M12 4 H22 M12 9 H22 M12 14 H22'};
        node('path',{d:paths[value],fill:'none',stroke:'currentColor','stroke-width':1.5,'stroke-linecap':'round','stroke-linejoin':'round'},iconSvg);
    }
    button('Undo drawing','↶',()=>{if(!state?.ready||state.error||!undo.length)return;drawings=JSON.parse(undo.pop());selected=-1;popup.close();void store();schedule();});
    toolStatus=button('Reload drawings','↻',()=>{if(!state||state.saving)return;if(state.error&&!state.conflict&&state.pending){state.error=false;void store();return;}state.pending=null;state.ready=false;buttons.forEach(b=>b.disabled=true);void load(state);});
    hint=document.createElement('span');hint.className='drawing-notice';hint.setAttribute('role','status');document.getElementById('chart').append(hint);
    popup=document.createElement('dialog');popup.className='drawing-popup';popup.setAttribute('aria-label','Drawing style');document.body.append(popup);
    svg=node('svg',{'id':'drawing-overlay','aria-label':'Chart drawings'},document.getElementById('chart'));
    capture=document.createElement('div');capture.id='drawing-input';capture.hidden=true;document.getElementById('chart').append(capture);
    const down=event=>{
        if(event.button!==0 || !state?.ready || state.error)return;
        const p=local(event);if(p.y<0 || p.y>height)return;
        if(select.value!=='pointer'){
            event.preventDefault();event.stopPropagation();
            const a=anchor(p.x,p.y);if(!a){feedback('No candle coordinates available yet. Wait for the chart to load.');return;}draft.push(a);
            if(draft.length===TOOLS[select.value]){remember();drawings.push({type:select.value,anchors:draft,style:{color:'#58b9ff',width:2,pattern:'solid',fillOpacity:.1},locked:false,timeframes:[window.DataCache.timeframe]});selected=drawings.length-1;store();mode();}
            schedule();return;
        }
        const target=event.target.closest('[data-drawing]');if(!target)return;
        event.preventDefault();event.stopPropagation();selected=Number(target.dataset.drawing);popup.close();
        if(drawings[selected].locked){edit();schedule();return;}
        drag={start:p,before:JSON.stringify(drawings),points:drawings[selected].anchors.map(point),handle:event.target.hasAttribute('data-anchor')?Number(event.target.dataset.anchor):null};
        svg.setPointerCapture(event.pointerId);schedule();
    };
    svg.addEventListener('pointerdown',down);capture.addEventListener('pointerdown',down);
    svg.addEventListener('pointermove',event=>{
        if(!drag)return;
        const p=local(event),updated=drawings[selected].anchors.map((a,i)=>{
            if(drag.handle!==null && i!==drag.handle)return a;
            const original=drag.points[i];return anchor(original.x+p.x-drag.start.x,original.y+p.y-drag.start.y)||a;
        });drawings[selected].anchors=updated;schedule();
    });
    function finish(){if(!drag)return;const changed=drag.before!==JSON.stringify(drawings);if(changed){undo.push(drag.before);if(undo.length>50)undo.shift();}drag=null;if(changed)void store();else edit();schedule();}
    svg.addEventListener('pointerup',finish);svg.addEventListener('pointercancel',()=>{if(drag){drawings=JSON.parse(drag.before);drag=null;schedule();}});
    document.addEventListener('keydown',event=>{
        if(event.key==='Escape' && !document.querySelector('dialog[open]')){if(drag){drawings=JSON.parse(drag.before);drag=null;}mode();}
        if((event.key==='Delete'||event.key==='Backspace') && selected>=0 && state?.ready && !state.error && !document.querySelector('dialog[open]') && !/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)){
            event.preventDefault();remember();drawings.splice(selected,1);selected=-1;store();schedule();
        }
    });
    chart.timeScale().subscribeVisibleLogicalRangeChange(schedule);chart.subscribeCrosshairMove(schedule);
    observer=new ResizeObserver(schedule);observer.observe(document.getElementById('chart'));
    window.addEventListener('pointermove',schedule,{passive:true});window.addEventListener('wheel',schedule,{passive:true});
    window.addEventListener('chart-settings-change',()=>requestAnimationFrame(schedule));
    window.DataCache.subscribe(()=>{market();schedule();});
    const timer=setInterval(()=>{if(state?.ready&&!state.saving&&!state.error&&!drag&&!draft.length&&!popup.open)void load(state,true);},10000);window.addEventListener('pagehide',()=>clearInterval(timer),{once:true});mode();
}
