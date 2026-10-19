import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { logicalShift } from '../Section_11_UI_UX/web_root/window_state.js';

function cache() {
    const context = vm.createContext({window:{}, URLSearchParams,
        fetch: () => { throw Error('unexpected network request'); }});
    vm.runInContext(fs.readFileSync(new URL('../Section_11_UI_UX/web_root/data_cache.js',import.meta.url),'utf8'),context);
    return context.window.DataCache;
}
const deferred = () => {let resolve; const promise=new Promise(r=>resolve=r); return {promise,resolve};};
const bar = (time, extra={}) => ({open_time:time*1000,time,symbol:'BTCUSDT',interval:'1m',
    client:{open:10,high:12,low:9,close:11},features:{ema50:10},adcn:null,...extra});
const page = (times, next=null) => ({bars:times.map(t=>bar(t)),next_before:next});

test('late initial response cannot overwrite a newer market', async()=>{
    const c=cache(); const pending=deferred();
    c._fetchPage=s=>s==='OLD'?pending.promise:Promise.resolve(page([200]));
    const old=c.loadInitial('OLD','1m');
    await c.loadInitial('NEW','5m');
    pending.resolve(page([100]));
    assert.equal(await old,false);
    assert.equal(c.symbol,'NEW'); assert.equal(c.bars[0].time,200);
});

test('one initial request carries candles, features and decisions together',async()=>{
    const c=cache(); const calls=[];
    c._fetchPage=async(...args)=>{calls.push(args);return {bars:[bar(60,{adcn:{signal_type:'BUY'}})],next_before:null};};
    await c.loadInitial('BTCUSDT','1m');
    assert.equal(calls.length,1); assert.equal(calls[0][2],1000);
    assert.equal(c.bars[0].features.ema50,10);
    assert.equal(c.bars[0].adcn.signal_type,'BUY');
    assert.equal(c.latestBar,c.bars[0]);
});

test('duplicate prefetch requests share one in-flight operation',async()=>{
    const c=cache(); const pending=deferred(); let calls=0;
    c.bars=[bar(120)];c.nextBefore=120000;
    c._fetchPage=()=>{calls++;return pending.promise;};
    const a=c.prefetchOlder(),b=c.prefetchOlder();
    assert.equal(a,b); assert.equal(calls,1);
    pending.resolve(page([60]));await a;
    assert.deepEqual(Array.from(c.bars,b=>b.time),[60,120]);
});

test('prefetch arrival notifies the coordinator without another user gesture',async()=>{
    const c=cache();c.bars=[bar(120)];c.nextBefore=120000;
    c._fetchPage=async()=>page([60]);
    let event; c.subscribe((_,op)=>event=op);
    await c.prefetchOlder();assert.equal(event,'history');
});

test('stale prefetch cannot contaminate a newly selected market',async()=>{
    const c=cache(); const pending=deferred();
    c.bars=[bar(120)];c.nextBefore=120000;
    c._fetchPage=()=>pending.promise;
    const old=c.prefetchOlder();
    c._fetchPage=async()=>page([500]);
    await c.loadInitial('NEW','1m');
    pending.resolve(page([60]));assert.equal(await old,false);
    assert.deepEqual(Array.from(c.bars,b=>b.time),[500]);
});

test('history exhaustion does not issue any more requests',async()=>{
    const c=cache();assert.equal(await c.prefetchOlder(),false);
});

test('prefetch failure preserves the cursor and can be retried',async()=>{
    const c=cache();c.bars=[bar(120)];c.nextBefore=120000;
    c._fetchPage=async()=>{throw Error('offline');};
    assert.equal(await c.prefetchOlder(),false);assert.equal(c.nextBefore,120000);
    c._fetchPage=async()=>page([60]);assert.equal(await c.prefetchOlder(),true);
    assert.equal(c.error,null);
});

test('pan into history while a stored refresh is pending preserves the view',async()=>{
    const c=cache();const pending=deferred();c.bars=[bar(60)];
    c._fetchPage=()=>pending.promise;
    const work=c.refreshStored();c.atLiveEdge=false;
    pending.resolve(page([120]));assert.equal(await work,false);
    assert.equal(c.bars[0].time,60);
});

test('stored refresh updates the unified record without dropping visited history',async()=>{
    const c=cache();c.bars=[bar(30),bar(60)];
    c._fetchPage=async()=>({bars:[bar(60,{features:{ema50:42}}),bar(120)],next_before:30000});
    assert.equal(await c.refreshStored(),true);
    assert.deepEqual(Array.from(c.bars,b=>b.time),[30,60,120]);
    assert.equal(c.bars[1].features.ema50,42);
    assert.equal(c.latestBar.time,120);
    let emitted=false;c.subscribe(()=>emitted=true);
    assert.equal(await c.refreshStored(),false);assert.equal(emitted,false);
});

test('active window is 1000 without evicting visible or visited history',()=>{
    const c=cache();c.bars=Array.from({length:15000},(_,i)=>bar(i));
    c.setVisibleWindow({from:300,to:1299});
    assert.equal(c.activeBars.length,1000);assert.equal(c.bars.length,15000);
    assert.equal(c.atLiveEdge,false);
});

test('prepend and gaps preserve the position of a shared candle',()=>{
    const old=[30,40,50,60].map(time=>({time}));
    assert.equal(logicalShift(old,[20,30,40,50,60].map(time=>({time}))),1);
    assert.equal(logicalShift(old,[50,60,80].map(time=>({time}))),-2);
});

test('markers update one wrapper in place over repeated redraws',async()=>{
    let created=0,updates=0,detached=0;
    globalThis.LightweightCharts={CandlestickSeries:{},createSeriesMarkers:()=>{
        created++;return {setMarkers:()=>updates++,detach:()=>detached++};
    }};
    const candles=await import('../Section_11_UI_UX/overlays/candles/index.js');
    const markers=await import('../Section_11_UI_UX/overlays/markers/index.js');
    candles.mount({addSeries:()=>({})});
    for(let i=0;i<100;i++) markers.update(null,{bars:[bar(60,{adcn:{signal_type:'BUY',final_score:70}})]});
    assert.equal(created,1);assert.equal(updates,99);assert.equal(detached,0);
});

test('stored polling is serial and uses only the cache local-store refresh',async()=>{
    const pending=deferred();let scheduled;let calls=0;
    const context=vm.createContext({DataCache:{refreshStored:()=>{calls++;return pending.promise;}},
        console,setTimeout:fn=>{scheduled=fn;return 1;},clearTimeout(){}});
    const source=fs.readFileSync(new URL('../Section_11_UI_UX/web_root/stored_poll.js',import.meta.url),'utf8')
        .replace(/export function/g,'function');
    vm.runInContext(source+'\nglobalThis.controls={start,stop};',context);
    context.controls.start();assert.equal(calls,0);
    const first=scheduled;scheduled=undefined;first();
    assert.equal(calls,1);assert.equal(scheduled,undefined);
    pending.resolve(false);await new Promise(r=>setImmediate(r));
    assert.equal(typeof scheduled,'function');context.controls.stop();
});
