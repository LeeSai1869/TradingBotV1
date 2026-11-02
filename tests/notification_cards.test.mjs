import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {notificationView,TOAST_LIFETIME_MS} from '../Section_11_UI_UX/web_root/notification_view.js';
const event={symbol:'ENAUSDT',interval:'4h',bar_time:123000,created:123456,name:'SELL',details:{side:'SELL',price:.2375,confidence:88,upper:{low:.24,high:.25},lower:{low:.21,high:.22}}};
const view=notificationView(event);assert.match(view.lines[0],/88\/100/);assert.match(view.lines[1],/0\.25/);assert.match(view.lines[2],/0\.21/);assert.match(view.url,/at=123000/);assert.equal(TOAST_LIFETIME_MS,20000);
assert.ok(notificationView({...event,details:null}).lines.every(line=>line.includes('Unavailable')));
const listeners={},notices=[],opened=[],waits=[];
const self={location:{origin:'https://laptop.tailnet.ts.net'},addEventListener:(key,fn)=>listeners[key]=fn,
    registration:{showNotification:async(...args)=>notices.push(args)},clients:{matchAll:async()=>[],openWindow:async url=>opened.push(url)}};
vm.runInNewContext(fs.readFileSync(new URL('../Section_11_UI_UX/web_root/sw.js',import.meta.url),'utf8'),{self,URL,caches:{},fetch(){throw Error('unreachable');}});
listeners.push({data:{json:()=>({title:'ENA SELL',body:'Price 0.2375',data:{url:view.url}})},waitUntil:p=>waits.push(p)});await Promise.all(waits);assert.equal(notices.length,1);
let closed=false;listeners.notificationclick({notification:{close:()=>closed=true,data:{url:'https://evil.test/'}},waitUntil:p=>waits.push(p)});await Promise.all(waits);assert.ok(closed);assert.equal(opened[0],'https://laptop.tailnet.ts.net/web_root/mobile.html');
listeners.notificationclick({notification:{close(){},data:{url:view.url}},action:'dismiss',waitUntil(){throw Error('dismiss must not navigate');}});
let intercepted=false;listeners.fetch({request:{method:'GET',url:'https://laptop.tailnet.ts.net/api/alerts/events'},respondWith(){intercepted=true;}});assert.equal(intercepted,false);
