import test from 'node:test';
import assert from 'node:assert/strict';
import {coalesceRender} from '../../Section_11_UI_UX/web_root/render_queue.js';

test('liquidity notifications preserve queued history, live, settings and latest work',()=>{
    for(const op of ['history','live','settings','stored-refresh','reload']){
        const prior={op,reset:false,latest:true,span:120};
        assert.deepEqual(coalesceRender(prior,'liquidity'),prior);
    }
    assert.equal(coalesceRender(null,'liquidity').op,'liquidity');
});
test('candle and market changes replace queued liquidity; reset dominates settings',()=>{
    for(const op of ['live','history','stored-refresh','settings'])assert.equal(coalesceRender({op:'liquidity'},op).op,op);
    assert.deepEqual(coalesceRender({op:'settings',latest:true,span:120},'loading',true),
        {op:'loading',reset:true,latest:false,span:undefined});
    assert.equal(coalesceRender({op:'history',reset:true},'liquidity').reset,true);
    assert.equal(coalesceRender({op:'settings'},'live').op,'settings');
});
