import test from 'node:test';
import assert from 'node:assert/strict';
import {confidenceLabel,targetRows,targetLabel} from '../Section_11_UI_UX/overlays/opportunity/index.js';
import {normalizeStyles} from '../Section_11_UI_UX/controls/settings/feature_styles.js';

test('confidence is an optional evidence score beside its own signal',()=>{
    const config=normalizeStyles();
    const bar={confidence:{status:'ready',buy_score:71.2,sell_score:24.5}};
    assert.equal(confidenceLabel(bar,'buy',config),'BUY · 71/100');
    assert.equal(confidenceLabel(bar,'sell',config),'SELL · 25/100');
    assert.equal(confidenceLabel({confidence:{status:'insufficient evidence',buy_score:65}},'buy',config),'BUY · confidence pending');
    config.confidence_buy.visible=false;
    assert.equal(confidenceLabel(bar,'buy',config),'BUY');
});
test('three independent target toggles preserve scenario direction and missing layers',()=>{
    const bar={opportunity:{status:'ready',buy:{invalidation:95,targets:[{price:105,net_reward_pct:4.8,reward_risk:1.2},{price:110,net_reward_pct:9.8,reward_risk:2.4}]},sell:{targets:[]}}};
    const config=normalizeStyles({opportunity_buy_1:{visible:true},opportunity_buy_2:{visible:false},opportunity_buy_3:{visible:true}});
    const rows=targetRows(bar,config);assert.equal(rows.length,1);assert.equal(rows[0].price,105);
    assert.match(targetLabel(rows[0]),/BUY T1 · net 4.80% · 1.20R/);
    assert.deepEqual(targetRows({...bar,provisional:true},config),[]);
    assert.deepEqual(targetRows({opportunity:{status:'unavailable'}},config),[]);
});
test('cost settings reject invalid saved values and preserve display controls',()=>{
    const config=normalizeStyles({opportunity_buy_1:{feeBps:8,slippageBps:3,visible:true}});
    assert.equal(config.opportunity_buy_1.feeBps,8);assert.equal(config.opportunity_buy_1.slippageBps,3);
    assert.equal(config.opportunity_buy_2.visible,false);
    assert.equal(normalizeStyles({opportunity_buy_1:{feeBps:-1}}).opportunity_buy_1.feeBps,0);
});
