// Alert configuration is per account; evaluation happens in the local backend.
import {notificationCard,notificationView,TOAST_LIFETIME_MS} from '../../web_root/notification_view.js';
import {formatValue} from '../../web_root/value_format.js';
export const name = 'alerts';
let editor, editorTitle, editorStatus, form, activity, status, catalog, audio, volume=0.35, eventCursor=null;
let signalPrefs=null, deliveryButton, notificationPanel, newButton;
const customBuffers=new Map();
let customLibrary=[];
let soundEnabled=true;
const playingSources=new Set();
function soundPreference(){try{localStorage.setItem(`alerts.enabled.${window.AppSession.username}`,String(soundEnabled));}catch{}}
let mobileConfigPromise;
function mobileConfig(){return mobileConfigPromise??=request('/api/mobile/config').catch(error=>{mobileConfigPromise=null;throw error;});}
let polling=false, timer, editing=null, saving=false;
const recent=[];
const soundQueue=[];let soundBusy=false;
function el(tag,text,parent,className) {
    const node=document.createElement(tag);if(text)node.textContent=text;
    if(parent)parent.append(node);if(className)node.className=className;return node;
}
async function request(path,data) {
    const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),15000);
    try {
        const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:controller.signal}:{cache:'no-store',signal:controller.signal});
        const packet=await response.json();if(!response.ok)throw new Error(packet.error||`Alert API: ${response.status}`);return packet;
    } catch(error) {
        if(error.name==='AbortError')throw new Error('Alert request timed out. Check Saved alerts before retrying.');
        throw error;
    } finally {clearTimeout(timeout);}
}
function select(label,key,options,parent) {
    const row=el('label',label,parent), input=el('select','',row);input.name=key;input.setAttribute('aria-label',label);
    for(const [value,title] of options) {const option=el('option',title,input);option.value=value;}
    return input;
}
function input(label,key,type,parent) {
    const row=el('label',label,parent), field=el('input','',row);field.name=key;field.type=type;return field;
}
async function unlock() {
    const Audio=window.AudioContext||window.webkitAudioContext;
    if(!Audio)throw new Error('Sound is not supported by this browser.');
    if(!audio){audio=new Audio();audio.onstatechange=updateDeliveryStatus;}await audio.resume();
    updateDeliveryStatus();
    if(audio.state!=='running')throw new Error('Click Enable sound again to allow audio.');
}
function sound(key) {
    if(key==='none'||!audio||audio.state!=='running')return;
    const notes={chime:[880,1174,1320],bell:[660,990],alarm:[880,440,880,440]}[key]||[];
    notes.forEach((hz,i)=>{
        const oscillator=audio.createOscillator(), gain=audio.createGain(), t=audio.currentTime+i*.22;
        oscillator.type=key==='alarm'?'square':'sine';oscillator.frequency.value=hz;
        gain.gain.setValueAtTime(0,t);gain.gain.linearRampToValueAtTime(volume*.4,t+.015);gain.gain.exponentialRampToValueAtTime(.0001,t+.3);
        oscillator.connect(gain);gain.connect(audio.destination);playingSources.add(oscillator);oscillator.onended=()=>playingSources.delete(oscillator);oscillator.start(t);oscillator.stop(t+.32);
    });
}
function enqueueSound(key){
    if(!soundEnabled||key==='none')return;
    if(audio?.state!=='running'){updateDeliveryStatus();return;}
    if(soundQueue.length<20)soundQueue.push(key);
    async function next(){
        if(soundBusy||!soundQueue.length)return;soundBusy=true;
        let duration=1.1;try{duration=await play(soundQueue.shift(),true);}catch(error){if(status?.isConnected)status.textContent=error.message;}
        setTimeout(()=>{soundBusy=false;void next();},Math.max(100,duration*1000+50));
    }
    void next();
}
function renderActivity() {
    if(!activity)return;
    activity.replaceChildren();
    if(!recent.length)el('p','No alerts triggered yet.',activity,'settings-note');
    for(const event of recent.slice(-10).reverse()){
        const row=el('div','',activity,'alert-rule');
        const link=el('a',`${event.name} · ${event.symbol} ${event.interval}`,row);link.href=notificationView(event).url;link.onclick=click=>{if(click.ctrlKey||click.metaKey)return;click.preventDefault();openEventChart(event);};
        el('span',` · ${new Date(event.created).toLocaleTimeString()}`,row);
        const detail=el('details','',row);el('summary','Details',detail);el('p',event.message,detail);
        el('p',`Candle: ${new Date(event.bar_time).toLocaleString()}`,detail);
    }
}
function openEventChart(event){window.focus();if(window.openAlertChart)void window.openAlertChart(event).catch(error=>{const target=document.getElementById('status');if(target)target.textContent=error.message;});else window.location.assign(notificationView(event).url);}
function receive(event,deliver=true) {
    if(recent.some(row=>row.seq===event.seq))return;
    recent.push(event);if(recent.length>100)recent.shift();renderActivity();
    if(!deliver)return;
    const view=notificationView(event);
    const open=()=>openEventChart(event);
    if(event.app!==false){
        document.getElementById('alert-toasts').append(notificationCard(event,{open,ephemeral:true}));
        while(document.querySelectorAll('#alert-toasts .alert-toast').length>5)document.querySelector('#alert-toasts .alert-toast').remove();
    }
    enqueueSound(event.sound);
    if(event.notify&&'Notification' in window&&Notification.permission==='granted') {
        try {const notice=new Notification(view.title,{body:view.lines.join('\n'),tag:`stored-alert-${event.seq}`});notice.onclick=()=>{notice.close?.();open();};setTimeout(()=>notice.close?.(),TOAST_LIFETIME_MS);}catch{ /* In-app activity remains available. */ }
    }
}

async function poll() {
    if(polling)return;polling=true;
    try {
        const packet=await request('/api/alerts/events'+(eventCursor===null?'':`?after=${eventCursor}`));
        if(eventCursor===null)for(const event of packet.history||[])receive(event,false);
        for(const event of packet.events)receive(event);
        eventCursor=packet.cursor;
        updateDeliveryStatus();
    } catch(error) {if(status?.isConnected)status.textContent=error.message;}
    finally {polling=false;timer=setTimeout(poll,2000);}
}
async function refresh(){if(notificationPanel?.marker.isConnected)await renderNotificationSettings(notificationPanel.parent);}
function syncMode() {
    const decision=form.elements.field.value.startsWith('decision.');
    for(const key of ['operator','value','target_field','mode'])form.elements[key].parentElement.hidden=decision;
    if(decision){form.elements.operator.value='equals';form.elements.value.value='1';form.elements.target_field.value='';}
    const features=[form.elements.field.value,form.elements.target_field.value].some(field=>field && !(catalog.live_fields || ['client.high','client.low','client.close']).includes(field));
    form.elements.mode.querySelector('[value="live"]').disabled=features;
    if(features)form.elements.mode.value='closed';
}
function fill(rule) {
    editing=rule.id||null;
    for(const [key,value] of Object.entries(rule)) {
        const field=form.elements.namedItem(key);if(!field)continue;
        if(field.type==='checkbox')field.checked=value;else field.value=value??'';
    }
    syncMode();
    form.querySelector('button[type=submit]').textContent=editing?'Save changes':'Create alert';

}
function reset() {
    form.reset();editing=null;
    form.elements.symbol.value=document.getElementById('symbol').value;
    form.elements.interval.value=document.getElementById('interval').value;
    form.elements.field.value='client.close';form.elements.sound.value='none';
    form.elements.enabled.checked=true;form.elements.notify.checked=true;
    form.elements.repeat.value='per_bar';form.elements.value.value='0';form.elements.mode.value='live';syncMode();
    form.querySelector('button[type=submit]').textContent='Create alert';
}
async function build() {
    if(form)return;
    catalog=await request('/api/alerts/catalog');
    editor=el('dialog','',document.body,'alerts-dialog alert-editor');editor.setAttribute('aria-labelledby','alert-editor-title');
    const header=el('header','',editor);editorTitle=el('h2','Create alert',header);editorTitle.id='alert-editor-title';
    const close=el('button','Close alert editor',header);close.onclick=()=>{if(!saving)editor.close();};
    editor.addEventListener('cancel',event=>{if(saving)event.preventDefault();});
    editor.addEventListener('close',()=>{if(!saving)reset();newButton?.focus();});
    editorStatus=el('p','',editor,'settings-note');editorStatus.setAttribute('role','status');
    form=el('form','',editor,'alert-form');
    const title=input('Alert name','name','text',form);title.required=true;title.maxLength=120;
    select('Coin','symbol',catalog.symbols.map(value=>[value,value]),form);
    select('Timeframe','interval',catalog.intervals.map(value=>[value,value]),form);
    select('Evaluation','mode',[['live','Live candle / provisional EMA / RSI'],['closed','Closed candle / stored features']],form);
    const search=input('Search fields','field_search','search',form);
    const fields=select('Field','field',Object.entries(catalog.fields),form);fields.onchange=syncMode;
    search.oninput=()=>{const selected=fields.value,query=search.value.toLowerCase();fields.replaceChildren();for(const [key,label] of Object.entries(catalog.fields)){if(key===selected||`${key} ${label}`.toLowerCase().includes(query)){const option=el('option',label,fields);option.value=key;}}fields.value=selected;};
    const presets=el('div','',form,'settings-coin-actions');
    for(const side of ['buy','sell']){const button=el('button',`${side.toUpperCase()} signal`,presets);button.type='button';button.onclick=()=>{search.value='';search.oninput();form.elements.field.value='decision.'+side;form.elements.operator.value='equals';form.elements.value.value='1';form.elements.target_field.value='';form.elements.name.value=`${side.toUpperCase()} ${form.elements.symbol.value}`;form.elements.repeat.value='per_bar';syncMode();};}
    select('Condition','operator',catalog.operators.map(value=>[value,value.replaceAll('_',' ')]),form);
    const threshold=input('Threshold (signed numbers allowed)','value','number',form);threshold.step='any';threshold.required=true;
    select('Or compare with field','target_field',[['','Use numeric threshold'],...Object.entries(catalog.fields)],form).onchange=syncMode;
    select('Frequency','repeat',[['once','Once, then pause'],['per_bar','Once per matching candle']],form);
    const tone=input('Sound','sound','hidden',form);tone.value='none';
    input('System notification','notify','checkbox',form);
    input('Alert enabled','enabled','checkbox',form);
    const save=el('button','Create alert',form);save.type='submit';
    const cancel=el('button','Cancel',form);cancel.type='button';cancel.onclick=()=>{if(!saving)editor.close();};
    form.onsubmit=async event=>{
        event.preventDefault();if(saving)return;saving=true;save.disabled=true;close.disabled=true;cancel.disabled=true;
        editorStatus.textContent='Saving alert…';
        let completed=false;
        try{
            const packet=Object.fromEntries(new FormData(form));delete packet.field_search;packet.value=Number(packet.value);packet.notify=form.elements.notify.checked;packet.enabled=form.elements.enabled.checked;if(editing)packet.id=editing;
            await request('/api/alerts',packet);
            completed=true;editor.close();reset();status.textContent='Alert saved. Watching the selected evaluation mode.';
        }catch(error){editorStatus.textContent=error.message;}finally{saving=false;save.disabled=false;close.disabled=false;cancel.disabled=false;}
        if(completed)void refresh().catch(error=>{status.textContent='Alert saved. Could not refresh the list: '+error.message;});
    };
    reset();
}
export function mount() {
    try {const stored=Number(localStorage.getItem(`alerts.volume.${window.AppSession.username}`));if(Number.isFinite(stored)&&stored>=0&&stored<=1&&localStorage.getItem(`alerts.volume.${window.AppSession.username}`)!==null)volume=stored;}catch{}
    try{soundEnabled=localStorage.getItem(`alerts.enabled.${window.AppSession.username}`)!=='false';}catch{}
    const resumeOnGesture=()=>{if(soundEnabled&&audio?.state!=='running')void unlock().catch(()=>{});};
    document.addEventListener('pointerdown',resumeOnGesture,{capture:true});
    document.addEventListener('keydown',resumeOnGesture,{capture:true});
    const toolbar=document.getElementById('toolbar'), open=el('button','Notifications',toolbar);open.id='alerts-button';
    const gear=document.getElementById('settings-button');if(gear)gear.before(open);
    el('div','',document.body).id='alert-toasts';
    open.disabled=true;
    open.onclick=async()=>{open.disabled=true;try{const prefs=await getSignalPreferences();await saveSignalPreferences({notify:!prefs.notify});}catch(error){open.title=error.message;}finally{open.disabled=false;}};
    // Polling is independent of chart symbol/viewport; no historical dataset fetches.
    // Initialize the event cursor without replaying old sounds on every reopen.
    request('/api/alerts/events').then(packet=>{eventCursor=packet.cursor;for(const event of packet.history||[])recent.push(event);renderActivity();timer=setTimeout(poll,2000);}).catch(()=>{timer=setTimeout(poll,5000);});
    deliveryButton=open;
    void getSignalPreferences().then(updateDeliveryStatus).catch(error=>{open.title=error.message;}).finally(()=>{open.disabled=false;});
    window.addEventListener('pagehide',()=>clearTimeout(timer),{once:true});
}

function updateDeliveryStatus(){
    if(!deliveryButton)return;
    const ready=audio?.state==='running';
    deliveryButton.textContent=`Notifications: ${signalPrefs?.notify?'on':'off'}`;
    deliveryButton.setAttribute('aria-label','Toggle desktop notifications');deliveryButton.setAttribute('aria-pressed',String(signalPrefs?.notify===true));
    for(const node of document.querySelectorAll('[data-delivery-status]'))node.textContent=node.dataset.audio==='true'?`Sound: ${!soundEnabled?'off':ready?(volume===0?'volume is 0':'ready'):'blocked — click Enable sound or interact with the app'}`:`Desktop permission: ${globalThis.Notification?.permission||'unavailable'}`;
    deliveryButton.title=`Desktop notification toggle; configure rules in Settings → Notifications. Automatic monitoring: ${signalPrefs?.enabled?'on':'off'} · Notifications: ${globalThis.Notification?.permission||'unavailable'}`;
}
export async function getSignalPreferences(){return signalPrefs=await request('/api/alerts/signals');}
export async function saveSignalPreferences(value){
    signalPrefs=await request('/api/alerts/signals',value);updateDeliveryStatus();return signalPrefs;
}
export function getSignalVolume(){return volume;}
export function setSignalVolume(level){
    volume=Math.max(0,Math.min(1,Number(level)));
    try{localStorage.setItem(`alerts.volume.${window.AppSession.username}`,String(volume));}catch{}
}

async function openEditor(rule=null){
    await build();form.elements.field_search.value='';form.elements.field_search.oninput();reset();
    if(rule)fill(rule);
    editorTitle.textContent=rule?'Edit alert':'Create alert';editorStatus.textContent='';editor.showModal();
}
function deliveryState(parent,showAudio=false){const node=el('p','',parent,'settings-note');node.dataset.deliveryStatus='';node.dataset.audio=String(showAudio);updateDeliveryStatus();const feedback=el('p','',parent,'settings-note');feedback.setAttribute('role','status');return feedback;}
export async function renderNotificationSettings(parent){
    parent.replaceChildren();const marker=el('div','',parent);notificationPanel={parent,marker};
    const feedback=deliveryState(parent);status=feedback;
    el('p','Choose which events notify you. Sound choices are in Settings → Sounds. Changes save immediately.',parent,'settings-note');
    const allow=el('button','Allow desktop notifications',parent);
    allow.onclick=async()=>{try{
        if(!('Notification' in window))throw new Error('Desktop notifications are unavailable in this browser.');
        const result=await Notification.requestPermission();updateDeliveryStatus();
        feedback.textContent=result==='granted'?'Desktop notifications allowed.':`Notifications ${result}. Check browser site permissions and macOS System Settings → Notifications.`;
    }catch(error){feedback.textContent=error.message;}};
    try{
        const [prefs,mobile]=await Promise.all([getSignalPreferences(),mobileConfig()]);if(!marker.isConnected)return;
        function toggle(label,key){const check=input(label,key,'checkbox',parent);check.checked=prefs[key]!==false;check.onchange=async()=>{try{await saveSignalPreferences({[key]:check.checked});}catch(error){check.checked=!check.checked;feedback.textContent=error.message;}};}
        toggle('Desktop notifications','notify');
        toggle('Mobile notifications','mobile');
        const mobileToggle=parent.querySelector('[name=mobile]');mobileToggle.disabled=!mobile.ready;mobileToggle.title=mobile.reason;
        const install=el('a','Open mobile app / installation',parent);install.href=mobile.origin?mobile.origin+'/web_root/mobile.html':'/web_root/mobile.html';install.target='_blank';install.rel='noopener';
        const signals=el('fieldset','',parent);el('legend','Automatic signals · active charts',signals);
        for(const side of ['buy','sell']){const check=input(`Notify ${side.toUpperCase()}`,side+'_notify','checkbox',signals);check.checked=prefs[side+'_notify']!==false;check.onchange=()=>void saveSignalPreferences({[side+'_notify']:check.checked}).catch(error=>feedback.textContent=error.message);}
        if(!prefs.enabled){const resume=el('button','Resume automatic signal monitoring',signals);resume.onclick=async()=>{await saveSignalPreferences({enabled:true});await refresh();};}
        el('p','Choose Desktop delivery per timeframe and coin in Settings → Timeframes and Coins. Mobile delivery requires connecting your installed phone app.',signals,'settings-note');
        const heading=el('div','',parent,'settings-coin-actions');el('h4','Custom notifications',heading);
        newButton=el('button','New notification',heading);newButton.onclick=()=>void openEditor().catch(error=>feedback.textContent=error.message);
        const packet=await request('/api/alerts');if(!marker.isConnected)return;
        if(!packet.rules.length)el('p','No custom notifications.',parent,'settings-note');
        for(const rule of packet.rules){
            const row=el('div','',parent,'settings-row notification-rule');
            const check=input(rule.name,rule.id,'checkbox',row);check.checked=rule.enabled;
            check.onchange=()=>void request('/api/alerts',{...rule,enabled:check.checked}).catch(error=>feedback.textContent=error.message);
            el('span',`${rule.symbol} · ${rule.interval}`,row);
            const edit=el('button','Edit',row);edit.setAttribute('aria-label',`Edit ${rule.name}`);edit.onclick=()=>void openEditor(rule);
            const remove=el('button','Remove',row);remove.setAttribute('aria-label',`Remove ${rule.name}`);remove.onclick=async()=>{try{await request('/api/alerts/delete',{id:rule.id});row.remove();}catch(error){feedback.textContent=error.message;}};
        }
        const history=el('details','',parent);el('summary','Recent activity',history);activity=el('section','',history,'alert-activity');renderActivity();
    }catch(error){feedback.textContent=error.message;}
}
export async function renderSoundSettings(parent){
    const marker=el('div','',parent),feedback=deliveryState(parent,true);
    el('p','Upload your own audio or choose a built-in tone. Select Silent to mute an event. Changes save immediately.',parent,'settings-note');
    const enabled=input('Alert sounds on','sound_enabled','checkbox',parent);enabled.checked=soundEnabled;enabled.onchange=()=>{soundEnabled=enabled.checked;soundPreference();if(!soundEnabled){soundQueue.length=0;for(const source of playingSources){try{source.stop();}catch{}}playingSources.clear();}else void unlock().catch(error=>feedback.textContent=error.message);updateDeliveryStatus();};
    const enable=el('button','Enable sound',parent);enable.onclick=async()=>{try{soundEnabled=true;enabled.checked=true;soundPreference();await unlock();sound('chime');updateDeliveryStatus();}catch(error){feedback.textContent=error.message;}};
    const slider=input('Sound volume','volume','range',parent);slider.min=0;slider.max=1;slider.step=.05;slider.value=volume;slider.oninput=()=>setSignalVolume(slider.value);
    try{
        const [prefs,library,packet]=await Promise.all([getSignalPreferences(),request('/api/alerts/sounds'),request('/api/alerts')]);if(!marker.isConnected)return;
        customLibrary=library.sounds;
        const options=[['none','Silent'],['chime','Chime'],['bell','Bell'],['alarm','Alarm'],...customLibrary.map(row=>[row.id,row.name])];
        function tone(label,value,save){
            const row=el('div','',parent,'settings-row'),choice=select(label,'tone',options,row);choice.value=value;
            choice.onchange=()=>{if(soundEnabled&&choice.value!=='none')void unlock().catch(error=>feedback.textContent=error.message);void save(choice.value).catch(error=>feedback.textContent=error.message);};
            const test=el('button',`Preview ${label}`,row);test.onclick=async()=>{try{await unlock();await play(choice.value);feedback.textContent=choice.value==='none'?'This event is silent.':'Preview played.';}catch(error){feedback.textContent=error.message;}};
        }
        for(const side of ['buy','sell'])tone(`${side.toUpperCase()} sound`,prefs[side],value=>saveSignalPreferences({[side]:value}));
        for(const rule of packet.rules)tone(`${rule.name} sound`,rule.sound,value=>request('/api/alerts',{...rule,sound:value}));
        const libraryBox=el('fieldset','',parent);el('legend','Your sounds',libraryBox);
        const file=input('Choose audio file','audio_file','file',libraryBox);file.accept='.wav,.mp3,.ogg,.flac,.m4a,audio/*';
        el('p','Up to 30 seconds and 2 MB per file; 10 files / 10 MB total.',libraryBox,'settings-note');
        const name=input('Sound name','audio_name','text',libraryBox);name.maxLength=120;
        const preview=el('button','Preview new sound',libraryBox),upload=el('button','Add sound',libraryBox);preview.disabled=upload.disabled=true;
        let selected=null;
        file.onchange=async()=>{
            selected=null;preview.disabled=upload.disabled=true;
            try{const chosen=file.files[0];if(!chosen)return;if(chosen.size>2*1024*1024)throw new Error('Audio file must be at most 2 MB.');
                const bytes=await chosen.arrayBuffer(),buffer=await audioContext().decodeAudioData(bytes.slice(0));
                if(buffer.duration>30)throw new Error('Choose an audio clip of 30 seconds or less.');
                selected={bytes,buffer};name.value=chosen.name.replace(/\.[^.]+$/,'').slice(0,120);preview.disabled=upload.disabled=false;feedback.textContent='Ready to preview or add.';
            }catch(error){feedback.textContent=error.message||'This audio file could not be decoded.';}
        };
        preview.onclick=async()=>{try{await unlock();playBuffer(selected.buffer);}catch(error){feedback.textContent=error.message;}};
        upload.onclick=async()=>{upload.disabled=true;try{
            const bytes=new Uint8Array(selected.bytes);let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
            await request('/api/alerts/sounds',{name:name.value,data:btoa(binary)});parent.replaceChildren();await renderSoundSettings(parent);
        }catch(error){feedback.textContent=error.message;upload.disabled=false;}};
        for(const item of customLibrary){
            const row=el('div','',libraryBox,'settings-row');el('span',item.name,row);
            const test=el('button',`Preview ${item.name}`,row);test.onclick=async()=>{try{await unlock();await play(item.id);}catch(error){feedback.textContent=error.message;}};
            const remove=el('button',`Delete ${item.name}`,row);remove.onclick=async()=>{try{await request('/api/alerts/sounds/delete',{id:item.id});customBuffers.delete(item.id);parent.replaceChildren();await renderSoundSettings(parent);}catch(error){feedback.textContent=error.message;}};
        }
    }catch(error){feedback.textContent=error.message;}
}

function audioContext(){const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)throw new Error('Audio is unavailable in this browser.');if(!audio){audio=new Audio();audio.onstatechange=updateDeliveryStatus;}return audio;}
function playBuffer(buffer){const source=audio.createBufferSource(),gain=audio.createGain();source.buffer=buffer;gain.gain.value=volume;source.connect(gain);gain.connect(audio.destination);playingSources.add(source);source.onended=()=>playingSources.delete(source);source.start();return buffer.duration;}
async function play(key,respectMute=false){
    if(key==='none'||audio?.state!=='running'||respectMute&&!soundEnabled)return 0;
    if(!key.startsWith('custom:')){sound(key);return 1.1;}
    if(!customBuffers.has(key)){
        const packet=await request('/api/alerts/sounds?id='+encodeURIComponent(key)),bytes=Uint8Array.from(atob(packet.data),value=>value.charCodeAt(0));
        customBuffers.set(key,await audio.decodeAudioData(bytes.buffer));
    }
    if(respectMute&&!soundEnabled)return 0;
    return playBuffer(customBuffers.get(key));
}

async function renderNotificationDelivery(parent,scope,key){
    const marker=el('span','',parent),feedback=el('span','',parent,'settings-note');
    try{const [prefs,mobile]=await Promise.all([signalPrefs||getSignalPreferences(),mobileConfig()]);if(!marker.isConnected)return;
        for(const [channel,label] of [['desktop','Desktop'],['mobile','Mobile']]){
            const check=input(label,channel,'checkbox',parent);check.setAttribute('aria-label',`${key} ${label} notifications`);
            check.checked=channel==='desktop'?prefs[scope]?.[key]?.desktop!==false:mobile.ready&&prefs[scope]?.[key]?.mobile!==false;
            check.disabled=channel==='mobile'&&!mobile.ready;if(check.disabled)check.title=mobile.reason;
            check.onchange=async()=>{try{await saveSignalPreferences({[scope]:{[key]:{[channel]:check.checked}}});}catch(error){check.checked=!check.checked;feedback.textContent=error.message;}};
        }
    }catch(error){feedback.textContent=error.message;}
}
export function renderTimeframeDelivery(parent,interval){return renderNotificationDelivery(parent,'timeframes',interval);}
export function renderCoinDelivery(parent,symbol){return renderNotificationDelivery(parent,'coins',symbol);}
