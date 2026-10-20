// Immediate server policy actions are separate from Apply/Cancel chart styles.
let session = { role: 'guest', configured: false };
let timeframes = [];
let loadError = "";
function el(tag, text, parent) {
    const node = document.createElement(tag); node.textContent = text;
    if (parent) parent.append(node); return node;
}
async function request(path, data) {
    const response = await fetch(path, data ? {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)} : {cache:'no-store'});
    const packet = await response.json();
    if (!response.ok) throw new Error(packet.error || 'Request failed');
    return packet;
}
export async function load() {
    try {
        session = await request('/api/session');
        timeframes = session.role === 'admin' ? (await request('/api/settings/timeframes')).timeframes : [];
        loadError = '';
    } catch {
        session = {role:'guest',configured:false}; timeframes = [];
        loadError = 'Cannot load account/download settings. Restart the updated UI server and reopen settings.';
    }
}
function message(parent) {
    const node = el('p', '', parent); node.className = 'settings-note'; node.setAttribute('role','status'); return node;
}
function action(parent, title, disabled, callback) {
    const button = el('button', title, parent); button.disabled = disabled;
    button.onclick = async () => {
        button.disabled = true;
        try { await callback(); } finally { if (button.isConnected) button.disabled = disabled; }
    };
    return button;
}
function changed(detail) { window.dispatchEvent(new CustomEvent('data-policy-change', {detail})); }
export function isAdmin() { return session.role === 'admin'; }
export function account(parent) {
    if (loadError) { message(parent).textContent = loadError; return; }
    el('p', session.role === 'guest' ? 'Your session has expired. Sign in again.' : `Signed in as ${session.username} (${session.role}).`, parent);
    const status = message(parent);
    action(parent, session.role === 'guest' ? 'Sign in again' : 'Sign out', false, async () => {
        try {
            await request('/api/logout', {});
            window.location.reload();
        } catch (e) { status.textContent = e.message; }
    });
}
function deleteControl(parent, scope, disabled, after) {
    action(parent, 'Delete data', disabled, async () => {
        if (parent.querySelector('.settings-delete-confirm')) return;
        const box = el('div','',parent); box.className = 'settings-delete-confirm';
        const value = scope.interval || scope.symbol;
        el('p', 'Deletes candles, features and decisions and makes this item inactive. Its settings/registry entry remains. This cannot be undone; Active downloads it again.', box);
        const label = el('label', `Type DELETE ${value}`, box), input = el('input','',label);
        input.autocomplete='off';
        const status = message(box);
        action(box,'Confirm deletion',false,async () => {
            try {
                const result = await request('/api/settings/delete',{...scope,confirmation:input.value});
                changed({deleted:scope});
                status.textContent=`Deleted ${result.deleted.candles} candles, ${result.deleted.features} feature rows and ${result.deleted.decisions} decision rows.`;
                await after();
            } catch (e) { status.textContent=e.message; }
        });
        action(box,'Cancel deletion',false,async () => box.remove());
    });
}
export function renderTimeframes(parent, refresh) {
    if (loadError) { message(parent).textContent = loadError; return; }
    el('p','Policy changes apply immediately to the runner. Inactive retains stored data; deletion also pauses downloads. Administrator settings.',parent).className='settings-note';
    for (const row of timeframes) {
        const wrap=el('div','',parent); wrap.className='settings-policy-item';
        const line=el('div','',wrap); line.className='settings-row';
        el('strong',row.interval,line);
        const label=el('label','Status ',line), select=el('select','',label);
        select.setAttribute('aria-label',`${row.interval} download status`);
        for (const value of ['active','inactive']) { const option=el('option',value,select); option.value=value; select.append(option); }
        select.value=row.status; select.disabled=session.role!=='admin';
        const status=message(wrap);
        select.onchange=async()=>{
            select.disabled=true;
            try { await request('/api/settings/timeframes',{interval:row.interval,status:select.value}); await load(); changed({}); refresh(); }
            catch(e) {status.textContent=e.message;select.value=row.status;}
            finally {select.disabled=session.role!=='admin';}
        };
        deleteControl(wrap,{interval:row.interval},session.role!=='admin',async()=>{await load();refresh();});
    }
}
export function coinActions(parent, selection, refresh) {
    if (loadError) { message(parent).textContent = loadError; return; }
    el('p','Administrator actions apply immediately. Eligibility, pending and staged categories follow registry rules. Select one coin for an action.',parent).className='settings-note';
    const single=selection.size===1, symbol=[...selection][0];
    const status=message(parent), buttons=el('div','',parent); buttons.className='settings-coin-actions';
    for (const [title, actionName] of [['Approve / activate','approve'],['Make inactive','inactive'],['Disapprove','disapprove']]) {
        action(buttons,title,session.role!=='admin'||!single,async()=>{
            try { await request('/api/settings/coins',{symbol,action:actionName});selection.clear();changed({});await refresh(); }
            catch(e) {status.textContent=e.message;}
        });
    }
    deleteControl(parent,{symbol},session.role!=='admin'||!single,refresh);
}
