import test from 'node:test';
import assert from 'node:assert/strict';
import {srSegments} from '../Section_11_UI_UX/overlays/zones/sr.js';
const config={support_zones:{visible:true},resistance_zones:{visible:true},inst_support_zones:{visible:true}};
const zone=(low=10,high=12)=>({side:'support',low,high,institutional:false});
const bar=(i,events)=>({time:i*60,client:{open_time:i*60000,close_time:(i+1)*60000-1},features:{sr_zone_events:JSON.stringify(events)}});
test('selection changes and empty events do not split a live zone; removal ends it',()=>{
    const a=zone(),b=zone(15,17);
    const rows=[bar(0,[{id:'a',...a,before:null}]),bar(1,[{id:'b',...b,before:null}]),bar(2,[]),bar(3,[{id:'a',removed:true,before:a}]),bar(4,[])];
    const zones=srSegments(rows,config);
    assert.equal(zones.length,2);
    assert.deepEqual([zones[0].start,zones[0].end,zones[0].invalidated],[0,180,true]);
    assert.equal(zones[1].end,240);
});
test('merged bounds remain one connected zone without rewriting older bounds',()=>{
    const a=zone(),merged=zone(9,13);
    const rows=[bar(0,[{id:'a',...a,before:null}]),bar(1,[{id:'a',...merged,before:a}]),bar(2,[])];
    const [z]=srSegments(rows,config);
    assert.equal(z.end,120);assert.equal(z.history.length,2);
    assert.deepEqual(z.history.map(p=>[p.low,p.high]),[[10,12],[9,13]]);
});
test('checkpoint and reversible removals recover zones born before the chart window',()=>{
    const a=zone(),b=zone(15,17);
    const rows=[bar(10,[]),bar(11,[{id:'a',removed:true,before:a}]),bar(12,[])];
    const zones=srSegments(rows,config,{through:720,zones:{b}});
    assert.equal(zones.length,2);
    assert.equal(zones.find(z=>z.identity.endsWith(':a')).end,660);
    assert.equal(zones.find(z=>z.identity.endsWith(':b')).end,720);
});
test('institutional promotion changes style without double-painting the same zone',()=>{
    const a=zone(),inst={...a,institutional:true};
    const rows=[bar(0,[{id:'a',...a,before:null}]),bar(1,[{id:'a',...inst,before:a}]),bar(2,[{id:'a',...a,before:inst}])];
    const zones=srSegments(rows,config);
    assert.equal(zones.filter(z=>z.key==='support_zones').length,2);
    assert.equal(zones.find(z=>z.key==='support_zones').end,60);
    assert.deepEqual(zones.find(z=>z.key==='inst_support_zones').history[0],{time:60,low:10,high:12});
});
test('masked features and raw gaps cannot prove continuous validity',()=>{
    const rows=[bar(0,[{id:'a',...zone(),before:null}]),bar(1,[])];
    rows[1].features={};
    const [z]=srSegments(rows,config);assert.equal(z.end,0);assert.equal(z.truncated,true);
});
