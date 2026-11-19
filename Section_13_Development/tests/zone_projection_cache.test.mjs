import test from 'node:test';
import assert from 'node:assert/strict';
import {ProjectionCache} from '../../Section_11_UI_UX/overlays/zones/projection_cache.js';
import {segments} from '../../Section_11_UI_UX/overlays/zones/index.js';
const bar=i=>({time:i*60,client:{open_time:i*60000,close_time:(i+1)*60000-1,low:99,high:102,close:100},features:{sr_zone_events:'[]'}});
const fixture=()=>({symbol:'BTCUSDT',timeframe:'5m',bars:[bar(0),bar(1)],srSnapshot:null,fvgFrames:{},srFrames:{}});

test('live prices and unrelated features do not rebuild closed zone history',()=>{
    let calls=0;const cache=new ProjectionCache(()=>{calls++;return [{end:60,until:120}];});
    const data=fixture(),styles={support_zones:{visible:true}};
    data.bars.push({...bar(2),provisional:true});cache.get(data,styles);
    data.bars.at(-1).client.close=999;data.bars[0].features.rsi=70;
    cache.items[0].end=120;cache.get(data,styles);
    assert.equal(calls,1);assert.equal(cache.items[0].end,60);
    // Network responses recreate row objects; identical input values still hit.
    data.bars=JSON.parse(JSON.stringify(data.bars));cache.get(data,styles);
    assert.equal(calls,1);assert.equal(cache.hits,2);
});

test('history, replay edits, snapshot updates, settings and timeframe changes invalidate',()=>{
    let calls=0;const cache=new ProjectionCache(()=>{calls++;return [];});
    const data=fixture(),styles={support_zones:{visible:true}};
    cache.get(data,styles);
    for(const change of [()=>data.bars.unshift(bar(-1)),()=>data.bars[0].features.sr_zone_events='[{"id":"new"}]',
        ()=>data.bars[0].client.low=80,()=>data.srSnapshot={through:60,zones:{}},
        ()=>data.fvgFrames.current={version:'new'},()=>data.srFrames['1h']={through:60,zones:{}},
        ()=>styles.support_zones.visible=false,()=>data.timeframe='1h',()=>data.bars.push(bar(2))]){
        const before=calls;change();cache.get(data,styles);assert.equal(calls,before+1);
    }
});

test('cached display matches fresh full projection including the forming edge and HTF births',()=>{
    const data=fixture(),styles={bull_fvg_4h_zones:{visible:true}};
    data.timeframe='5m';data.bars.push({...bar(2),provisional:true});
    data.fvgFrames['4h']={bars:[],active:[{side:'bull',time:0,close_time:119999,low:80,high:90,score:3}]};
    const cache=new ProjectionCache(segments);
    for(let i=0;i<3;i++){
        const fresh=segments(data.bars,styles,{...data.fvgFrames,sr:data.srSnapshot,institutional:data.srFrames},data.timeframe);
        assert.deepEqual(cache.get(data,styles),fresh);
        data.bars.at(-1).client.close+=1;
    }
    assert.equal(cache.builds,1);
    assert.equal(cache.items.length,1);
});
