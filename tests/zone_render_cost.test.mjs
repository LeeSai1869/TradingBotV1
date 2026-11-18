import test from 'node:test';
import assert from 'node:assert/strict';
import {segments} from '../Section_11_UI_UX/overlays/zones/index.js';
import {srSegments,srRole} from '../Section_11_UI_UX/overlays/zones/sr.js';

test('hidden SR and OB never parse their historical event blobs',()=>{
    const features={};
    Object.defineProperty(features,'sr_zone_events',{get(){throw Error('hidden SR parsed');}});
    Object.defineProperty(features,'ob_zone_events',{get(){throw Error('hidden OB parsed');}});
    const rows=[{time:60,features,client:{close_time:119999,close:100,low:99,high:101}}];
    assert.deepEqual(segments(rows,{}),[]);
});

test('role classification visits only candles during the segment lifetime',()=>{
    let reads=0;
    const bars=Array.from({length:10000},(_,i)=>({time:i, get client(){reads++;return {close:i%3+9};}}));
    const role=srRole({key:'support_zones',start:5000,end:5001,low:10,high:12},bars);
    assert.equal(role,'both');
    assert.ok(reads<=2,`visited ${reads} candles for a two-bar zone`);
});

test('long lifecycle histories keep every unpromoted segment',()=>{
    const rows=Array.from({length:4000},(_,i)=>({time:i*60,client:{open_time:i*60000,close_time:(i+1)*60000-1,close:100},
        features:{sr_zone_events:JSON.stringify([
            ...(i?[{id:String(i-1),removed:true}]:[]),
            {id:String(i),side:'support',low:90,high:95,institutional:false,before:null}
        ])}}));
    const zones=srSegments(rows,{support_zones:{visible:true}});
    assert.equal(zones.length,4000);
    assert.equal(zones[0].invalidated,true);
    assert.equal(zones.at(-1).identity,'support_zones:3999');
});
