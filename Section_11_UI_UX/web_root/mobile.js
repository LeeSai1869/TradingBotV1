import {notificationCard} from './notification_view.js';
import './inbox_store.js';
const cache=globalThis.InboxStore,$=id=>document.getElementById(id),status=$('mobile-status');
let account=null,cursor=null,timer,registration,config,installPrompt,polling=false,before=Number.MAX_SAFE_INTEGER;
const previous=[];
async function api(path,data){const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),15000);try{const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:controller.signal}:{cache:'no-store',signal:controller.signal});const packet=await response.json();if(!response.ok)throw new Error(packet.error||`Request failed (${response.status})`);return packet;}finally{clearTimeout(timeout);}}
function keyBytes(value){return Uint8Array.from(atob(value.replaceAll('-','+').replaceAll('_','/')+'='.repeat((-value.length+4)%4)),c=>c.charCodeAt(0));}
async function render(){if(!account)return;const rows=await cache.list(location.origin,account.username,before);$('mobile-events').replaceChildren();for(const event of rows)$('mobile-events').append(notificationCard(event,{navigate:false,dismissible:false}));$('mobile-older').disabled=rows.length===0;$('mobile-newer').disabled=previous.length===0;}
async function syncPage(){
    if(!account)return;
    try{const owner=account.username,packet=await api('/api/alerts/history?limit=50'+(before===Number.MAX_SAFE_INTEGER?'':`&before=${before}`));if(account?.username!==owner)return;
        for(const event of packet.history)await cache.save(location.origin,owner,event);
        if(cursor===null)cursor=packet.cursor;await render();status.textContent='History synchronized. Messages stay saved on this device.';
    }catch(error){await render();status.textContent='Showing saved messages. '+error.message;}
}
async function deviceSettings(){
    if(!account)return;const value=await cache.settings(location.origin,account.username,{notifications:$('mobile-notifications').checked,sound:$('mobile-sound').checked});
    const reg=registration?await registration:null,sub=await reg?.pushManager.getSubscription();
    if(sub)await api('/api/mobile/preferences',{endpoint:sub.endpoint,enabled:value.notifications,sound:value.sound});
}
async function signedIn(identity){
    account=identity;cursor=null;before=Number.MAX_SAFE_INTEGER;previous.length=0;$('mobile-login').hidden=true;$('mobile-account').hidden=false;$('mobile-user').textContent=`Signed in as ${identity.username}`;localStorage.setItem('mobile-last-account',identity.username);
    const settings=await cache.settings(location.origin,identity.username);$('mobile-notifications').checked=settings.notifications;$('mobile-sound').checked=settings.sound;
    await render();config=await api('/api/mobile/config');const webReady=config.web_ready??config.ready;$('mobile-setup').textContent=webReady?'Ready to connect this device.':config.reason+'. Laptop Web Push setup is needed for this web companion.';
    $('mobile-connect').disabled=!webReady||!('serviceWorker' in navigator)||!('PushManager' in window)||!('Notification' in window);
    if('serviceWorker' in navigator&&window.isSecureContext)registration=navigator.serviceWorker.register('/sw.js',{scope:'/'}).catch(error=>{status.textContent=error.message;return null;});
    const target=Number(new URLSearchParams(location.search).get('seq'));if(Number.isSafeInteger(target)&&target>0)before=target+1;
    await syncPage();void poll();
}
async function poll(){
    if(!account||polling)return;polling=true;const owner=account.username;
    try{const packet=await api('/api/alerts/events'+(cursor===null?'':`?after=${cursor}`));if(account?.username!==owner)return;
        for(const event of [...(packet.history||[]),...packet.events])await cache.save(location.origin,owner,event);
        cursor=packet.cursor;await render();
    }catch(error){status.textContent='Offline history remains available. '+error.message;}
    finally{polling=false;clearTimeout(timer);if(account)timer=setTimeout(poll,5000);}
}
$('mobile-login').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget;try{const identity=await api('/api/login',{username:form.elements.username.value,password:form.elements.password.value,remember:form.elements.remember.checked});form.elements.password.value='';await signedIn(identity);}catch(error){status.textContent=error.message;}};
$('mobile-notifications').onchange=$('mobile-sound').onchange=()=>void deviceSettings().catch(error=>status.textContent='Saved on this device; laptop update pending. '+error.message);
$('mobile-older').onclick=async()=>{const rows=await cache.list(location.origin,account.username,before);if(!rows.length)return;previous.push(before);before=rows.at(-1).seq;await syncPage();};
$('mobile-newer').onclick=async()=>{if(previous.length){before=previous.pop();await render();}};
$('mobile-refresh').onclick=async()=>{before=Number.MAX_SAFE_INTEGER;previous.length=0;await syncPage();};
$('mobile-connect').onclick=async()=>{
    try{if(!(config?.web_ready??config?.ready))throw new Error(config?.reason||'Laptop push is not configured');const permission=await Notification.requestPermission();if(permission!=='granted')throw new Error('Allow notifications in device settings. On iPhone, install to Home Screen first.');
        const reg=await registration||await navigator.serviceWorker.register('/sw.js',{scope:'/'});await navigator.serviceWorker.ready;
        const subscription=await reg.pushManager.getSubscription()||await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:keyBytes(config.public_key)});
        await api('/api/mobile/subscribe',{subscription:subscription.toJSON()});await deviceSettings();$('mobile-test').disabled=false;status.textContent='Push connected. New notifications can arrive while the app is closed.';
    }catch(error){status.textContent=error.message;}
};
$('mobile-test').onclick=async()=>{try{const reg=await registration,sub=await reg?.pushManager.getSubscription();if(!sub)throw new Error('Connect this device first.');await api('/api/mobile/test',{endpoint:sub.endpoint});status.textContent='Test submitted. Check device notifications.';}catch(error){status.textContent=error.message;}};
$('mobile-logout').onclick=async()=>{
    try{const reg='serviceWorker' in navigator?await navigator.serviceWorker.getRegistration('/'):null,sub=await reg?.pushManager.getSubscription();if(sub){await api('/api/mobile/unsubscribe',{endpoint:sub.endpoint});await sub.unsubscribe();}
        if(reg)for(const notice of await reg.getNotifications())notice.close();await api('/api/logout',{});account=null;clearTimeout(timer);localStorage.removeItem('mobile-last-account');$('mobile-events').replaceChildren();$('mobile-account').hidden=true;$('mobile-login').hidden=false;status.textContent='Signed out. This device is disconnected from push.';
    }catch(error){status.textContent='Could not disconnect: '+error.message;}
};
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;$('mobile-install').hidden=false;});$('mobile-install').onclick=async()=>{await installPrompt?.prompt();$('mobile-install').hidden=true;};
try{const identity=await api('/api/session');if(identity.role==='guest'){$('mobile-login').hidden=false;status.textContent='Sign in to your notification inbox.';}else await signedIn(identity);}catch(error){const owner=localStorage.getItem('mobile-last-account');if(owner){account={username:owner};$('mobile-account').hidden=false;$('mobile-user').textContent=`Saved inbox · ${owner}`;const settings=await cache.settings(location.origin,owner);$('mobile-notifications').checked=settings.notifications;$('mobile-sound').checked=settings.sound;await render();}else $('mobile-login').hidden=false;status.textContent='Offline. Saved messages are available; reconnect to synchronize.';}
