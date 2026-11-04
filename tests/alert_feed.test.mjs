import assert from 'node:assert/strict';
import {createAlertFeed,watchAlertFeed} from '../Section_11_UI_UX/controls/alerts/feed.js';
const flush=async()=>{for(let i=0;i<10;i++)await Promise.resolve();};
function fixture(){
    let seq=10,fail=false,hold=null;const timers=new Map(),requests=[],events=[],history=[],errors=[];let id=0;
    const feed=createAlertFeed({request:async path=>{requests.push(path);if(hold)await hold;if(fail)throw Error('offline');return path.includes('after=')?{cursor:seq,events:seq>Number(path.split('=')[1])?[{seq}]:[]}:{cursor:seq,events:[],history:[{seq:9}]};},
        onEvent:e=>events.push(e.seq),onHistory:rows=>history.push(...rows.map(e=>e.seq)),onState:e=>errors.push(e?.message),
        schedule:fn=>{timers.set(++id,fn);return id;},cancel:key=>timers.delete(key)});
    return {feed,requests,events,history,errors,timers,setSeq:n=>seq=n,setFail:v=>fail=v,setHold:p=>hold=p,
        tick:async()=>{const [key,fn]=timers.entries().next().value;timers.delete(key);await fn();}};
}
{
    const f=fixture();f.feed.start();await flush();assert.deepEqual(f.history,[9]);assert.deepEqual(f.events,[]);
    f.setSeq(11);await f.tick();assert.deepEqual(f.events,[11]);assert.equal(f.requests.at(-1),'/api/alerts/events?after=10');
    await f.tick();assert.deepEqual(f.events,[11]);
    f.setFail(true);await f.tick();assert.equal(f.errors.at(-1),'offline');
    f.setSeq(12);f.setFail(false);f.feed.wake();await flush();assert.deepEqual(f.events,[11,12]);
    f.feed.pause();assert.equal(f.timers.size,0);f.setSeq(13);f.feed.start();await flush();assert.deepEqual(f.events,[11,12,13]);
    assert.equal(f.history.length,1);f.feed.pause();
}
{
    const f=fixture();let release;f.setHold(new Promise(resolve=>release=resolve));f.feed.start();f.feed.wake();f.feed.pause();release();await flush();
    assert.equal(f.timers.size,0);assert.equal(f.requests.length,1);
    f.setHold(null);f.setSeq(11);f.feed.start();await flush();assert.deepEqual(f.events,[11]);f.feed.pause();
}
{
    const f=fixture(),win=new EventTarget(),doc=new EventTarget();doc.visibilityState='visible';
    const stop=watchAlertFeed(f.feed,win,doc);await flush();
    win.dispatchEvent(new Event('pagehide'));assert.equal(f.timers.size,0);
    f.setSeq(11);win.dispatchEvent(new Event('pageshow'));await flush();assert.deepEqual(f.events,[11]);
    f.setSeq(12);doc.dispatchEvent(new Event('visibilitychange'));await flush();assert.deepEqual(f.events,[11,12]);
    f.setSeq(13);win.dispatchEvent(new Event('online'));await flush();assert.deepEqual(f.events,[11,12,13]);
    stop();win.dispatchEvent(new Event('focus'));await flush();assert.equal(f.timers.size,0);
}
console.log('PASS live delivery, retries, cursor preservation, suspension/restore and deduplication');
