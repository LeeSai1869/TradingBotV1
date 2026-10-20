import {normalizeHud} from './preferences.js';
export const name = 'workspace';
let panel, hud, hudToggle, table, heading, status, toggle, timer, request, generation = 0, pending = false;
let catalogPromise;
export function catalog() {
    if (!catalogPromise) catalogPromise = fetch('/api/hud/catalog',{cache:'no-store'}).then(async response => {
        if (!response.ok) throw new Error('Cannot load HUD choices. Restart the updated UI server.');
        return response.json();
    }).catch(error => {catalogPromise=null; throw error;});
    return catalogPromise;
}
function el(tag, text, parent, className) {
    const node=document.createElement(tag);node.textContent=text;
    if(className)node.className=className;
    parent?.append(node);return node;
}
function preferences() {return normalizeHud(window.Composer.config.hud);}
function selectedSymbol(config) {return config.symbol || document.getElementById('symbol').value;}
function format(value) {
    if(value==null)return '—';
    if(typeof value==='number')return new Intl.NumberFormat(undefined,{maximumSignificantDigits:7}).format(value);
    return String(value);
}
function invalidate() {
    generation++; request?.abort();pending=false;
    table?.replaceChildren();
    if(hud) {
        const config=preferences();hud.hidden=!config.visible;hud.dataset.position=config.position;
        hudToggle.setAttribute("aria-pressed",String(config.visible));
        if(config.visible)void refresh();
    }
}
async function refresh() {
    if(hud.hidden || pending || document.hidden)return;
    const config=preferences(), symbol=selectedSymbol(config);
    if(!symbol)return;
    const version=generation;pending=true;request=new AbortController();
    heading.textContent=`${symbol} · closed candles`;
    status.textContent='Updating comparison…';
    try {
        const response=await fetch('/api/hud?'+new URLSearchParams({symbol,intervals:config.intervals.join(','),fields:config.fields.join(',')}),
            {cache:'no-store',signal:request.signal});
        if(!response.ok)throw new Error('Cannot load comparison. Restart the updated UI server.');
        const packet=await response.json(), choices=await catalog();
        if(version!==generation || hud.hidden)return;
        table.replaceChildren();
        const caption=el('caption',`${symbol} multi-timeframe comparison`,table);
        caption.className='sr-only';
        const head=el('thead','',table), headRow=el('tr','',head);
        el('th','Feature',headRow).scope='col';
        for(const column of packet.columns) {
            const cell=el('th',column.interval,headRow);cell.scope='col';
            const state=!column.active?'Inactive':column.stale?'Stale':column.open_time==null?'Waiting':'Stored';
            el('small',state,cell,column.stale?'hud-stale':'');
            const time=el('small',column.open_time==null?'No candles':new Date(column.open_time).toISOString().replace('T',' ').slice(0,16)+' UTC',cell);
            time.title='Open time of the latest stored candle';
        }
        const body=el('tbody','',table);
        for(const field of config.fields) {
            const row=el('tr','',body);el('th',choices.fields[field] || field,row).scope='row';
            for(const column of packet.columns) {
                const value=column.values[field];const cell=el('td',format(value),row);
                cell.title=value==null?'Not calculated or downloaded yet':`${symbol} ${column.interval} · ${choices.fields[field] || field}: ${value}`;
            }
        }
        status.textContent='Latest stored values · refreshed '+new Date(packet.as_of).toLocaleTimeString()+'. Missing values appear as —.';
    } catch(error) {
        if(version===generation && error.name!=='AbortError') {
            table.replaceChildren();status.textContent=error.message;
        }
    } finally {if(version===generation)pending=false;}
}
export function mount() {
    panel=document.getElementById('analysis-panel');
    document.getElementById('chart').append(document.getElementById('flags-panel'));
    toggle=el('button','Analysis',document.getElementById('toolbar'));
    toggle.id='workspace-button';toggle.setAttribute('aria-controls','analysis-panel');toggle.setAttribute('aria-expanded','false');
    const header=el('header','',panel);el('h2','Analysis workspace',header);
    const close=el('button','Collapse panel',header);close.onclick=()=>setOpen(false);
    const opportunity=el('section','',panel,'workspace-card');el('h3','Best opportunity',opportunity);
    el('p','AI ranking is not connected yet. Opportunities across coins will appear here once the prediction engine is ready.',opportunity);
    const body=el('div','',panel,'workspace-body');
    body.tabIndex=0;body.setAttribute('role','region');body.setAttribute('aria-label','Analysis and chat');
    hud=el('section','',document.getElementById('chart'),'chart-hud');
    hud.id='chart-hud';hud.setAttribute('aria-label','Comparison HUD');
    hudToggle=el('button','HUD',document.getElementById('toolbar'));
    hudToggle.setAttribute('aria-label','Show comparison HUD');hudToggle.setAttribute('aria-controls','chart-hud');
    hudToggle.onclick=()=>window.dispatchEvent(new CustomEvent('hud-visibility-change',{detail:!preferences().visible}));
    const hudHeader=el('header','',hud,'hud-header');
    heading=el('strong','',hudHeader);const settings=el('button','⚙',hudHeader);
    settings.setAttribute('aria-label','Configure HUD');
    settings.onclick=()=>window.dispatchEvent(new Event('open-hud-settings'));
    const scroll=el('div','',hud,'hud-scroll');table=el('table','',scroll);table.id='comparison-hud';
    status=el('p','',hud,'workspace-note');status.setAttribute('role','status');
    // Interacting with the overlay must not pan or zoom the chart underneath it.
    for(const event of ['pointerdown','mousedown','touchstart','wheel','dblclick'])hud.addEventListener(event,event=>event.stopPropagation());
    const analysis=el('section','',body,'workspace-card');el('h3','Chart analysis',analysis);
    el('p','Coin and timeframe analysis will be connected here later.',analysis);
    const chat=el('section','',body,'workspace-card workspace-chat');el('h3','AI chat',chat);
    el('p','Chat will be available when an AI provider is connected.',chat);
    const input=el('textarea','',chat);input.disabled=true;input.placeholder='AI chat is not connected yet';input.setAttribute('aria-label','AI chat message');
    const send=el('button','Send',chat);send.disabled=true;
    function setOpen(open) {
        panel.hidden=!open;toggle.setAttribute('aria-expanded',String(open));
        if(!open)toggle.focus();
        try{localStorage.setItem('tradingbot.workspace-open',String(open));}catch{}
    }
    toggle.onclick=()=>setOpen(panel.hidden);
    panel.onkeydown=event=>{if(event.key==='Escape')setOpen(false);};
    document.getElementById('symbol').addEventListener('change',invalidate);
    window.addEventListener('chart-settings-change',invalidate);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)void refresh();});
    invalidate();
    timer=setInterval(()=>void refresh(),5000);
    window.addEventListener('pagehide',()=>{clearInterval(timer);request?.abort();},{once:true});
    try{if(localStorage.getItem('tradingbot.workspace-open')==='true')setOpen(true);}catch{}
}
