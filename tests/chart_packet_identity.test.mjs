import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
function fixture(){
    const context={window:{},URLSearchParams,AbortController,setTimeout,clearTimeout};
    vm.runInNewContext(fs.readFileSync('Section_11_UI_UX/web_root/data_cache.js','utf8'),context);
    const cache=context.window.DataCache;cache.liveEnabled=false;
    const bar={symbol:'ETHUSDT',interval:'5m',open_time:300000,time:300,
        client:{symbol:'ETHUSDT',interval:'5m',open_time:300000,close_time:599999,open:2000,high:2001,low:1999,close:2000,volume:10},
        features:{symbol:'ETHUSDT',interval:'5m',open_time:300000,ema50:2000}};
    const packet={symbol:'ETHUSDT',interval:'5m',bars:[bar],next_before:null};
    const reply=data=>context.fetch=async()=>({ok:true,status:200,json:async()=>structuredClone(data)});
    return {cache,context,packet,reply};
}

test('wrong market/timeframe or nested feature identity is rejected before admission',async()=>{
    for(const change of [p=>p.symbol='BTCUSDT',p=>p.interval='15m',p=>p.bars[0].symbol='BTCUSDT',
        p=>p.bars[0].client.symbol='BTCUSDT',p=>p.bars[0].client.interval='15m',
        p=>p.bars[0].features.symbol='BTCUSDT',p=>p.bars[0].features.open_time=0,
        p=>p.bars.push(structuredClone(p.bars[0]))]){
        const {cache,packet,reply}=fixture();change(packet);reply(packet);
        await assert.rejects(cache.loadInitial('ETHUSDT','5m'),/Rejected mismatched chart response/);
        assert.equal(cache.bars.length,0);assert.match(cache.error,/ETHUSDT 5m/);
    }
});

test('valid stored identity is accepted and a wrong live quote never replaces it',async()=>{
    const {cache,packet,reply}=fixture();reply(packet);
    await cache.loadInitial('ETHUSDT','5m');assert.equal(cache.bars[0].client.close,2000);
    cache.liveEnabled=true;
    const wrong={symbol:'ETHUSDT',interval:'5m',live:{status:'live',bar:{...packet.bars[0],symbol:'BTCUSDT'}}};
    reply(wrong);
    await assert.rejects(cache.refreshLive(),/live quote identity/);
    assert.equal(cache.liveQuote,null);assert.equal(cache.bars[0].symbol,'ETHUSDT');
    assert.equal(cache.liveStatus,'response mismatch');
});
