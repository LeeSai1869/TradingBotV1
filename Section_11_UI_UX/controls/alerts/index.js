// Alert configuration is per account; evaluation happens in the local backend.
export const name = 'alerts';
let dialog, form, rules, activity, status, catalog, audio, volume=0.35, eventCursor=null;
let polling=false, timer, editing=null, refreshId=0;
const recent=[];
const soundQueue=[];let soundBusy=false;
function el(tag,text,parent,className) {
    const node=document.createElement(tag);if(text)node.textContent=text;
    if(parent)parent.append(node);if(className)node.className=className;return node;
}
async function request(path,data) {
    const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{cache:'no-store'});
    const packet=await response.json();if(!response.ok)throw new Error(packet.error||`Alert API: ${response.status}`);return packet;
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
    if(!audio)audio=new Audio();await audio.resume();
    if(audio.state!=='running')throw new Error('Click Enable sound again to allow audio.');
}
function sound(key) {
    if(key==='none'||!audio||audio.state!=='running')return;
    const notes={chime:[880,1174,1320],bell:[660,990],alarm:[880,440,880,440]}[key]||[];
    notes.forEach((hz,i)=>{
        const oscillator=audio.createOscillator(), gain=audio.createGain(), t=audio.currentTime+i*.22;
        oscillator.type=key==='alarm'?'square':'sine';oscillator.frequency.value=hz;
        gain.gain.setValueAtTime(0,t);gain.gain.linearRampToValueAtTime(volume*.15,t+.015);gain.gain.exponentialRampToValueAtTime(.0001,t+.3);
        oscillator.connect(gain);gain.connect(audio.destination);oscillator.start(t);oscillator.stop(t+.32);
    });
}
function enqueueSound(key) {
    if(key==='none'||!audio||audio.state!=='running')return;
    if(soundQueue.length<20)soundQueue.push(key);
    function next() {
        if(soundBusy||!soundQueue.length)return;
        soundBusy=true;sound(soundQueue.shift());
        setTimeout(()=>{soundBusy=false;next();},1100);
    }
    next();
}
function renderActivity() {
    if(!activity)return;
    activity.replaceChildren();
    if(!recent.length)el('p','No alerts triggered yet.',activity,'settings-note');
    for(const event of recent.slice(-20).reverse())el('p',`${new Date(event.created).toLocaleString()} — ${event.message} · Candle: ${new Date(event.bar_time).toLocaleString()}`,activity);
}
function receive(event,deliver=true) {
    recent.push(event);if(recent.length>100)recent.shift();renderActivity();
    if(!deliver)return;
    const text=`${event.message} · Candle: ${new Date(event.bar_time).toLocaleString()}`;
    const toast=el('div',text,document.getElementById('alert-toasts'),'alert-toast');toast.setAttribute('role','status');
    setTimeout(()=>toast.remove(),15000);
    while(document.querySelectorAll('.alert-toast').length>5)document.querySelector('.alert-toast').remove();
    enqueueSound(event.sound);
    if(event.notify&&'Notification' in window&&Notification.permission==='granted') {
        try {new Notification(event.name,{body:text,tag:`stored-alert-${event.seq}`});}catch{ /* In-app activity remains available. */ }
    }
}
async function poll() {
    if(polling)return;polling=true;
    try {
        const packet=await request('/api/alerts/events'+(eventCursor===null?'':`?after=${eventCursor}`));
        if(eventCursor===null)for(const event of packet.history||[])receive(event,false);
        for(const event of packet.events)receive(event);
        eventCursor=packet.cursor;
        if(dialog.open&&form)await refresh();
    } catch(error) {if(dialog.open)status.textContent=error.message;}
    finally {polling=false;timer=setTimeout(poll,2000);}
}
async function refresh() {
    const id=++refreshId, packet=await request('/api/alerts');if(id!==refreshId)return;rules.replaceChildren();
    if(!packet.rules.length)el('p','No saved alerts. Create a rule below.',rules,'settings-note');
    for(const rule of packet.rules) {
        const row=el('div','',rules,'alert-rule');
        el('strong',rule.name,row);el('p',`${rule.symbol} ${rule.interval} · ${rule.field} ${rule.operator.replaceAll('_',' ')} ${rule.target_field||rule.value} · ${rule.status}`,row,'settings-note');
        const buttons=el('div','',row,'settings-coin-actions');
        const edit=el('button','Edit',buttons);edit.onclick=()=>fill(rule);
        const toggle=el('button',rule.enabled?'Pause':'Re-arm',buttons);
        toggle.onclick=async()=>{try{await request('/api/alerts',{...rule,enabled:!rule.enabled});await refresh();}catch(error){status.textContent=error.message;}};
        const remove=el('button','Delete rule',buttons);
        remove.onclick=async()=>{try{await request('/api/alerts/delete',{id:rule.id});if(editing===rule.id)reset();await refresh();}catch(error){status.textContent=error.message;}};
    }
}
function syncMode() {
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
    form.scrollIntoView({block:'nearest'});
}
function reset() {
    form.reset();editing=null;
    form.elements.symbol.value=document.getElementById('symbol').value;
    form.elements.interval.value=document.getElementById('interval').value;
    form.elements.field.value='client.close';form.elements.sound.value='chime';
    form.elements.enabled.checked=true;form.elements.notify.checked=true;
    form.elements.repeat.value='once';form.elements.value.value='0';form.elements.mode.value='live';syncMode();
    form.querySelector('button[type=submit]').textContent='Create alert';
}
async function build() {
    if(form)return;
    catalog=await request('/api/alerts/catalog');
    el('p','Live rules watch candle high, low and close. Feature rules use newly stored closed candles and wait for their calculation. Rules run independently of your chart. Keep the app open for sound/notifications; use Enable notifications and sound after opening the app. Old downloaded history does not trigger new closed-feature alerts.',dialog,'settings-note');
    const enable=el('button','Enable notifications and sound',dialog);
    enable.onclick=async()=>{
        const messages=[];
        try{await unlock();sound('chime');messages.push('Sound enabled for this app session.');}catch(error){messages.push(error.message);}
        if('Notification' in window) {
            try{messages.push(`System notifications: ${await Notification.requestPermission()}.`);}catch{messages.push('System notifications unavailable.');}
        } else messages.push('System notifications unavailable here; in-app alerts still work.');
        status.textContent=messages.join(' ');
    };
    const slider=input('Sound volume','volume','range',dialog);slider.min=0;slider.max=100;slider.value=Math.round(volume*100);
    slider.oninput=()=>{volume=Number(slider.value)/100;try{localStorage.setItem(`alerts.volume.${window.AppSession.username}`,String(volume));}catch{}};
    el('h3','Saved alerts',dialog);rules=el('section','',dialog);
    el('h3','Create / edit alert',dialog);form=el('form','',dialog,'alert-form');
    const title=input('Alert name','name','text',form);title.required=true;title.maxLength=120;
    select('Coin','symbol',catalog.symbols.map(value=>[value,value]),form);
    select('Timeframe','interval',catalog.intervals.map(value=>[value,value]),form);
    select('Evaluation','mode',[['live','Live candle / provisional EMA / RSI'],['closed','Closed candle / stored features']],form);
    select('Field','field',Object.entries(catalog.fields),form).onchange=syncMode;
    select('Condition','operator',catalog.operators.map(value=>[value,value.replaceAll('_',' ')]),form);
    const threshold=input('Threshold (signed numbers allowed)','value','number',form);threshold.step='any';threshold.required=true;
    select('Or compare with field','target_field',[['','Use numeric threshold'],...Object.entries(catalog.fields)],form).onchange=syncMode;
    select('Frequency','repeat',[['once','Once, then pause'],['per_bar','Once per matching candle']],form);
    const sounds=select('Sound','sound',catalog.sounds.map(value=>[value,value]),form);
    const test=el('button','Test selected sound',form);test.type='button';test.onclick=async()=>{try{await unlock();sound(sounds.value);status.textContent='Sound test played.';}catch(error){status.textContent=error.message;}};
    input('System notification','notify','checkbox',form);
    input('Alert enabled','enabled','checkbox',form);
    const save=el('button','Create alert',form);save.type='submit';
    const cancel=el('button','New / cancel edit',form);cancel.type='button';cancel.onclick=reset;
    form.onsubmit=async event=>{
        event.preventDefault();save.disabled=true;
        try{await unlock();}catch{ /* In-app alerts still work without audio support. */ }
        try{
            const packet=Object.fromEntries(new FormData(form));packet.value=Number(packet.value);packet.notify=form.elements.notify.checked;packet.enabled=form.elements.enabled.checked;if(editing)packet.id=editing;
            await request('/api/alerts',packet);reset();await refresh();status.textContent='Alert saved. Watching the selected evaluation mode.';
        }catch(error){status.textContent=error.message;}finally{save.disabled=false;}
    };
    el('h3','Recent activity',dialog);activity=el('section','',dialog,'alert-activity');renderActivity();reset();
}
export function mount() {
    try {const stored=Number(localStorage.getItem(`alerts.volume.${window.AppSession.username}`));if(Number.isFinite(stored)&&stored>=0&&stored<=1&&localStorage.getItem(`alerts.volume.${window.AppSession.username}`)!==null)volume=stored;}catch{}
    const toolbar=document.getElementById('toolbar'), open=el('button','Alerts',toolbar);open.id='alerts-button';
    const gear=document.getElementById('settings-button');if(gear)gear.before(open);
    dialog=el('dialog','',document.body,'alerts-dialog');dialog.setAttribute('aria-labelledby','alerts-title');
    const header=el('header','',dialog);el('h2','Alerts',header).id='alerts-title';const close=el('button','Close alerts',header);close.onclick=()=>dialog.close();
    status=el('p','',dialog,'settings-note');status.setAttribute('role','status');
    el('div','',document.body).id='alert-toasts';
    open.onclick=async()=>{dialog.showModal();try{await build();reset();await refresh();}catch(error){status.textContent=error.message+' Restart the updated UI backend if this API is missing.';}};
    dialog.addEventListener('close',()=>open.focus());
    // Polling is independent of chart symbol/viewport; no historical dataset fetches.
    // Initialize the event cursor without replaying old sounds on every reopen.
    request('/api/alerts/events').then(packet=>{eventCursor=packet.cursor;for(const event of packet.history||[])recent.push(event);renderActivity();timer=setTimeout(poll,2000);}).catch(()=>{timer=setTimeout(poll,5000);});
    window.addEventListener('pagehide',()=>clearTimeout(timer),{once:true});
}
