import test from 'node:test';
import assert from 'node:assert/strict';
import {hudRequest} from '../Section_11_UI_UX/controls/workspace/requests.js';

test('a hanging HUD request times out and a subsequent retry can succeed',async()=>{
    const original=globalThis.fetch;
    try {
        globalThis.fetch=(_,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError'))));
        await assert.rejects(hudRequest('/api/hud/catalog',{timeoutMs:20}),/did not respond/);
        globalThis.fetch=async()=>({ok:true,json:async()=>({fields:{}})});
        assert.deepEqual(await hudRequest('/api/hud/catalog'),{fields:{}});
    } finally {globalThis.fetch=original;}
});
test('busy responses and disconnected servers give actionable HUD errors',async()=>{
    const original=globalThis.fetch;
    try {
        globalThis.fetch=async()=>({ok:false,json:async()=>({error:'Market data is busy. Retry shortly.'})});
        await assert.rejects(hudRequest('/api/hud'),/busy/);
        globalThis.fetch=async()=>{throw new TypeError('Load failed');};
        await assert.rejects(hudRequest('/api/hud'),/restart_ui.py/);
    } finally {globalThis.fetch=original;}
});
