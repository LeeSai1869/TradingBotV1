import test from 'node:test';
import assert from 'node:assert/strict';
import {fresh,bandRows,bandLabel,currentBookVisible,feedState,profileRows,stackedSegments,heatmapSpans} from '../Section_11_UI_UX/overlays/liquidity/index.js';
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

test('one price band joins green bids and red asks into one proportional bar',()=>{
    const sample={observed:true,market:'usdt_perpetual',bands:[
        {side:'bid',low:100,high:101,notional_usdt:30},
        {side:'ask',low:100,high:101,notional_usdt:70},
        {side:'bid',low:99,high:100,notional_usdt:200},
    ]};
    const config={liquidity_bids:{visible:true},liquidity_asks:{visible:true}};
    const rows=profileRows(sample,config);assert.equal(rows.length,2);
    const row=rows.find(r=>r.low===100);assert.equal(row.total,100);
    const [green,red]=stackedSegments(row,200,p=>1000-p,1000,40);
    assert.equal(green.band.side,'bid');assert.equal(red.band.side,'ask');
    assert.equal(green.y,red.y);assert.equal(green.height,red.height);
    assert.equal(green.x+green.width,red.x);assert.equal(red.x+red.width,995);
    assert.equal(green.width,60);assert.equal(red.width,140);
    const largest=stackedSegments(rows.find(r=>r.low===99),200,p=>1000-p,1000,40);
    assert.equal(largest.length,1);assert.equal(largest[0].width,400);
});
test('missing side remains empty and toggles never fabricate opposite liquidity',()=>{
    const config=normalizeStyles({liquidity_bids:{visible:true}});
    const rows=profileRows(latest,config);assert.equal(rows.length,1);
    assert.equal(rows[0].ask,0);
    const segments=stackedSegments(rows[0],rows[0].total,p=>p,1000,45);
    assert.equal(segments.length,1);assert.equal(segments[0].band.side,'bid');
    assert.equal(config.liquidity_bids.lengthPercent,45);
});
test('subpixel heatmap time widths stay exact and leave the live candle clear',()=>{
    assert.deepEqual(heatmapSpans(10,.025,null,6),[{x:10,width:.025}]);
    assert.deepEqual(heatmapSpans(100,1,100,6),[]);
    assert.deepEqual(heatmapSpans(90,20,100,6),[{x:90,width:6},{x:104,width:6}]);
    assert.deepEqual(heatmapSpans(90,2,100,6),[{x:90,width:2}]);
});
