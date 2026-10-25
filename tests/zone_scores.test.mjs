import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeStyles} from '../Section_11_UI_UX/controls/settings/feature_styles.js';
import {zoneScoreLabel} from '../Section_11_UI_UX/overlays/zones/index.js';
import {srSegments} from '../Section_11_UI_UX/overlays/zones/sr.js';
import {fvgSegments} from '../Section_11_UI_UX/overlays/zones/fvg.js';
test('zone score toggles default on and preserve explicit off for ordinary and higher frames',()=>{
    const styles=normalizeStyles({support_zones:{scores:false},bull_fvg_4h_zones:{scores:false}});
    assert.equal(styles.support_zones.scores,false);assert.equal(styles.bull_fvg_4h_zones.scores,false);
    assert.equal(styles.resistance_zones.scores,true);assert.equal(styles.bear_fvg_zones.scores,true);
    assert.equal(styles.ema50.scores,undefined);
});
test('score labels identify the metric and never invent zero for missing scores',()=>{
    assert.equal(zoneScoreLabel({key:'bull_fvg_zones',score:0}),'FVG reaction: 0.00');
    assert.equal(zoneScoreLabel({key:'support_zones',score:12.345}),'S/R score: 12.35');
    assert.equal(zoneScoreLabel({key:'support_zones'}),'S/R score: unavailable');
});
test('all active SR scores attach by stable identity without changing lifecycle geometry',()=>{
    const zone={side:'support',low:10,high:12,institutional:false};
    const bars=[{time:60,features:{sr_zone_events:JSON.stringify([{id:'s1',...zone,before:null}])}}];
    const [item]=srSegments(bars,{support_zones:{visible:true}},{through:60,zones:{s1:{...zone,score:25,score_time:60}}});
    assert.equal(item.score,25);assert.equal(item.scoreTime,60);assert.deepEqual(item.history,[{time:60,low:10,high:12}]);
});
test('FVG checkpoint scores enrich existing gaps rather than duplicate them',()=>{
    const bars=[{time:0,client:{open_time:0,close_time:59999,low:14,high:16,close:15},features:{qualified_bull_fvg:true,bull_fvg_low:10,bull_fvg_high:12}}];
    const zones=fvgSegments(bars,{bull_fvg_zones:{visible:true}},{target:'1m',seeds:[{side:'bull',low:10,high:12,time:0,score:9,score_time:0}]});
    assert.equal(zones.length,1);assert.equal(zones[0].score,9);
});
test('MTF options display on their own source charts without duplicate generic gaps',()=>{
    for(const target of ['4h','1d','1w']){
        const key=`bull_fvg_${target}_zones`,bars=[{time:0,client:{low:14,high:16,close:15,open_time:0,close_time:59999},features:{qualified_bull_fvg:true,bull_fvg_low:10,bull_fvg_high:12}}];
        const zones=fvgSegments(bars,{[key]:{visible:true},bull_fvg_zones:{visible:true}},{target});
        assert.equal(zones.length,1);assert.equal(zones[0].key,key);
    }
});
