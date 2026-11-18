// Superseded timeframe requests must abort without corrupting the current cache.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const calls=[];
const context={window:{},URLSearchParams,AbortController,setTimeout,clearTimeout,
    fetch:(url,{signal})=>new Promise((resolve,reject)=>{
        calls.push({url,signal,resolve,reject});
        signal.addEventListener('abort',()=>reject(Object.assign(new Error('aborted'),{name:'AbortError'})));
    })};
vm.runInNewContext(fs.readFileSync('Section_11_UI_UX/web_root/data_cache.js','utf8'),context);
const cache=context.window.DataCache;cache.liveEnabled=false;
function finish(call,stamp){call.resolve({ok:true,status:200,json:async()=>({bars:[{time:stamp/1000,open_time:stamp,client:{close_time:stamp+59999}}],next_before:null})});}
(async()=>{
    const old=cache.loadInitial('BTCUSDT','1m');
    const fresh=cache.loadInitial('BTCUSDT','1h');
    assert(calls[0].signal.aborted);
    finish(calls[1],3600000);
    assert.equal(await old,false);assert.equal(await fresh,true);
    assert.equal(cache.timeframe,'1h');assert.equal(cache.latestBar.open_time,3600000);
    const refresh=cache.refreshStored();
    const next=cache.loadInitial('BTCUSDT','15m');
    assert(calls[2].signal.aborted);
    finish(calls[3],7200000);
    assert.equal(await refresh,false);assert.equal(await next,true);
    assert.equal(cache.timeframe,'15m');assert.equal(cache._requests.size,0);
    const active=cache.loadInitial('BTCUSDT','5m');
    calls[4].reject(Object.assign(new Error('timeout'),{name:'AbortError'}));
    await assert.rejects(active,/timed out/);
    assert.equal(cache._requests.size,0);
    console.log('PASS: obsolete initial/refresh requests abort, current timeframe wins, active timeouts still report errors');
})().catch(e=>{console.error(e);process.exitCode=1;});
