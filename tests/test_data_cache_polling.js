// Run with node tests/test_data_cache_polling.js. No browser or market writes.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('Section_11_UI_UX/web_root/data_cache.js','utf8');

function fixture(){
    const context={window:{},URLSearchParams,setTimeout,clearTimeout,AbortController};
    vm.runInNewContext(source,context);
    const cache=context.window.DataCache;
    const bars=[{open_time:0,client:{close_time:3599999},features:{rsi:50}},{open_time:3600000,client:{close_time:7199999},features:{rsi:51}}];
    Object.assign(cache,{symbol:'BTCUSDT',timeframe:'1h',bars,latestBar:bars[1],featureProgress:{status:'features current'},liveEnabled:false});
    const calls=[];
    cache._fetchPage=async(s,t,limit)=>{calls.push(limit);return {bars,feature_progress:{status:'features current'}};};
    return {cache,calls,bars};
}

(async()=>{
    const {cache,calls,bars}=fixture();
    for(let i=0;i<24;i++)await cache.refreshStored();
    assert.equal(calls.length,24);
    assert.ok(calls.every(limit=>limit===2),'current live chart must not download full history every twelve polls');
    cache.featureProgress={status:'updating affected features',repair:{through:0}};
    cache._fetchPage=async(s,t,limit)=>{calls.push(limit);return {bars,feature_progress:{status:'updating affected features',repair:{through:0}}};};
    for(let i=0;i<12;i++)await cache.refreshStored();
    assert.equal(calls.at(-1),1000,'active feature replay still refreshes historical rows');
    cache._fetchPage=async(s,t,limit)=>{calls.push(limit);return {bars,feature_progress:{status:'features current'}};};
    await cache.refreshStored();
    assert.equal(calls.at(-1),2);
    await cache.refreshStored();
    assert.equal(calls.at(-1),1000,'replay completion must refresh the repaired historical window once');
    await cache.refreshStored();assert.equal(calls.at(-1),2);
    await cache.refreshStored({full:true});assert.equal(calls.at(-1),1000,'explicit settings refresh must remain available');
    const before=calls.length;cache.atLiveEdge=false;
    await cache.refreshStored({full:true});assert.equal(calls.length,before);
    cache.atLiveEdge=true;await cache.refreshStored();assert.equal(calls.at(-1),1000,'queued full refresh survives history browsing');
    cache._fetchPage=async()=>{throw new Error('network test');};
    await assert.rejects(cache.refreshStored({full:true}),/network test/);
    cache._fetchPage=async(s,t,limit)=>{calls.push(limit);return {bars,feature_progress:{status:'features current'}};};
    await cache.refreshStored();assert.equal(calls.at(-1),1000,'failed full refresh is retried without losing demand');
    console.log('PASS: current edge polling, active replay, replay completion, explicit settings, history navigation and retry behavior');
})().catch(error=>{console.error(error);process.exitCode=1;});
