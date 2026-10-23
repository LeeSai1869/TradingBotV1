import test from 'node:test';
import assert from 'node:assert/strict';
import {FEATURE_STYLES,normalizeStyles} from '../Section_11_UI_UX/controls/settings/feature_styles.js';
import {histogramRows} from '../Section_11_UI_UX/overlays/volume_profile/index.js';
import {segments} from '../Section_11_UI_UX/overlays/zones/index.js';

test('Volume Profile offers independent levels and a styled value-area band',()=>{
    const keys=FEATURE_STYLES['Volume Profile'].outputs.map(([key])=>key);
    assert.deepEqual(keys,['vp_poc','vp_va_high','vp_va_low','vp_histogram','vp_hvn_nodes','vp_lvn_nodes','vp_value_area']);
    const styles=normalizeStyles({vp_poc:{visible:true,color:'#123456',width:3,style:2},vp_value_area:{visible:true,opacity:37}});
    assert.deepEqual(styles.vp_poc,{visible:true,color:'#123456',width:3,style:2});
    assert.equal(styles.vp_value_area.opacity,37);assert.equal(styles.vp_va_high.visible,false);
    assert.equal(normalizeStyles({support_zones:{opacity:120}}).support_zones.opacity,100);
    assert.equal(normalizeStyles().support_zones.opacity,20);
    assert.equal(normalizeStyles({vp_hvn_low:{visible:true}}).vp_hvn_nodes.visible,true);
});

test('S/R bands retain both bounds and do not invent a range from a single price',()=>{
    const bars=[{time:1,features:{nearest_support:99}},
        {time:2,features:{support_zone_low:97,support_zone_high:99,nearest_support_zone_id:'s'}},
        {time:3,features:{support_zone_low:97,support_zone_high:99,nearest_support_zone_id:'s'}},
        {time:4,features:{support_zone_low:null,support_zone_high:99,nearest_support:99}},
        {time:5,features:{support_zone_low:99,support_zone_high:99}}];
    const bands=segments(bars,{support_zones:{visible:true}});
    assert.deepEqual(bands,[{key:'support_zones',identity:'s',low:97,high:99,start:2,end:3}]);
    assert.deepEqual(segments(bars,{support_zones:{visible:false}}),[]);
});

test('histogram widths reflect actual volume and node toggles retain separate bins',()=>{
    const profile={status:'ready',bins:[{low:0,high:1,volume:10,node:'low'},{low:1,high:2,volume:40,node:'high'},{low:2,high:3,volume:20,node:'normal'}]};
    const styles=normalizeStyles({vp_histogram:{visible:true},vp_hvn_nodes:{visible:true},vp_lvn_nodes:{visible:true}});
    assert.deepEqual(histogramRows(profile,styles).map(b=>[b.key,b.fraction]),[['vp_lvn_nodes',.25],['vp_hvn_nodes',1],['vp_histogram',.5]]);
    styles.vp_histogram.visible=false;
    assert.equal(histogramRows(profile,styles).length,2);
    assert.deepEqual(histogramRows({status:'waiting',bins:[]},styles),[]);
});
