import test from 'node:test';
import assert from 'node:assert/strict';
import {obSegments} from '../Section_11_UI_UX/overlays/zones/ob.js';
import {FEATURE_STYLES,normalizeStyles} from '../Section_11_UI_UX/controls/settings/feature_styles.js';
const key='normal_bull_ob_zones',config={[key]:{visible:true}};
const zone={side:'bull',kind:'ob',strict:false,low:10,high:12,strength:1.5};
const bar=(i,events)=>({time:i*60,client:{open_time:i*60000,close_time:(i+1)*60000-1},features:{ob_zone_events:JSON.stringify(events)}});
test('older valid OBs remain connected after a new same-side block and stop at invalidation',()=>{
 const bars=[bar(0,[{id:'a',...zone,before:null}]),bar(1,[{id:'b',...zone,low:13,high:14,before:null}]),bar(2,[]),bar(3,[{id:'a',removed:true,before:zone,terminal:{...zone,invalidated_bar:3}}]),bar(4,[])];
 const items=obSegments(bars,config);
 assert.equal(items.length,2);assert.equal(items[0].start,0);assert.equal(items[0].end,180);assert.equal(items[0].invalidated,true);
 assert.equal(items[1].end,240);assert.equal(items[0].score,1.5);
});
test('checkpoint seeds pre-window blocks and masked repairs never extend them',()=>{
 const items=obSegments([bar(5,[]),bar(6,[])],config,{through:360,ob_zones:{a:zone}});
 assert.equal(items.length,1);assert.equal(items[0].start,300);assert.equal(items[0].end,360);
 const masked=obSegments([bar(5,[]),{time:360,features:{}},bar(7,[])],config,{through:420,ob_zones:{a:zone}});
 assert.equal(masked[0].truncated,true);assert.equal(masked[0].end,300);
});
test('normal, strict and breaker visibility are independent; no invented legacy lifetimes',()=>{
 assert.equal(FEATURE_STYLES['Order Blocks'].outputs.length,8);
 const styles=normalizeStyles({[key]:{visible:true,style:3,scores:false}});
 assert.equal(styles[key].style,3);assert.equal(styles[key].scores,false);
 assert.equal(styles.strict_bull_ob_zones.visible,false);
 assert.deepEqual(obSegments([{time:0,features:{active_bull_ob_low:10,active_bull_ob_high:12}}],config),[]);
});
