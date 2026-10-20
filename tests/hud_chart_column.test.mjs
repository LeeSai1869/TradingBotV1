import test from 'node:test';
import assert from 'node:assert/strict';
import {chartColumn} from '../Section_11_UI_UX/controls/workspace/chart_column.js';
const cache=()=>({symbol:'BTCUSDT',timeframe:'1m',loading:false,atLiveEdge:true,liveStatus:'live',
    latestBar:{open_time:60000,client:{close:10,close_time:119999},features:{rsi:40}},
    formingBar:{open_time:120000,provisional:true,client:{close:12,close_time:179999},features:{rsi:62}}});
test('HUD projects the exact chart live bar and feature values without fetching',()=>{
    const column=chartColumn(cache(),'BTCUSDT','1m',['client.close','features.rsi','features.adx'],150000);
    assert.deepEqual(column.values,{'client.close':12,'features.rsi':62,'features.adx':null});
    assert.equal(column.status,'live provisional candle');assert.equal(column.open_time,120000);
});
test('unavailable live feed uses the closed chart bar; other pairs and history require fresh snapshots',()=>{
    const state=cache();state.liveStatus='unavailable';
    assert.equal(chartColumn(state,'BTCUSDT','1m',['features.rsi'],150000).values['features.rsi'],40);
    assert.equal(chartColumn(state,'ETHUSDT','1m',[]),null);
    assert.equal(chartColumn(state,'BTCUSDT','1h',[]),null);
    state.atLiveEdge=false;assert.equal(chartColumn(state,'BTCUSDT','1m',[]),null);
});
