const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const context={window:{},URLSearchParams,setTimeout,clearTimeout,AbortController};
vm.runInNewContext(fs.readFileSync('Section_11_UI_UX/web_root/data_cache.js','utf8'),context);
const c=context.window.DataCache;
const stored={open_time:0,client:{close_time:299999}};
const forming={symbol:'BTCUSDT',interval:'5m',time:300,open_time:300000,client:{symbol:'BTCUSDT',interval:'5m',open_time:300000,close_time:599999,open:100,high:102,low:99,close:101,volume:1}};
Object.assign(c,{symbol:'BTCUSDT',timeframe:'5m',bars:[stored],latestBar:stored});
let events=[];c.subscribe((cache,event)=>events.push(event));
(async()=>{
    // An identical two-row edge must not repaint the full initial history.
    c.liveEnabled=false;
    c._latestSignature='initial full-history signature';
    c._fetchPage=async()=>({bars:[stored],feature_progress:null});
    await c.refreshStored();assert.deepEqual(events,[]);
    // Progress-only polls must not replace identical rows or source snapshots.
    const snapshot={through:0,zones:{}};c.srSnapshot=snapshot;c.srFrames={};
    c._fetchPage=async()=>({bars:[JSON.parse(JSON.stringify(stored))],sr_snapshot:JSON.parse(JSON.stringify(snapshot)),
        sr_frames:{},feature_progress:{status:'features current'}});
    await c.refreshStored();assert.equal(c.bars[0],stored);assert.equal(c.srSnapshot,snapshot);
    events=[];
    c.liveEnabled=true;
    c._fetchPage=()=>new Promise(()=>{});
    c.refreshStored(); // Deliberately stuck full chart request.
    let calls=0;
    context.fetch=async()=>{calls++;return {ok:true,json:async()=>({symbol:'BTCUSDT',interval:'5m',live:{status:'live',bar:forming}})};};
    const first=c.refreshLive();assert.equal(c.refreshLive(),first,'one live request at a time');
    await first;
    assert.equal(c.formingBar.client.close,101);
    assert.deepEqual(events,['live','quote']);assert.equal(calls,1);
    // A missing closed candle must still block a forward jump.
    context.fetch=async()=>({ok:true,json:async()=>({symbol:'BTCUSDT',interval:'5m',live:{status:'live',bar:{...forming,time:900,open_time:900000,client:{...forming.client,open_time:900000,close_time:1199999}}}})});
    await c.refreshLive();assert.equal(c.formingBar.open_time,300000);
    assert.equal(c.liveStatus,'waiting for stored bar');
    // Loading or browsing old candles must not hide the independent current quote.
    c.loading=true;c.atLiveEdge=false;
    context.fetch=async()=>({ok:true,json:async()=>({symbol:'BTCUSDT',interval:'5m',live:{status:'live',bar:{...forming,client:{...forming.client,close:105}}}})});
    const count=c.bars.length;await c.refreshLive();
    assert.equal(c.liveQuote.client.close,105);assert.equal(c.bars.length,count);
    c.loading=false;c.atLiveEdge=true;
    let release;
    context.fetch=()=>new Promise(resolve=>release=resolve);
    const old=c.refreshLive();++c._reloadGeneration;c.formingBar=null;
    release({ok:true,json:async()=>({symbol:'BTCUSDT',interval:'5m',live:{status:'live',bar:forming}})});await old;
    assert.equal(c.formingBar,null,'late live response cannot enter another timeframe');
    c.liveEnabled=false;await c.refreshLive();
    console.log('PASS: live price continues during blocked stored reads; deduplication, gaps and dataset isolation preserved');
})().catch(error=>{console.error(error);process.exitCode=1;});
