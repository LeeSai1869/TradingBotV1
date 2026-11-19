import test from 'node:test';
import assert from 'node:assert/strict';
import * as candles from '../Section_11_UI_UX/overlays/candles/index.js';

test('current price ray remains visible when the quote is ahead of stored candles',()=>{
    globalThis.LightweightCharts={CandlestickSeries:{},LineStyle:{Dotted:1}};
    globalThis.window={Composer:{config:{}}};
    let primitive,lineOptions;
    let points=[];
    const series={attachPrimitive:p=>primitive=p,options:()=>({visible:true,upColor:'green',downColor:'red'}),
        applyOptions(){},setData:data=>points=data,data:()=>points,priceToCoordinate:price=>price,
        createPriceLine:options=>{lineOptions=options;return {applyOptions:o=>lineOptions=o};}};
    let coordinates=new Map([[60,40]]);
    const chart={addSeries:()=>series,timeScale:()=>({timeToCoordinate:time=>coordinates.get(time)??null})};
    candles.mount(chart);primitive.attached({chart,series,requestUpdate(){}});
    candles.update(chart,{bars:[{time:60,client:{open:100,close:100}}]});
    candles.updateQuote(chart,{time:120,client:{open:100,close:105}});
    const calls=[];const ctx={save(){},restore(){},beginPath(){},stroke(){calls.push('stroke');},
        setLineDash:dash=>calls.push(['dash',dash]),moveTo:(x,y)=>calls.push(['from',x,y]),lineTo:(x,y)=>calls.push(['to',x,y])};
    const target={useMediaCoordinateSpace:draw=>draw({context:ctx,mediaSize:{width:200,height:150}})};
    primitive.draw(target);
    assert.deepEqual(calls,[['dash',[]],['from',40,105],['to',200,105],'stroke']);
    assert.equal(lineOptions.title,'');assert.equal(lineOptions.price,105);
    assert.equal(series.data().length,1);assert.equal(series.data()[0].time,60,'a live quote must not create a candle across a gap');
    calls.length=0;coordinates=new Map();primitive.draw(target);
    assert.deepEqual(calls,[['dash',[2,3]],['from',0,105],['to',200,105],'stroke']);
    calls.length=0;coordinates=new Map([[60,300]]);primitive.draw(target);
    assert.deepEqual(calls,[['dash',[2,3]],['from',0,105],['to',200,105],'stroke']);
});
