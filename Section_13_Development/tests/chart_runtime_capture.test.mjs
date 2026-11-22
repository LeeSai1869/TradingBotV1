import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

test('runtime capture observes only new work and restores original chart methods',async()=>{
    let clock=100,resourceCallback;
    const old={op:'old',ms:999},composer={config:{featureStyles:{rsi:{visible:true},adx:{visible:false}}},
        updateLive(){},updateAll(){},updateLiquidity(){}};
    const original=composer.updateLive;
    class Observer {
        static supportedEntryTypes=['resource'];
        constructor(callback){resourceCallback=callback;}
        observe(){} disconnect(){} takeRecords(){return [];}
    }
    const fresh={name:'http://localhost/api/chart_live?private=hidden',startTime:2100,responseEnd:2102,duration:2,transferSize:42,decodedBodySize:50};
    const context={window:{Composer:composer,ChartRenderTimings:[old],DataCache:{}},PerformanceObserver:Observer,
        performance:{now:()=>clock,getEntriesByType:()=>{throw Error('shared buffer must not be used when observation is supported');}},
        requestAnimationFrame(fn){clock+=1000;composer.updateLive(null,{bars:[]});if(clock===2100)resourceCallback({getEntries:()=>[fresh]});fn(clock);},
        document:{querySelector:()=>null,visibilityState:'visible'},navigator:{userAgent:'fixture'},location:{origin:'http://localhost'},
        devicePixelRatio:2,URL,console:{log(){}}};
    const report=await vm.runInNewContext(fs.readFileSync('Section_13_Development/diagnostics/capture_chart_runtime.js','utf8'),context);
    assert.equal(report.version,2);assert.equal(report.render_timings.length,10);
    assert.equal(report.recent_requests.length,1);assert.equal(report.recent_requests[0].route,'/api/chart_live');
    assert.equal(report.long_task_observer_supported,false);
    assert.deepEqual(Array.from(report.visible_features),['rsi']);
    assert.equal(composer.updateLive,original);assert.equal(context.window.ChartRenderTimings[0],old);
});
