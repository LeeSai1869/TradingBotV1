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
    const config=normalizeStyles({opportunity_buy_1:{visible:true,preview:true},opportunity_buy_2:{visible:false},opportunity_buy_3:{visible:true}});
    const rows=targetRows(bar,config);assert.equal(rows.length,1);assert.equal(rows[0].price,105);
    assert.match(targetLabel(rows[0]),/BUY T1 @ 105.0000 · net 4.80% · 1.20R/);
    assert.deepEqual(targetRows({...bar,provisional:true},config),[]);
    assert.deepEqual(targetRows({opportunity:{status:'unavailable'}},config),[]);
});
test('cost settings reject invalid saved values and preserve display controls',()=>{
    const config=normalizeStyles({opportunity_buy_1:{feeBps:8,slippageBps:3,visible:true}});
    assert.equal(config.opportunity_buy_1.feeBps,8);assert.equal(config.opportunity_buy_1.slippageBps,3);
    assert.equal(config.opportunity_buy_2.visible,false);
    assert.equal(normalizeStyles({opportunity_buy_1:{feeBps:-1}}).opportunity_buy_1.feeBps,0);
});

test('anchored levels use the decision point rather than the latest close',()=>{
    const config=normalizeStyles({opportunity_sell_1:{visible:true},opportunity_buy_1:{visible:true}});
    const context={side:'SELL',state:'active',open_time:1000,entry:81000,plan:{entry:81000,invalidation:83000,targets:[{price:78000,net_reward_pct:3.5,reward_risk:1.5}]}};
    const row={open_time:2000,signal_context:context,opportunity:{status:'ready',sell:{entry:85000,targets:[{price:82000}]}}};
    const targets=targetRows(row,config);
    assert.equal(targets.length,1);assert.equal(targets[0].price,78000);assert.equal(targets[0].entry,81000);
    assert.equal(targets[0].anchorTime,1000);assert.equal(targets[0].side,'sell');
    assert.deepEqual(targetRows({...row,signal_context:{...context,state:'invalidated'}},config),[]);
    assert.deepEqual(targetRows({...row,signal_context:null},config),[]);
});
test('directional setup modes are displayed explicitly',()=>{
    const config=normalizeStyles();
    const row={confidence:{status:'ready',sell_status:'ready',sell_mode:'reversal',sell_score:82}};
    assert.equal(confidenceLabel(row,'sell',config),'SELL · reversal 82/100');
});
