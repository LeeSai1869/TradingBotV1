import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {normalizeStyles} from '../../Section_11_UI_UX/controls/settings/feature_styles.js';
import {structureSegments} from '../../Section_11_UI_UX/overlays/zones/structure.js';
const code=fs.readFileSync(new URL('../../Section_11_UI_UX/overlays/structure_tags/index.js',import.meta.url),'utf8')
 .replace("import {getSeries} from '../candles/index.js';",'const getSeries=()=>globalThis.mockSeries;');
const tags=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const bar=(i,f)=>({time:i*60,open_time:i*60000,client:{close_time:(i+1)*60000-1},features:f});
const styles=normalizeStyles({protected_high:{visible:true},protected_low:{visible:true},latest_confirmed_pivot_high:{visible:true},latest_confirmed_pivot_low:{visible:true}});
test('current protected levels survive a flat loaded window with no publication change',()=>{
 const bars=[bar(1,{protected_high:12,protected_low:8}),bar(2,{protected_high:12,protected_low:8})];
 assert.equal(tags.structureTags(bars,styles).length,0);
 assert.deepEqual(tags.structureGeometry(bars,styles).protectedLevels.map(l=>[l.label,l.price]),[['PH',12],['PL',8]]);
 assert.equal(tags.structureGeometry(bars,normalizeStyles({})).protectedLevels.length,0);
});
test('trend-line visibility migrates from confirmed outputs but explicit disabling wins',()=>{
 assert.equal(styles.structure_high_trendline.visible,true);
 assert.equal(styles.structure_low_trendline.visible,true);
 assert.equal(normalizeStyles({latest_confirmed_pivot_high:{visible:true},structure_high_trendline:{visible:false}}).structure_high_trendline.visible,false);
});
test('trend lines use deduplicated confirmed origins, excluding candidates and provisional data',()=>{
 const event=(o,p)=>({type:'PIVOT_HIGH',origin_time:o*60000,confirmation_time:(o+1)*60000,price:p});
 const bars=[bar(0,{}),bar(1,{structure_events:JSON.stringify([event(0,12)])}),bar(2,{candidate_pivot:1,candidate_pivot_high_price:14,structure_events:'[]'}),bar(3,{structure_events:JSON.stringify([event(2,13)])}),{...bar(4,{structure_events:JSON.stringify([event(3,99)])}),provisional:true}];
 assert.deepEqual(tags.structureGeometry(bars,styles).trendLines[0].points,[{time:0,price:12},{time:120,price:13}]);
});
test('range band requires an actual range and never fabricates bounds for a bear trend',()=>{
 assert.deepEqual(structureSegments([bar(1,{current_structure:'STRUCTURE_BEAR',structure_range_low:null,structure_range_high:null})],{structure_range_zones:{visible:true}}),[]);
 const ranges=structureSegments([bar(1,{current_structure:'STRUCTURE_RANGE',structure_range_low:8,structure_range_high:12,structure_origin_bar:0}),bar(2,{})],{structure_range_zones:{visible:true}});
 assert.equal(ranges.length,1);assert.equal(ranges[0].low,8);assert.equal(ranges[0].high,12);
});
test('off-screen PH/PL draw edge prices even without tags and do not change autoscaling',()=>{
 let primitive;const text=[];
 const chart={timeScale:()=>({getVisibleRange:()=>({from:0,to:300}),timeToCoordinate:t=>t})};
 globalThis.mockSeries={attachPrimitive:p=>{primitive=p;p.attached({chart,series:globalThis.mockSeries,requestUpdate:()=>{}});},options:()=>({visible:true}),priceToCoordinate:p=>1000-p};
 globalThis.window={Composer:{config:{featureStyles:styles}}};tags.mount();tags.update(chart,{bars:[bar(1,{protected_high:12,protected_low:8})]});
 const context={save(){},restore(){},setLineDash(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){},measureText:t=>({width:t.length*6}),fillText:t=>text.push(t)};
 primitive.draw({useMediaCoordinateSpace:fn=>fn({context,mediaSize:{width:500,height:300}})});
 assert.ok(text.some(t=>t.includes('PH 12')&&t.includes('↓')));assert.ok(text.some(t=>t.includes('PL 8')&&t.includes('↓')));
 delete globalThis.window;delete globalThis.mockSeries;
});

test('only the current candidate is drawn, including delayed activation with an older origin',()=>{
 const cfg=normalizeStyles({candidate_high_tag:{visible:true},candidate_low_tag:{visible:true}});
 const bars=[bar(0,{}),bar(1,{candidate_pivot:-1,candidate_pivot_low_time:0,candidate_pivot_low_price:8}),bar(2,{candidate_pivot:1,candidate_pivot_high_time:0,candidate_pivot_high_price:12})];
 assert.deepEqual(tags.structureTags(bars,cfg).map(t=>[t.label,t.time,t.price]),[['CH',0,12]]);
 bars.push(bar(3,{candidate_pivot:1,candidate_pivot_high_time:180000,candidate_pivot_high_price:13}));
 assert.deepEqual(tags.structureTags(bars,cfg),[]);
 bars.push(bar(4,{candidate_pivot:1,candidate_pivot_high_time:180000,candidate_pivot_high_price:13}));
 assert.deepEqual(tags.structureTags(bars,cfg).map(t=>[t.label,t.time,t.price]),[['CH',180,13]]);
});
