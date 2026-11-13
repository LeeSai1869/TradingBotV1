import test from 'node:test';
import assert from 'node:assert/strict';
import {FEATURE_STYLES,migrateStyles} from '../Section_11_UI_UX/controls/settings/feature_styles.js';
import {changeFeature,hiddenFeatures,legendEntries} from '../Section_11_UI_UX/controls/settings/feature_legend.js';
const preferences=()=>({outputs:migrateStyles(),hiddenFeatures:{},ema:true,markers:true});
test('every connected feature can hide, restore its exact outputs, and be removed without changing styles',()=>{
    for(const [name,feature] of Object.entries(FEATURE_STYLES)){
        if(!feature.connected)continue;
        const p=preferences();for(const output of Object.values(p.outputs))output.visible=false;
        const key=feature.outputs[0][0];p.outputs[key].visible=true;p.outputs[key].color='#123abc';
        assert.deepEqual(legendEntries(p),[{name,hidden:false}]);
        const hidden=changeFeature(p,name,'hide');
        assert.equal(p.outputs[key].visible,true);
        assert.equal(hidden.outputs[key].visible,false);
        assert.deepEqual(legendEntries(hidden),[{name,hidden:true}]);
        const restored=changeFeature(hidden,name,'show');assert.deepEqual(restored,p);
        const removed=changeFeature(hidden,name,'remove');assert.deepEqual(legendEntries(removed),[]);
        assert.equal(removed.outputs[key].color,'#123abc');
    }
});
test('saved hidden entries validate keys and clear when enabled again in settings',()=>{
    const p=preferences();for(const output of Object.values(p.outputs))output.visible=false;
    assert.deepEqual(hiddenFeatures({RSI:['rsi','unknown'],missing:['x']},p.outputs),{RSI:['rsi']});
    p.outputs.rsi.visible=true;
    assert.deepEqual(hiddenFeatures({RSI:['rsi']},p.outputs),{});
});
