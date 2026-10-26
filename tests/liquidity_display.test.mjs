import test from 'node:test';
import assert from 'node:assert/strict';
import {fresh,bandRows,bandLabel} from '../Section_11_UI_UX/overlays/liquidity/index.js';
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
