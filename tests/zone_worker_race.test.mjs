import test from 'node:test';
import assert from 'node:assert/strict';
import * as candles from '../Section_11_UI_UX/overlays/candles/index.js';
import * as zones from '../Section_11_UI_UX/overlays/zones/index.js';

test('worker jobs coalesce and old datasets cannot replace the selected chart',()=>{
    const sent=[];let worker;
    globalThis.window={Composer:{config:{featureStyles:{}}}};
    globalThis.LightweightCharts={CandlestickSeries:{}};
    globalThis.Worker=class{constructor(){worker=this;}postMessage(task){sent.push(task);}terminate(){}};
    const series={attachPrimitive(){},removePriceLine(){},createPriceLine(){}};
    candles.mount({addSeries:()=>series});zones.mount();
    const data=frame=>({symbol:'BTCUSDT',timeframe:frame,bars:[{time:60,client:{close:100},features:{}}],fvgFrames:{},srFrames:{}});
    zones.update(null,data('5m'));
    zones.update(null,data('15m'));
    zones.update(null,data('1h'));
    assert.equal(sent.length,1,'only one expensive job should run at a time');
    worker.onmessage({data:{id:sent[0].id,items:[{identity:'obsolete',end:60}],ms:400}});
    assert.equal(zones.getSegments().length,0);
    assert.equal(sent.length,2);assert.equal(sent[1].target,'1h','skip superseded queued timeframe');
    worker.onmessage({data:{id:sent[1].id,items:[{identity:'current',end:60}],ms:200}});
    assert.equal(zones.getSegments()[0].identity,'current');
    assert.equal(zones.getProjectionStats().pending,false);
    assert.equal(zones.getProjectionStats().worker,true);
    delete globalThis.Worker;
});
