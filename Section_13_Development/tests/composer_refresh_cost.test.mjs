import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

test('metadata refresh skips full series, while edits and settings still update',()=>{
    let source=fs.readFileSync('Section_11_UI_UX/web_root/composer.js','utf8');
    const context={window:{},performance,console};
    source=source.replace(/^import \* as (\w+) from .*;$/gm,(_,name)=>{context[name]={};return '';});
    vm.runInNewContext(source,context);
    const c=context.window.Composer,calls={};
    c.visuals=['candles','ema50','indicators','markers','zones'].map(name=>({name,
        update(){calls[name]=(calls[name]||0)+1;},updateLive(){}}));c.panels=[];
    const data={symbol:'BTCUSDT',timeframe:'5m',_barsVersion:1,_liveVersion:1,bars:[]};
    c.updateAll(null,data,'reload');c.updateAll(null,data,'stored-refresh');
    for(const name of ['candles','ema50','indicators','markers'])assert.equal(calls[name],1);
    assert.equal(calls.zones,2,'zone snapshots remain independently refreshable');
    data._liveVersion++;c.updateLive(null,data);c.updateAll(null,data,'stored-refresh');
    assert.equal(calls.indicators,1,'already applied live ticks must not rebuild history');
    data._barsVersion++;c.updateAll(null,data,'stored-refresh');assert.equal(calls.indicators,2);
    c.updateAll(null,data,'settings');assert.equal(calls.indicators,3);
    c.updateAll(null,data,'stored-refresh',{resetViewport:true});assert.equal(calls.indicators,4);
});

test('queued liquidity-only render leaves candle and indicator series untouched',()=>{
    let source=fs.readFileSync('Section_11_UI_UX/web_root/composer.js','utf8');
    const context={window:{},performance,console};
    source=source.replace(/^import \* as (\w+) from .*;$/gm,(_,name)=>{context[name]={};return '';});
    vm.runInNewContext(source,context);
    const c=context.window.Composer,calls={};
    c.visuals=['candles','ema50','indicators','markers','zones','liquidity'].map(name=>({name,
        update(){calls[name]=(calls[name]||0)+1;}}));c.panels=[];
    const data={symbol:'BTCUSDT',timeframe:'5m',_barsVersion:1,_liveVersion:1,bars:[]};
    c.updateAll(null,data,'reload');c.updateAll(null,data,'liquidity');
    for(const name of ['candles','ema50','indicators','markers','zones'])assert.equal(calls[name],1);
    assert.equal(calls.liquidity,2);
    // If data changed, a mislabeled event must still refresh all series.
    data._barsVersion++;
    c.updateAll(null,data,'liquidity');assert.equal(calls.indicators,2);
    c.updateAll(null,data,'settings');assert.equal(calls.indicators,3);
    c.updateAll(null,data,'liquidity',{resetViewport:true});assert.equal(calls.indicators,4);
    data.symbol='ETHUSDT';c.updateAll(null,data,'liquidity');assert.equal(calls.indicators,5);
    assert.equal(typeof context.window.ChartRenderTimings.at(-1).at,'number');
});
