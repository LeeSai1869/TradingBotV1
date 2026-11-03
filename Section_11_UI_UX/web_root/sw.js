importScripts('/web_root/inbox_store.js');
const CACHE='trading-mobile-shell-v2';
const SHELL=['/web_root/mobile.html','/web_root/mobile.js','/web_root/inbox_store.js','/web_root/mobile.css','/web_root/notification_view.js','/web_root/icons/app-192.png','/web_root/icons/app-512.png'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('trading-mobile-shell-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
    const url=new URL(event.request.url);if(event.request.method!=='GET'||url.origin!==self.location.origin||!SHELL.includes(url.pathname))return;
    event.respondWith(fetch(event.request).catch(()=>caches.match(url.pathname))); // Never cache sessions, signal data or APIs.
});
self.addEventListener('push',event=>{
    let packet;try{packet=event.data.json();}catch{return;}
    if(typeof packet.title!=='string'||typeof packet.body!=='string')return;
    event.waitUntil((async()=>{
        const source=packet.data||{};let settings={notifications:true,sound:true};
        if(source.account&&source.event&&source.server&&self.InboxStore){await self.InboxStore.save(source.server,source.account,source.event);settings=await self.InboxStore.settings(source.server,source.account);}
        if(!settings.notifications)return;
        await self.registration.showNotification(packet.title.slice(0,300),{body:packet.body.slice(0,1000),tag:packet.tag,renotify:false,silent:packet.silent===true||!settings.sound,
            timestamp:packet.timestamp,icon:'/web_root/icons/app-192.png',badge:'/web_root/icons/app-192.png',data:packet.data,actions:[{action:'dismiss',title:'Dismiss'}]});
    })());
});
self.addEventListener('notificationclick',event=>{
    event.notification.close();if(event.action==='dismiss')return;
    let url;try{url=new URL(event.notification.data?.url||'/web_root/mobile.html',self.location.origin);if(url.origin!==self.location.origin||url.pathname!='/web_root/mobile.html')throw new Error();}catch{url=new URL('/web_root/mobile.html',self.location.origin);}
    event.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(async windows=>{
        if(windows.length){const client=await windows[0].navigate(url.href);if(client)return client.focus();}
        return self.clients.openWindow(url.href);
    }));
});
