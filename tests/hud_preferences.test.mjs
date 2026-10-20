import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeHud, INTERVALS, DEFAULT_HUD} from '../Section_11_UI_UX/controls/workspace/preferences.js';

test('HUD preferences preserve an independent reference and ordered selections',()=>{
    const state=normalizeHud({symbol:'BTCUSDT',intervals:['4h','1m','4h'],fields:['features.di_direction','features.rsi']});
    assert.deepEqual(state,{symbol:'BTCUSDT',intervals:['4h','1m'],fields:['features.di_direction','features.rsi']});
});
test('HUD preferences bound columns and rows and recover empty selections',()=>{
    assert.equal(normalizeHud({intervals:INTERVALS}).intervals.length,8);
    assert.equal(normalizeHud({fields:Array.from({length:30},(_,i)=>`features.ema${i}`)}).fields.length,20);
    assert.deepEqual(normalizeHud({symbol:'../bad',intervals:['invalid'],fields:[]}),DEFAULT_HUD);
    assert.deepEqual(normalizeHud(null),DEFAULT_HUD);
});
