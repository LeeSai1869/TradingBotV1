import test from 'node:test';
import assert from 'node:assert/strict';
import {zoneReadiness} from '../Section_11_UI_UX/overlays/zones/readiness.js';
test('higher-frame repairs are explained instead of being called missing candles',()=>{
    const text=zoneReadiness({zone_repairs:['FVG','Support / Resistance']},{'1w':{status:'feature repair pending'}},{bull_fvg_zones:{visible:true},inst_support_zones:{visible:true},bull_fvg_1w_zones:{visible:true}},'4h');
    assert.match(text,/Zone coverage pending feature repair: FVG, Support/);
    assert.match(text,/1w FVG: feature repair pending/);
});
test('disabled or ready zones do not show a pending warning',()=>{
    assert.equal(zoneReadiness({zone_repairs:['FVG']},{'1w':{status:'ready'}},{},'4h'),'');
    assert.equal(zoneReadiness(null,{current:{status:'ready'}},{bull_fvg_zones:{visible:true}},'4h'),'');
});
