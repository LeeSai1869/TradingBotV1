import test from 'node:test';
import assert from 'node:assert/strict';
import {institutionalProjection,srRole} from '../Section_11_UI_UX/overlays/zones/sr.js';
import {normalizeStyles} from '../Section_11_UI_UX/controls/settings/feature_styles.js';
const config=normalizeStyles({inst_support_zones:{visible:true}});
const rows=[{time:60,client:{close:15,close_time:119999}},{time:120,client:{close:8,close_time:179999}}];
const frame={through:0,valid_until:60,current:true,status:'ready',zones:{a:{institutional:true,side:'support',origin_time:0,low:10,high:12,score:56}}};
test('higher institution extends from source origin to latest lower bar without changing score',()=>{
    const [z]=institutionalProjection(rows,config,frame,'4h');
    assert.equal(z.start,0);assert.equal(z.end,120);assert.equal(z.source,'4h');assert.equal(z.score,56);
    assert.equal(srRole(z,rows),'both');
});
test('projection respects opt out, pending repair, missing origins, and behind checkpoints',()=>{
    assert.deepEqual(institutionalProjection(rows,normalizeStyles({inst_support_zones:{visible:true,higher:false}}),frame,'4h'),[]);
    assert.deepEqual(institutionalProjection(rows,config,{...frame,status:'feature repair pending'},'4h'),[]);
    assert.deepEqual(institutionalProjection(rows,config,{...frame,zones:{a:{...frame.zones.a,origin_time:null}}},'4h'),[]);
    assert.equal(institutionalProjection(rows,config,{...frame,current:false},'4h')[0].end,60);
});
test('roles use closed price and the bounds valid at that time',()=>{
    const z={key:'support_zones',start:0,end:120,low:10,high:12,history:[{time:0,low:10,high:12}]};
    assert.equal(srRole(z,[rows[0]]),'support');
    assert.equal(srRole(z,[rows[0],{...rows[1],provisional:true}]),'support');
    assert.equal(srRole({...z,end:60},rows),'support');
    assert.equal(srRole({...z,key:'resistance_zones'},[rows[1]]),'resistance');
});
