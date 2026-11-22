import test from 'node:test';
import assert from 'node:assert/strict';
import {PaintCache,viewportKey} from '../../Section_11_UI_UX/chart/paint_cache.js';

function fixture(){
    const original=globalThis.document;let blits=0,paints=0;
    const offscreen={setTransform(){},clearRect(){}};
    globalThis.document={createElement:()=>({width:0,height:0,getContext:()=>offscreen})};
    const context={getTransform:()=>({a:2,d:2,b:0,c:0,e:0,f:0}),drawImage(){blits++;}};
    const scope={context,mediaSize:{width:800,height:400}},cache=new PaintCache();
    return {cache,scope,paint(){paints++;},counts:()=>({paints,blits}),restore(){globalThis.document=original;}};
}

test('crosshair repaints reuse one bitmap; viewport, revision and DPR invalidate',()=>{
    const f=fixture();try{
        for(let i=0;i<100;i++)f.cache.draw(f.scope,[1,0,100],f.paint);
        assert.deepEqual(f.counts(),{paints:1,blits:100});assert.equal(f.cache.stats.hits,99);
        f.cache.draw(f.scope,[2,0,100],f.paint);assert.equal(f.counts().paints,2);
        f.cache.draw(f.scope,[2,1,101],f.paint);assert.equal(f.counts().paints,3);
        f.cache.invalidate();f.cache.draw(f.scope,[2,1,101],f.paint);assert.equal(f.counts().paints,4);
        f.scope.context.getTransform=()=>({a:1,d:1,b:0,c:0,e:0,f:0});
        f.cache.draw(f.scope,[2,1,101],f.paint);assert.equal(f.counts().paints,5);
        f.cache.clear();assert.equal(f.cache.canvas,null);
    }finally{f.restore();}
});
test('oversized and unusual transforms use direct drawing without keeping a bitmap',()=>{
    const f=fixture();try{
        f.cache.draw(f.scope,1,f.paint);
        f.scope.mediaSize={width:10000,height:10000};f.cache.draw(f.scope,1,f.paint);
        assert.equal(f.cache.canvas,null);assert.equal(f.cache.stats.direct,1);
        f.scope.mediaSize={width:800,height:400};
        f.scope.context.getTransform=()=>({a:2,d:2,b:0,c:0,e:1,f:0});
        f.cache.draw(f.scope,1,f.paint);assert.equal(f.cache.stats.direct,2);
        assert.equal(f.counts().paints,3);
    }finally{f.restore();}
});
test('viewport keys change for horizontal pan, price scaling and bar spacing',()=>{
    let from=1,offset=0,spacing=5;
    const chart={timeScale:()=>({getVisibleLogicalRange:()=>({from,to:10}),options:()=>({barSpacing:spacing})})};
    const series={priceToCoordinate:p=>p+offset};
    const initial=viewportKey(chart,series,100);
    from++;assert.notDeepEqual(viewportKey(chart,series,100),initial);from--;
    offset++;assert.notDeepEqual(viewportKey(chart,series,100),initial);offset--;
    spacing++;assert.notDeepEqual(viewportKey(chart,series,100),initial);
});

test('unavailable bitmap allocation falls back to the original renderer',()=>{
    const f=fixture();try{
        globalThis.document.createElement=()=>{throw Error('canvas allocation unavailable');};
        f.cache.draw(f.scope,1,f.paint);
        assert.equal(f.counts().paints,1);assert.equal(f.cache.stats.direct,1);assert.equal(f.cache.canvas,null);
    }finally{f.restore();}
});
