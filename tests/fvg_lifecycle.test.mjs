import test from 'node:test';
import assert from 'node:assert/strict';
import {fvgSegments,HTF} from '../Section_11_UI_UX/overlays/zones/fvg.js';
import {normalizeStyles} from '../Section_11_UI_UX/controls/settings/feature_styles.js';
const bar=(i,features={},prices={},step=60000)=>({time:i*step/1000,features,client:{open_time:i*step,close_time:(i+1)*step-1,open:13,high:14,low:13,close:13,...prices}});
const config={bull_fvg_zones:{visible:true},bear_fvg_zones:{visible:true}};
const birth={qualified_bull_fvg:true,bull_fvg_low:10,bull_fvg_high:12};

test('nearest switches and missing feature rows do not split a living FVG',()=>{
    const rows=[bar(0,birth),bar(1,{nearest_bull_fvg_low:4,nearest_bull_fvg_high:6,nearest_bull_fvg_created_bar:1,nearest_bull_fvg_age:0}),bar(2,null),bar(3,{}, {low:9,high:11,close:9}),bar(4)];
    const zones=fvgSegments(rows,config,{target:'1m',endTime:240});
    assert.equal(zones.length,2);
    assert.deepEqual([zones[0].start,zones[0].end,zones[0].invalidated],[0,180,true]);
    assert.deepEqual([zones[1].start,zones[1].end,zones[1].invalidated],[60,240,false]);
});
test('weak touches and wicks do not invalidate a gap; touched closed break does',()=>{
    const zones=fvgSegments([bar(0,birth),bar(1,{}, {low:9,high:14,close:13}),bar(2,{}, {low:10,high:12,close:11}),bar(3,{}, {low:9,high:11,close:9})],config,{target:'1m'});
    assert.equal(zones.length,1);assert.equal(zones[0].end,180);assert.equal(zones[0].invalidated,true);
});
test('bearish lifecycle uses touched close above high, not a wick above it',()=>{
    const rows=[bar(0,{qualified_bear_fvg:true,bear_fvg_low:15,bear_fvg_high:17}),bar(1,{}, {low:14,high:18,close:14}),bar(2,{}, {low:16,high:19,close:18})];
    const zones=fvgSegments(rows,config,{target:'1m'});
    assert.equal(zones[0].end,120);assert.equal(zones[0].invalidated,true);
});
test('forming candle extends an active gap without provisional invalidation',()=>{
    const rows=[bar(0,birth),{...bar(1,{}, {low:8,high:9,close:8}),provisional:true}];
    const zones=fvgSegments(rows,config,{target:'1m',endTime:60});
    assert.equal(zones[0].end,60);assert.equal(zones[0].invalidated,false);
});
test('higher frames confirm before visibility and end on the source invalidation candle',()=>{
    for(const source of ['4h','1d','1w']){
        const step=HTF[source],key=`bull_fvg_${source}_zones`,settings={[key]:{visible:true}};
        const rows=[bar(0,birth,{},step),bar(1,{}, {low:9,high:11,close:9},step)];
        assert.deepEqual(fvgSegments(rows,settings,{source,target:'1h',endTime:step/1000-1}),[]);
        const zones=fvgSegments(rows,settings,{source,target:'1h',endTime:2*step/1000});
        assert.equal(zones[0].start,step/1000);assert.equal(zones[0].end,(2*step-3600000)/1000);
        assert.deepEqual(fvgSegments(rows,settings,{source,target:source}),[]);
        assert.deepEqual(fvgSegments(rows,{},{source,target:'1m'}),[]);
    }
});
test('missing raw history truncates validity instead of bridging an unknown gap',()=>{
    const zones=fvgSegments([bar(0,birth),bar(3)],config,{target:'1m',endTime:180});
    assert.equal(zones[0].end,0);assert.equal(zones[0].truncated,true);
});
test('checkpoint seeds preserve older active gaps even when never nearest',()=>{
    const seeds=[{side:'bull',low:2,high:3,created:10,time:0,older:true},{side:'bull',low:4,high:5,created:20,time:0,older:true}];
    const zones=fvgSegments([bar(0),bar(1)],config,{target:'1m',endTime:60,seeds});
    assert.equal(zones.length,2);assert.ok(zones.every(z=>z.end===60));
});
test('no-border style is accepted for all zones but never as a line style',()=>{
    const styles=normalizeStyles({bull_fvg_zones:{style:3},support_zones:{style:3},rsi:{style:3},bull_fvg_4h_zones:{visible:true,style:3}});
    assert.equal(styles.bull_fvg_zones.style,3);assert.equal(styles.support_zones.style,3);
    assert.equal(styles.rsi.style,0);assert.equal(styles.bull_fvg_4h_zones.style,3);
});
