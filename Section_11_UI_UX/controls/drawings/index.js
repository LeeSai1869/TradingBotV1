import {getSeries} from '../../overlays/candles/index.js';
import {TOOLS,fibLevels,normalizeDrawings} from './geometry.js';
export const name='drawings';
const NS='http://www.w3.org/2000/svg';
let chart,svg,select,hint,drawings=[],draft=[],selected=-1,key='',drag=null,undo=[],frame=0;
let width=0,height=0,paneNode,observer;
function schedule(){if(!frame)frame=requestAnimationFrame(()=>{frame=0;render();});}
function node(tag,attrs,parent=svg,text){const n=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.textContent=text;parent.append(n);return n;}
function store(){try{localStorage.setItem(key,JSON.stringify(drawings));hint.textContent='Saved in this browser.';}catch{hint.textContent='Could not save drawings in this browser.';}}
function remember(){undo.push(JSON.stringify(drawings));if(undo.length>50)undo.shift();}
function mode(value='pointer'){
    select.value=value;draft=[];svg.dataset.active=String(value!=='pointer');
    chart.applyOptions({handleScroll:value==='pointer',handleScale:value==='pointer'});
    hint.textContent=value==='pointer'?'Select a drawing to move or delete it.':`Click ${TOOLS[value]} ${TOOLS[value]===1?'point':'points'} on the price chart. Escape cancels.`;schedule();
}
function market(){
    const cache=window.DataCache;if(!cache?.symbol)return;
    const next=`tradingbot.drawings.v1.${window.AppSession?.username||'user'}.${cache.symbol}.${cache.timeframe}`;
    if(next===key)return;
    key=next;try{drawings=normalizeDrawings(JSON.parse(localStorage.getItem(key)||'[]'));}catch{drawings=[];}
    selected=-1;drag=null;undo=[];mode();
}
function anchor(x,y){
    const bars=window.DataCache?.renderBars||[],logical=chart.timeScale().coordinateToLogical(x),price=getSeries()?.coordinateToPrice(y);
    if(!bars.length || logical==null || price==null || !Number.isFinite(price))return null;
    const index=Math.max(0,Math.min(bars.length-1,Math.round(logical)));
    return {time:bars[index].time,offset:logical-index,price};
}
function point(a){
    const x=chart.timeScale().timeToCoordinate(a.time),y=getSeries()?.priceToCoordinate(a.price);
    return x==null || y==null?null:{x:x+a.offset*chart.timeScale().options().barSpacing,y,price:a.price};
}
function stroke(a,b,parent,color='#58b9ff',hit=false){
    return node('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:hit?'transparent':color,'stroke-width':hit?12:1.5,
        class:hit?'drawing-hit':'','pointer-events':hit?'stroke':'none'},parent);
}
function render(){
    market();svg.replaceChildren();
    const pane=chart.panes()[0];if(!pane)return;
    if(pane.getHTMLElement()!==paneNode){if(paneNode)observer.unobserve(paneNode);paneNode=pane.getHTMLElement();if(paneNode)observer.observe(paneNode);}
    width=chart.timeScale().width();height=pane.getHeight();svg.style.width=width+'px';svg.style.height=height+'px';svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
    function paint(d,index){
        const points=d.anchors.map(point);if(points.some(p=>!p))return;
        const group=node('g',{'data-drawing':index,'data-type':d.type});
        const hit=select.value==='pointer' && index>=0;
        function segment(a,b,color){stroke(a,b,group,color);if(hit)stroke(a,b,group,color,true);}
        const [a,b]=points;
        if(d.type==='horizontal')segment({x:0,y:a.y},{x:width,y:a.y});
        else if(d.type==='line')segment(a,b);
        else if(d.type==='rectangle'){
            const corners=[a,{x:b.x,y:a.y},b,{x:a.x,y:b.y}];
            node('rect',{x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.abs(b.x-a.x),height:Math.abs(b.y-a.y),fill:'#58b9ff18','pointer-events':'none'},group);
            corners.forEach((p,i)=>segment(p,corners[(i+1)%4]));
        }else{
            for(let i=1;i<points.length;i++)stroke(points[i-1],points[i],group,'#718096');
            const left=Math.min(...points.map(p=>p.x)), right=Math.max(...points.map(p=>p.x))+(d.type==='extension'?120:0);
            for(const level of fibLevels(d.type,points)){
                const y=getSeries().priceToCoordinate(level.price);if(y==null)continue;
                const color=level.ratio===.618 || level.ratio===1.618?'#f5c542':'#58b9ff';
                segment({x:left,y},{x:right,y},color);
                node('text',{x:left+4,y:y-4,fill:color,'font-size':10,'pointer-events':'none'},group,`${(level.ratio*100).toFixed(2)}% · ${getSeries().priceFormatter().format(level.price)}`);
            }
        }
        if(hit && index===selected)points.forEach((p,i)=>node('circle',{cx:p.x,cy:p.y,r:5,fill:'#111',stroke:'#fff','stroke-width':1.5,class:'drawing-handle','data-anchor':i},group));
    }
    drawings.forEach(paint);
    if(draft.length){
        const required=TOOLS[select.value];
        if(draft.length===required)paint({type:select.value,anchors:draft},-1);
        else for(const a of draft){const p=point(a);if(p)node('circle',{cx:p.x,cy:p.y,r:4,fill:'#f5c542','pointer-events':'none'});}
    }
}
function local(event){const bounds=svg.getBoundingClientRect();return {x:event.clientX-bounds.left,y:event.clientY-bounds.top};}
export function mount(instance){
    chart=instance;
    const controls=document.createElement('div');controls.className='drawing-tools';controls.setAttribute('aria-label','Drawing tools');document.getElementById('toolbar').append(controls);
    select=document.createElement('select');select.setAttribute('aria-label','Drawing tool');
    for(const [value,label] of Object.entries({pointer:'Pointer',line:'Trend line',rectangle:'Rectangle zone',horizontal:'Horizontal line',retracement:'Fib retracement',extension:'Fib extension'})){
        const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option);
    }controls.append(select);select.onchange=()=>mode(select.value);
    function button(label,action){const b=document.createElement('button');b.textContent=label;b.onclick=action;controls.append(b);}
    button('Delete drawing',()=>{if(selected<0)return;remember();drawings.splice(selected,1);selected=-1;store();schedule();});
    button('Undo drawing',()=>{if(!undo.length)return;drawings=JSON.parse(undo.pop());selected=-1;store();schedule();});
    hint=document.createElement('span');hint.className='drawing-instructions';hint.setAttribute('role','status');controls.append(hint);
    svg=node('svg',{'id':'drawing-overlay','aria-label':'Chart drawings'},document.getElementById('chart'));
    svg.addEventListener('pointerdown',event=>{
        if(event.button!==0)return;
        const p=local(event);if(p.y<0 || p.y>height)return;
        if(select.value!=='pointer'){
            event.preventDefault();event.stopPropagation();
            const a=anchor(p.x,p.y);if(!a)return;draft.push(a);
            if(draft.length===TOOLS[select.value]){remember();drawings.push({type:select.value,anchors:draft});selected=drawings.length-1;store();mode();}
            schedule();return;
        }
        const target=event.target.closest('[data-drawing]');if(!target)return;
        event.preventDefault();event.stopPropagation();selected=Number(target.dataset.drawing);
        drag={start:p,before:JSON.stringify(drawings),points:drawings[selected].anchors.map(point),handle:event.target.hasAttribute('data-anchor')?Number(event.target.dataset.anchor):null};
        svg.setPointerCapture(event.pointerId);schedule();
    });
    svg.addEventListener('pointermove',event=>{
        if(!drag)return;
        const p=local(event),updated=drawings[selected].anchors.map((a,i)=>{
            if(drag.handle!==null && i!==drag.handle)return a;
            const original=drag.points[i];return anchor(original.x+p.x-drag.start.x,original.y+p.y-drag.start.y)||a;
        });drawings[selected].anchors=updated;schedule();
    });
    function finish(){if(!drag)return;undo.push(drag.before);if(undo.length>50)undo.shift();drag=null;store();schedule();}
    svg.addEventListener('pointerup',finish);svg.addEventListener('pointercancel',()=>{if(drag){drawings=JSON.parse(drag.before);drag=null;schedule();}});
    document.addEventListener('keydown',event=>{
        if(event.key==='Escape' && !document.querySelector('dialog[open]')){if(drag){drawings=JSON.parse(drag.before);drag=null;}mode();}
        if((event.key==='Delete'||event.key==='Backspace') && selected>=0 && !document.querySelector('dialog[open]') && !/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)){
            event.preventDefault();remember();drawings.splice(selected,1);selected=-1;store();schedule();
        }
    });
    chart.timeScale().subscribeVisibleLogicalRangeChange(schedule);chart.subscribeCrosshairMove(schedule);
    observer=new ResizeObserver(schedule);observer.observe(document.getElementById('chart'));
    window.addEventListener('pointermove',schedule,{passive:true});window.addEventListener('wheel',schedule,{passive:true});
    window.addEventListener('chart-settings-change',()=>requestAnimationFrame(schedule));
    window.DataCache.subscribe(()=>{market();schedule();});mode();
}
