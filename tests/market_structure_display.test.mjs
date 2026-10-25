import test from 'node:test';
import assert from 'node:assert/strict';
import {structureSegments} from '../Section_11_UI_UX/overlays/zones/structure.js';
test('structure display uses stored range and ends when establishment disappears',()=>{
    const f={current_structure:'STRUCTURE_RANGE',structure_range_low:10,structure_range_high:12,structure_origin_bar:2};
    const bars=[{time:1,features:f},{time:2,features:f},{time:3,features:{}}];
    const [z]=structureSegments(bars,{structure_range_zones:{visible:true}});
    assert.deepEqual([z.start,z.end,z.low,z.high],[1,2,10,12]);
    assert.deepEqual(structureSegments(bars,{}),[]);
});
