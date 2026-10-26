import test from 'node:test';
import assert from 'node:assert/strict';
import {fresh,bandRows,bandLabel,currentBookVisible,feedState,bookGutter,heatmapSpans} from '../Section_11_UI_UX/overlays/liquidity/index.js';
import {normalizeStyles,FEATURE_STYLES} from '../Section_11_UI_UX/controls/settings/feature_styles.js';
const latest={observed:true,market:'usdt_perpetual',available_ms:1000,book_received_ms:1000,
    bands:[{side:'bid',low:99,high:100,notional_usdt:200},{side:'ask',low:101,high:102,notional_usdt:400}]};
test('only fresh synchronized perpetual depth is shown as current',()=>{
    assert.equal(fresh({status:'live',latest},1000),latest);
    assert.equal(fresh({status:'live',latest},11001),null);
    assert.equal(fresh({status:'stale',latest},1000),null);
    assert.equal(fresh({status:'live',latest},999),null);
});
test('buy/sell bands preserve observed notional and independent toggles',()=>{
    const config=normalizeStyles({liquidity_bids:{visible:true,opacity:40}});
    const rows=bandRows(latest,config);assert.equal(rows.length,1);assert.equal(rows[0].notional_usdt,200);
    assert.match(bandLabel(rows[0]),/Resting bids/);assert.match(bandLabel(rows[0]),/200 USDT/);
    assert.deepEqual(bandRows({...latest,market:'spot'},config),[]);
    assert.deepEqual(bandRows({...latest,observed:false},config),[]);
    assert.equal(FEATURE_STYLES.Liquidity.outputs.length,3);
    assert.equal(config.liquidity_bids.opacity,40);assert.equal(config.liquidity_asks.visible,false);
});


test('current depth stays visible between closed candles without a provisional candle',()=>{
    const bars=[{time:60,open_time:60000,client:{close_time:119999}}];
    const sample={sampled_ms:125000};
    assert.equal(currentBookVisible(sample,bars,true,{from:0,to:180}),true);
    assert.equal(currentBookVisible({...sample,sampled_ms:179999},bars),true);
    assert.equal(currentBookVisible(sample,[{...bars[0],provisional:true}]),true);
    assert.equal(currentBookVisible({...sample,sampled_ms:180000},bars),false);
});
test('current depth never projects onto a historical viewport or unrelated old candles',()=>{
    const bars=[{time:60,open_time:60000,client:{close_time:119999}}],sample={sampled_ms:125000};
    assert.equal(currentBookVisible(sample,bars,false),false);
    assert.equal(currentBookVisible(sample,bars,true,{from:0,to:59}),false);
    assert.equal(currentBookVisible({sampled_ms:999999},bars),false);
    assert.equal(currentBookVisible(sample,[]),false);
    assert.equal(currentBookVisible(null,bars),false);
});

test('an expired cached live packet is labelled stale rather than live',()=>{
    assert.equal(feedState({status:'live',latest},1000),'live');
    assert.equal(feedState({status:'live',latest},11001),'stale');
    assert.equal(feedState({status:'resynchronizing',latest:null},1000),'resynchronizing');
});

test('current-book geometry never covers the last candle or its wick',()=>{
    const gutter=bookGutter(1000,940,6);
    assert.ok(gutter.left>940+6/2);assert.ok(gutter.right<1000);
    assert.equal(gutter.origin,gutter.right);
    assert.equal(gutter.origin-gutter.maxWidth,gutter.left);
    assert.equal(bookGutter(1000,990,6),null);
});
test('subpixel heatmap time widths stay exact and leave the live candle clear',()=>{
    assert.deepEqual(heatmapSpans(10,.025,null,6),[{x:10,width:.025}]);
    assert.deepEqual(heatmapSpans(100,1,100,6),[]);
    assert.deepEqual(heatmapSpans(90,20,100,6),[{x:90,width:6},{x:104,width:6}]);
    assert.deepEqual(heatmapSpans(90,2,100,6),[{x:90,width:2}]);
});
