import {notificationCard} from './notification_view.js';
const $=id=>document.getElementById(id),status=$('mobile-status');let account=null,cursor=null,timer,registration,config,installPrompt;
async function api(path,data){const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{cache:'no-store'});const packet=await response.json();if(!response.ok)throw new Error(packet.error||`Request failed (${response.status})`);return packet;}
function keyBytes(value){return Uint8Array.from(atob(value.replaceAll('-','+').replaceAll('_','/')+'='.repeat((-value.length+4)%4)),c=>c.charCodeAt(0));}
async function signedIn(identity){
    account=identity;cursor=null;$('mobile-events').replaceChildren();$('mobile-login').hidden=true;$('mobile-account').hidden=false;$('mobile-user').textContent=`Signed in as ${identity.username}`;
    config=await api('/api/mobile/config');$('mobile-setup').textContent=config.ready?'Ready to connect this device.':config.reason+'. Server setup is required before phone push can work.';
    $('mobile-connect').disabled=!config.ready||!('serviceWorker' in navigator)||!('PushManager' in window)||!('Notification' in window);
    if('serviceWorker' in navigator&&window.isSecureContext)registration=navigator.serviceWorker.register('/sw.js',{scope:'/'});
    status.textContent='Connected. Push requires enabling this device.';void poll();
}
async function poll(){
    if(!account)return;
    const owner=account.username;
    try{const packet=await api('/api/alerts/events'+(cursor===null?'':`?after=${cursor}`));
        if(account?.username!==owner)return;
        for(const event of [...(packet.history||[]),...packet.events]){
            const card=notificationCard(event);$('mobile-events').prepend(card);
        }
        while($('mobile-events').children.length>20)$('mobile-events').lastElementChild.remove();cursor=packet.cursor;
    }catch(error){status.textContent=error.message;}
    clearTimeout(timer);timer=setTimeout(poll,5000);
}
$('mobile-login').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget;try{const identity=await api('/api/login',{username:form.elements.username.value,password:form.elements.password.value,remember:form.elements.remember.checked});form.elements.password.value='';await signedIn(identity);}catch(error){status.textContent=error.message;}};
$('mobile-connect').onclick=async()=>{
    try{if(!config?.ready)throw new Error(config?.reason||'Server push is not configured');
        // Permission is requested directly from the user click, before other work.
        const permission=await Notification.requestPermission();if(permission!=='granted')throw new Error('Allow notifications in your browser/device settings. On iPhone, install to Home Screen first.');
        const reg=await registration||await navigator.serviceWorker.register('/sw.js',{scope:'/'});await navigator.serviceWorker.ready;
        const subscription=await reg.pushManager.getSubscription()||await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:keyBytes(config.public_key)});
        await api('/api/mobile/subscribe',{subscription:subscription.toJSON()});$('mobile-test').disabled=false;status.textContent='Mobile push connected. Notifications can arrive while this app is closed.';
    }catch(error){status.textContent=error.message;}
};
$('mobile-test').onclick=async()=>{try{const reg=await registration,sub=await reg?.pushManager.getSubscription();if(!sub)throw new Error('Enable mobile notifications on this device first.');await api('/api/mobile/test',{endpoint:sub.endpoint});status.textContent='Test submitted to the push service. Check your device notifications.';}catch(error){status.textContent=error.message;}};
$('mobile-logout').onclick=async()=>{
    try{const reg='serviceWorker' in navigator?await navigator.serviceWorker.getRegistration('/'):null;
        const sub=await reg?.pushManager.getSubscription();if(sub){await api('/api/mobile/unsubscribe',{endpoint:sub.endpoint});await sub.unsubscribe();}
        if(reg)for(const notice of await reg.getNotifications())notice.close();
        await api('/api/logout',{});account=null;clearTimeout(timer);$('mobile-events').replaceChildren();$('mobile-account').hidden=true;$('mobile-login').hidden=false;status.textContent='Signed out. This device has been disconnected from push.';
    }catch(error){status.textContent='Could not disconnect push: '+error.message;}
};
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;$('mobile-install').hidden=false;});
$('mobile-install').onclick=async()=>{await installPrompt?.prompt();$('mobile-install').hidden=true;};
try{const identity=await api('/api/session');if(identity.role==='guest'){$('mobile-login').hidden=false;status.textContent='Sign in to view your signals.';}else await signedIn(identity);}catch(error){status.textContent=error.message;$('mobile-login').hidden=false;}
