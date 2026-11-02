import assert from 'node:assert/strict';
import {fieldValue,chartColumn} from '../Section_11_UI_UX/controls/workspace/chart_column.js';
import {normalizeHud} from '../Section_11_UI_UX/controls/workspace/preferences.js';
const bar={open_time:0,client:{close:100,close_time:59999},signal_context:{side:'BUY',entry:99,confidence:{buy_score:88}},opportunity:{areas:{resistance:[{low:105,high:106,confluence_families:3}]}}};
assert.equal(fieldValue(bar,'confidence.signal_score'),88);
assert.equal(fieldValue(bar,'opportunity.sell_1_families'),3);
assert.equal(fieldValue(bar,'opportunity.buy_1_low'),null);
assert.deepEqual(normalizeHud({fields:['adcn.final_score','adcn.signal_type']}).fields,['confidence.signal_score','signal_context.side']);
const packet=chartColumn({atLiveEdge:true,symbol:'BTCUSDT',timeframe:'1m',latestBar:bar,liveStatus:'live',formingBar:{open_time:60000,client:{close:101,close_time:119999},provisional:true}},'BTCUSDT','1m',['client.close','confidence.signal_score']);
assert.equal(packet.values['client.close'],101);assert.equal(packet.values['confidence.signal_score'],88);

assert.ok(normalizeHud({fields:'malformed'}).fields.length>0);
