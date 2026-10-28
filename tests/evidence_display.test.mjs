import test from 'node:test';
import assert from 'node:assert/strict';
import {confidenceLabel,targetRows,targetLabel,layoutLabels} from '../Section_11_UI_UX/overlays/opportunity/index.js';
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
test('three independent band toggles retain full bounds on the reference plan',()=>{
    const plan={entry:100,invalidation:95,targets:[{price:105,low:105,high:107,net_reward_pct:4.8,net_reward_far_pct:6.8,reward_risk:1.2},{price:115,low:115,high:117,net_reward_pct:14.8,reward_risk:2.4}]};
    const bar={signal_context:{side:'BUY',state:'active',open_time:1000,plan}};
    const config=normalizeStyles({opportunity_buy_1:{visible:true},opportunity_buy_2:{visible:false},opportunity_buy_3:{visible:true}});
    const rows=targetRows(bar,config);assert.equal(rows.length,1);assert.equal(rows[0].low,105);assert.equal(rows[0].high,107);
    assert.match(targetLabel(rows[0]),/Upside 1.*105.*107.*4.80–6.80%/);
    assert.deepEqual(targetRows({...bar,provisional:true},config),[]);
    assert.deepEqual(targetRows({opportunity:{status:'ready',buy:plan}},config),[]);
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
    assert.equal(targetRows({...row,signal_context:{...context,state:'invalidated'}},config).length,1);
    assert.deepEqual(targetRows({...row,signal_context:null},config),[]);
});
test('directional setup modes are displayed explicitly',()=>{
    const config=normalizeStyles();
    const row={confidence:{status:'ready',sell_status:'ready',sell_mode:'reversal',sell_score:82}};
    assert.equal(confidenceLabel(row,'sell',config),'SELL · reversal 82/100');
});

test('labels separate without changing the underlying band prices',()=>{
    const source=[{y:100,text:'A'},{y:101,text:'B'},{y:102,text:'C'}];
    const result=layoutLabels(source,300);
    assert.equal(result[1].textY-result[0].textY,18);
    assert.deepEqual(result.map(v=>v.y),[100,101,102]);
    assert.equal(normalizeStyles({opportunity_buy_1:{preview:true}}).opportunity_buy_1.preview,undefined);
});
