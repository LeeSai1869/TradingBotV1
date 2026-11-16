// Unit-level DOM/chart doubles; no browser, service or market-data writes.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {TOOLS,fibLevels,normalizeDrawings} from '../Section_11_UI_UX/controls/drawings/geometry.js';

class Element {
    constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attributes={};this.dataset={};this.style={};this.listeners={};this.hidden=false;this.open=false;this.captures=new Set();}
    append(...nodes){for(const node of nodes){if(typeof node==='string')continue;node.remove();node.parent=this;this.children.push(node);}}
    remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);this.parent=null;}
    after(node){const parent=this.parent;node.remove();node.parent=parent;parent.children.splice(parent.children.indexOf(this)+1,0,node);}
    replaceChildren(...nodes){for(const child of this.children)child.parent=null;this.children=[];this.append(...nodes);}
    setAttribute(key,value){this.attributes[key]=String(value);if(key==='id')this.id=String(value);if(key.startsWith('data-'))this.dataset[key.slice(5)]=String(value);}
    getAttribute(key){return this.attributes[key]??null;}
    hasAttribute(key){return key in this.attributes;}
    contains(node){return this===node||this.children.some(child=>child.contains(node));}
    closest(selector){if(selector==='[data-drawing]'&&this.hasAttribute('data-drawing'))return this;return this.parent?.closest(selector)||null;}
    all(){return [this,...this.children.flatMap(child=>child.all())];}
    querySelector(selector){
        if(selector==='button:not(:disabled)')return this.all().find(n=>n.tagName==='BUTTON'&&!n.disabled);
        return this.all().find(n=>n.tagName==='DIALOG'&&n.open&&(!selector.includes(':not')||n.className!=='drawing-popup'))||null;
    }
    addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
    dispatch(type,event){for(const fn of this.listeners[type]||[])fn(event);}
    getBoundingClientRect(){return {left:0,top:0,bottom:34};}
    setPointerCapture(id){this.captures.add(id);}
    hasPointerCapture(id){return this.captures.has(id);}
    releasePointerCapture(id){this.captures.delete(id);this.dispatch('lostpointercapture',{});}
    show(){this.open=true;}
    close(){this.open=false;}
    focus(){}
}

async function fixture(){
    const document=new Element('document');document.body=new Element('body');document.append(document.body);
    document.createElement=tag=>new Element(tag);document.createElementNS=(_,tag)=>new Element(tag);
    document.getElementById=id=>document.all().find(n=>n.id===id);
    const add=(tag,id,parent=document.body)=>{const n=new Element(tag);n.id=id;parent.append(n);return n;};
    const toolbar=add('div','toolbar'),chartElement=add('div','chart');
    add('button','workspace-button',toolbar);add('button','hud-button',toolbar);add('button','alerts-button',toolbar);
    const data={symbol:'BTCUSDT',timeframe:'1h',renderBars:Array.from({length:100},(_,i)=>({time:1000+i*3600,open_time:(1000+i*3600)*1000,client:{close_time:(1000+(i+1)*3600)*1000-1}})),subscribe(fn){this.subscriber=fn;}};
    const original={handleScroll:{pressedMouseMove:true,mouseWheel:false},handleScale:{pinch:false,mouseWheel:true}};
    let options=structuredClone(original),revision=1,failNext=false;
    let saved=[{type:'line',anchors:[{time:37000,offset:0,price:800},{time:73000,offset:0,price:700}],style:{color:'#58b9ff',width:2,pattern:'dashed',fillOpacity:.1},locked:false,timeframes:['1h']}];
    const requests=[],raf=[],series={coordinateToPrice:y=>1000-y,priceToCoordinate:p=>1000-p,priceFormatter:()=>({format:String})};
    const chart={options:()=>options,applyOptions:value=>{options={...options,...structuredClone(value)};},timeScale:()=>({coordinateToLogical:x=>x/10,timeToCoordinate:t=>(t-1000)/3600*10,options:()=>({barSpacing:10}),width:()=>1000,subscribeVisibleLogicalRangeChange(){}}),panes:()=>[{getHTMLElement:()=>chartElement,getHeight:()=>700}],subscribeCrosshairMove(){}};
    const window={DataCache:data,AppSession:{username:'admin'},innerWidth:1400,innerHeight:900,addEventListener(){}};
    const context=vm.createContext({window,document,TOOLS,fibLevels,normalizeDrawings,getSeries:()=>series,structuredClone,AbortController,console,localStorage:{},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,requestAnimationFrame:fn=>{raf.push(fn);return raf.length;},ResizeObserver:class{observe(){}unobserve(){}},fetch:async(url,init)=>{
        if(init?.method==='POST'){
            if(failNext){failNext=false;return {ok:false,status:503,json:async()=>({error:'Temporary drawing storage failure'})};}
            const packet=JSON.parse(init.body);assert.equal(packet.revision,revision);saved=packet.drawings;revision++;requests.push(packet);
        }
        return {ok:true,status:200,json:async()=>({revision,drawings:structuredClone(saved)})};
    }});
    const source=fs.readFileSync(new URL('../Section_11_UI_UX/controls/drawings/index.js',import.meta.url),'utf8').replace(/^import .*;\n/gm,'').replace(/export /g,'');
    vm.runInContext(source,context);context.mount(chart);
    function flush(){let count=0;while(raf.length){assert.ok(count++<30,'animation frame loop');raf.shift()();}}
    async function settle(){for(let turn=0;turn<3;turn++){for(let i=0;i<12;i++)await Promise.resolve();flush();}}
    await settle();
    const svg=document.getElementById('drawing-overlay'),popup=document.all().find(n=>n.className==='drawing-popup'),menu=document.getElementById('drawing-tools-menu');
    const button=label=>document.all().find(n=>n.tagName==='BUTTON'&&(n.getAttribute('aria-label')===label||n.textContent===label));
    function pointer(type,target,x,y){const event={button:0,pointerId:7,target,clientX:x,clientY:y,preventDefault(){},stopPropagation(){}};if(type==='pointerdown')document.dispatch(type,event);svg.dispatch(type,event);flush();}
    function key(value,extra={}){const event={key:value,target:document.body,preventDefault(){this.prevented=true;},...extra};document.dispatch('keydown',event);flush();return event;}
    function group(index=0){return svg.children.find(n=>n.dataset.drawing===String(index));}
    return {document,toolbar,chartElement,svg,popup,menu,button,pointer,key,group,settle,flush,data,original,options:()=>options,saved:()=>saved,requests,failSave:()=>failNext=true};
}

test('one toolbar button contains all tools including both Fibonacci tools and dismisses outside',async()=>{
    const f=await fixture();
    assert.equal(f.menu.hidden,true);
    assert.equal(f.menu.parent,f.document.body);
    assert.deepEqual(f.toolbar.children.map(n=>n.id),['workspace-button','hud-button','drawings-button','alerts-button']);
    f.button('Drawings').onclick();assert.equal(f.menu.hidden,false);
    assert.equal(f.button('Fib retracement').parent,f.menu);assert.equal(f.button('Fib extension').parent,f.menu);
    f.button('Fib retracement').onclick();assert.equal(f.menu.hidden,true);
    assert.equal(f.document.getElementById('drawing-input').hidden,false);
    f.key('Escape');assert.deepEqual(f.options(),f.original);
    f.button('Drawings').onclick();f.document.dispatch('pointerdown',{target:f.chartElement});assert.equal(f.menu.hidden,true);
});

test('click jitter opens style editor, clicks inside keep it, and outside clicks dismiss it',async()=>{
    const f=await fixture(),hit=f.group().children.find(n=>n.getAttribute('class')==='drawing-hit');
    assert.equal(hit.getAttribute('stroke-dasharray'),'','dashed-line gaps must remain selectable');
    f.pointer('pointerdown',hit,150,250);f.pointer('pointermove',f.svg,151,251);f.pointer('pointerup',f.svg,151,251);
    assert.equal(f.popup.open,true);assert.equal(f.requests.length,0);
    const color=f.document.all().find(n=>n.getAttribute('aria-label')==='Drawing color');
    f.document.dispatch('pointerdown',{target:color});assert.equal(f.popup.open,true);
    color.value='#ff1234';f.button('Apply drawing').onclick();await f.settle();assert.equal(f.saved()[0].style.color,'#ff1234');
    f.pointer('pointerdown',f.group().children[1],150,250);f.pointer('pointerup',f.svg,150,250);
    assert.equal(f.popup.open,true);f.document.dispatch('pointerdown',{target:f.chartElement});assert.equal(f.popup.open,false);
});

test('whole-drawing drag, anchor edit and cancellation preserve geometry and chart navigation',async()=>{
    const f=await fixture();
    f.pointer('pointerdown',f.group().children[1],150,250);
    assert.equal(f.options().handleScroll,false);
    f.pointer('pointermove',f.svg,180,270);f.pointer('pointerup',f.svg,180,270);await f.settle();
    assert.deepEqual(f.saved()[0].anchors,[{time:47800,offset:0,price:780},{time:83800,offset:0,price:680}]);
    assert.equal(f.popup.open,false);assert.equal(f.svg.hasPointerCapture(7),false);assert.deepEqual(f.options(),f.original);
    const handle=f.group().children.find(n=>n.hasAttribute('data-anchor'));
    f.pointer('pointerdown',handle,130,220);f.pointer('pointermove',f.svg,140,240);f.pointer('pointerup',f.svg,140,240);await f.settle();
    assert.deepEqual(f.saved()[0].anchors,[{time:51400,offset:0,price:760},{time:83800,offset:0,price:680}]);
    f.pointer('pointerdown',f.group().children[1],170,280);f.pointer('pointermove',f.svg,200,310);f.svg.dispatch('pointercancel',{});f.flush();
    assert.deepEqual(f.options(),f.original);assert.equal(f.svg.hasPointerCapture(7),false);
    assert.equal(f.requests.length,2,'cancelled drag must not save');
});

test('duplicate and copy/paste save independent drawings with their styles and timeframe scope',async()=>{
    const f=await fixture();
    f.pointer('pointerdown',f.group().children[1],150,250);f.pointer('pointerup',f.svg,150,250);
    f.button('Duplicate drawing').onclick();await f.settle();
    assert.equal(f.saved().length,2);assert.notDeepEqual(f.saved()[0].anchors,f.saved()[1].anchors);
    assert.deepEqual(f.saved()[0].style,f.saved()[1].style);assert.deepEqual(f.saved()[1].timeframes,['1h']);
    assert.equal(f.key('c',{metaKey:true}).prevented,true);assert.equal(f.key('v',{metaKey:true}).prevented,true);await f.settle();
    assert.equal(f.saved().length,3);assert.notDeepEqual(f.saved()[1].anchors,f.saved()[2].anchors);
    assert.equal(f.key('c',{ctrlKey:true,target:new Element('input')}).prevented,undefined);
});

test('rectangle interiors and Fibonacci legs can be selected and dragged',async()=>{
    const f=await fixture(),capture=f.document.getElementById('drawing-input');
    for(const [label,points] of [['Rectangle zone',[[300,100],[400,200]]],['Fib extension',[[500,100],[600,200],[700,150]]]]){
        f.button('Drawings').onclick();f.button(label).onclick();
        for(const [x,y] of points)f.pointer('pointerdown',capture,x,y);
        await f.settle();
    }
    assert.equal(f.saved().length,3);
    const rectangle=f.group(1).children[0];assert.equal(rectangle.getAttribute('pointer-events'),'all');
    f.pointer('pointerdown',rectangle,350,150);f.pointer('pointermove',f.svg,360,160);f.pointer('pointerup',f.svg,360,160);await f.settle();
    assert.equal(f.saved()[1].anchors[0].price,890);
    const leg=f.group(2).children[1];assert.equal(leg.getAttribute('class'),'drawing-hit');
    f.pointer('pointerdown',leg,550,150);f.pointer('pointermove',f.svg,560,160);f.pointer('pointerup',f.svg,560,160);await f.settle();
    assert.equal(f.saved()[2].anchors[0].price,890);
});

test('locked drawings remain editable; switching timeframes cancels an active drag',async()=>{
    const f=await fixture();
    const click=()=>{f.pointer('pointerdown',f.group().children[1],150,250);f.pointer('pointerup',f.svg,150,250);};
    click();let lock=f.document.all().find(n=>n.getAttribute('aria-label')==='Lock position');lock.checked=true;f.button('Apply drawing').onclick();await f.settle();
    click();assert.equal(f.popup.open,true);assert.equal(f.group().children.some(n=>n.tagName==='CIRCLE'),false);
    lock=f.document.all().find(n=>n.getAttribute('aria-label')==='Lock position');lock.checked=false;f.button('Apply drawing').onclick();await f.settle();
    f.pointer('pointerdown',f.group().children[1],150,250);f.pointer('pointermove',f.svg,180,270);
    f.data.timeframe='5m';f.data.subscriber();f.flush();
    assert.deepEqual(f.options(),f.original);assert.equal(f.svg.hasPointerCapture(7),false);assert.equal(f.requests.length,2);
    assert.equal(f.svg.children.length,0,'1h drawing must retain its saved timeframe scope');
});

test('failed drawing saves remain recoverable from inside the compact menu',async()=>{
    const f=await fixture();f.failSave();
    f.pointer('pointerdown',f.group().children[1],150,250);f.pointer('pointermove',f.svg,180,270);f.pointer('pointerup',f.svg,180,270);await f.settle();
    assert.equal(f.requests.length,0);assert.deepEqual(f.options(),f.original);
    f.button('Drawings').onclick();const retry=f.button('Retry saving drawings');assert.equal(retry.parent,f.menu);
    retry.onclick();await f.settle();assert.equal(f.requests.length,1);assert.equal(f.saved()[0].anchors[0].price,780);
    assert.equal(f.button('Trend line').disabled,false);assert.equal(f.menu.hidden,true);
});
