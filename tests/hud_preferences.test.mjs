import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeHud, INTERVALS, DEFAULT_HUD} from '../Section_11_UI_UX/controls/workspace/preferences.js';

test('HUD preferences preserve an independent reference and ordered selections',()=>{
    const state=normalizeHud({symbol:'BTCUSDT',intervals:['4h','1m','4h'],fields:['features.di_direction','features.rsi']});
    assert.deepEqual(state,{...DEFAULT_HUD,symbol:'BTCUSDT',intervals:['4h','1m'],fields:['features.di_direction','features.rsi']});
});
test('HUD preferences bound columns and rows and recover empty selections',()=>{
    assert.equal(normalizeHud({intervals:INTERVALS}).intervals.length,8);
    assert.equal(normalizeHud({fields:Array.from({length:30},(_,i)=>`features.ema${i}`)}).fields.length,20);
    assert.deepEqual(normalizeHud({symbol:'../bad',intervals:['invalid'],fields:[]}),DEFAULT_HUD);
    assert.deepEqual(normalizeHud(null),DEFAULT_HUD);
});

test('HUD visibility and placement persist independently of the analysis panel',()=>{
    const state=normalizeHud({visible:false,position:'bottom-right'});
    assert.equal(state.visible,false);assert.equal(state.position,'bottom-right');
    assert.equal(normalizeHud({position:'invalid'}).position,'top-left');
});

test('HUD supports only BTC reference, normalizes styles and hides candle dates by default',()=>{
    assert.equal(normalizeHud({symbol:'ETHUSDT'}).symbol,'');
    const hud=normalizeHud({style:{fontSize:99,borderWidth:-2,borderStyle:'dotted',fontFamily:'monospace',showDates:true},size:{width:500,height:300}});
    assert.equal(hud.style.fontSize,24);assert.equal(hud.style.borderWidth,0);
    assert.equal(hud.style.borderStyle,'dotted');assert.equal(hud.style.showDates,true);
    assert.deepEqual(hud.size,{width:500,height:300});
    assert.equal(DEFAULT_HUD.style.showDates,false);
});
