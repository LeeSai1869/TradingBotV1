import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { logicalShift } from '../Section_11_UI_UX/web_root/window_state.js';

function cache(fetcher, styles={}) {
    const context = vm.createContext({window:{}, URLSearchParams, AbortController, setTimeout, clearTimeout,
        fetch: fetcher || (() => { throw Error('unexpected network request'); })});
    vm.runInContext(fs.readFileSync(new URL('../Section_11_UI_UX/web_root/data_cache.js',import.meta.url),'utf8'),context);
    context.window.Composer={config:{featureStyles:styles}};
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
    candles.mount({addSeries:()=>({attachPrimitive(){}})});
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

const provisional = (time, close=12) => bar(time,{
    provisional:true, client:{open_time:time*1000,close_time:time*1000+59999,open:10,high:13,low:9,close,volume:5},
    features:null,adcn:null,
});
const closed = time => bar(time,{client:{open_time:time*1000,close_time:time*1000+59999,open:10,high:12,low:9,close:11}});

test('forming price shares the bar shape but never enters permanent cached rows',async()=>{
    const c=cache();c.bars=[closed(60)];c._latestSignature=JSON.stringify(c.bars);
    c._fetchPage=async()=>({bars:[closed(60)],live:{bar:provisional(120),status:'live'}});
    let op;c.subscribe((_,event)=>op=event);
    assert.equal(await c.refreshStored(),true);
    assert.equal(c.bars.length,1);assert.equal(c.renderBars.length,2);
    assert.equal(c.renderBars.at(-1).features,null);assert.equal(op,'live');
});

test('rollover waits for audited closure and replaces provisional bar exactly once',async()=>{
    const c=cache();c.bars=[closed(60)];c._latestSignature=JSON.stringify(c.bars);
    c._applyLive({bar:provisional(120),status:'live'});
    c._fetchPage=async()=>({bars:[closed(60)],live:{bar:provisional(180),status:'live'}});
    await c.refreshStored();
    assert.equal(c.formingBar.time,120);assert.equal(c.liveStatus,'waiting for stored bar');
    c._fetchPage=async()=>({bars:[closed(60),closed(120)],live:{bar:provisional(180),status:'live'}});
    await c.refreshStored();
    assert.deepEqual(Array.from(c.renderBars,b=>b.time),[60,120,180]);
    assert.equal(c.renderBars[1].provisional,undefined);
    assert.equal(c.formingBar.time,180);
});

test('stale forming response cannot follow a new symbol selection',async()=>{
    const c=cache();c.bars=[closed(60)];const pending=deferred();
    c._fetchPage=()=>pending.promise;
    const work=c.refreshStored();
    c._fetchPage=async()=>({bars:[closed(300)],next_before:null});
    await c.loadInitial('NEW','1m');
    pending.resolve({bars:[closed(60)],live:{bar:provisional(120),status:'live'}});
    assert.equal(await work,false);assert.equal(c.formingBar,null);
});

test('deletion in another session invalidates cached candles on refresh',async()=>{
    const c=cache();
    c._fetchPage=async()=>({...page([60,120]),storage_epoch:'0:0'});
    await c.loadInitial('BTCUSDT','1m');
    c._fetchPage=async()=>({...page([]),storage_epoch:'0:1'});
    await c.refreshStored();
    assert.equal(c.bars.length,0);
    assert.equal(c.latestBar,null);
    assert.equal(c._storageEpoch,'0:1');
});

test('deletion observed by an older request reloads instead of merging old cached data',async()=>{
    const c=cache();
    c._fetchPage=async()=>({...page([60,120],60000),storage_epoch:'0:0'});
    await c.loadInitial('BTCUSDT','1m');
    c._fetchPage=async()=>({...page([]),storage_epoch:'1:0'});
    await c.prefetchOlder();
    assert.equal(c.bars.length,0);
    assert.equal(c.nextBefore,null);
});


test('a busy stored-bar response is retried without losing the initial chart load',async()=>{
    let calls=0;
    const c=cache(async()=>{
        calls++;
        return calls===1?{status:503,ok:false,json:async()=>({error:'Market data is busy'})}
            :{status:200,ok:true,json:async()=>page([60,120])};
    });
    await c.loadInitial('BTCUSDT','1m');
    assert.equal(calls,2);assert.equal(c.bars.length,2);assert.equal(c.loading,false);assert.equal(c.error,null);
});


test('ordinary refresh polls two bars and periodically reconciles replayed window',async()=>{
    const c=cache();const calls=[];
    c._fetchPage=(symbol,tf,limit)=>{calls.push(limit);return Promise.resolve(page([100,101]));};
    await c.loadInitial('BTCUSDT','1m');
    for(let i=0;i<12;i++)await c.refreshStored();
    assert.equal(calls[0],1000);
    assert.deepEqual(calls.slice(1,12),Array(11).fill(2));
    assert.equal(calls[12],1000);
    assert.equal(c.bars.length,2);
});


test('finishing historical catch-up reloads the cached window to remove old gaps',async()=>{
    const c=cache();let calls=0;
    c._fetchPage=()=>Promise.resolve(++calls===1?{...page([1,2]),history_pending:true}:
        calls===2?{...page([10,11]),history_pending:false}:{...page([3,4,5,6,7,8,9,10,11]),history_pending:false});
    await c.loadInitial('BTCUSDT','1m');
    assert.equal(c.historyPending,true);
    await c.refreshStored();
    assert.equal(calls,3);assert.equal(c.historyPending,false);
    assert.deepEqual(Array.from(c.bars,b=>b.time),[3,4,5,6,7,8,9,10,11]);
});

test('feature checkpoint progress redraws status even when candle data is unchanged',async()=>{
    const c=cache();let through=0;
    c._fetchPage=async()=>({...page([60]),feature_progress:{through,status:'historical feature replay'}});
    await c.loadInitial('ENAUSDT','1m');const events=[];c.subscribe((_,op)=>events.push(op));
    through=60000;
    assert.equal(await c.refreshStored(),true);
    assert.equal(c.featureProgress.through,60000);assert.deepEqual(events,['stored-refresh']);
    assert.equal(c.bars.length,1);assert.equal(await c.refreshStored(),false);
});


test('OB-only display fetches its checkpoint in the shared bars request',async()=>{
    const calls=[];
    const c=cache(async url=>{calls.push(url);return {ok:true,status:200,json:async()=>({bars:[]})};}, {normal_bull_ob_zones:{visible:true}});
    await c._fetchPage('ETHUSDT','4h',1000);
    assert.equal(calls.length,1);assert.equal(new URL(calls[0],'http://local').searchParams.get('sr_zones'),'1');
    await c._fetchPage('ETHUSDT','4h',1000,123);
    assert.equal(new URL(calls[1],'http://local').searchParams.has('sr_zones'),false);
});

test('liquidity uses the combined poll and never attaches history to old-page requests',async()=>{
    const calls=[];
    const c=cache(async url=>{calls.push(url);return {ok:true,status:200,json:async()=>({bars:[]})};},{liquidity_bids:{visible:true}});
    await c._fetchPage('BTCUSDT','1m',1000);
    assert.equal(new URL(calls[0],'http://local').searchParams.get('liquidity'),'1');
    await c._fetchPage('BTCUSDT','1m',1000,123);
    assert.equal(new URL(calls[1],'http://local').searchParams.has('liquidity'),false);
});

test('institutional higher projection requests every higher source only when selected',async()=>{
    const calls=[],styles={inst_support_zones:{visible:true,higher:true}};
    const data=cache(async url=>{calls.push(url);return {ok:true,json:async()=>({bars:[]})};},styles);
    await data._fetchPage('BTCUSDT','1h',1000);
    const query=new URL(calls[0],'http://local').searchParams;
    assert.equal(query.get('sr_frames'),'2h,4h,6h,8h,12h,1d,3d,1w,1M');
    styles.inst_support_zones.higher=false;
    await data._fetchPage('BTCUSDT','1h',1000);
    assert.equal(new URL(calls[1],'http://local').searchParams.has('sr_frames'),false);
});

test('two-candle polls send the known decision reference only for the same pair',async()=>{
    const calls=[],data=cache(async url=>{calls.push(url);return {ok:true,json:async()=>({bars:[]})};});
    data.symbol='ENAUSDT';data.timeframe='4h';data.bars=[{open_time:1000,signal_context:{open_time:500}}];
    await data._fetchPage('ENAUSDT','4h',2);
    assert.equal(new URL(calls[0],'http://local').searchParams.get('analysis_reference'),'500');
    await data._fetchPage('BTCUSDT','4h',2);
    assert.equal(new URL(calls[1],'http://local').searchParams.has('analysis_reference'),false);
});
