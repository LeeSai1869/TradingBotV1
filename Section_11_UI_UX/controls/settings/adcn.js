// ADCN administration only. No direct access to physical market stores.
function el(tag,text,parent){const node=document.createElement(tag);node.textContent=text;parent.append(node);return node;}
async function request(data){const response=await fetch('/api/settings/adcn',data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{cache:'no-store'});const packet=await response.json();if(!response.ok)throw new Error(packet.error||'ADCN request failed');return packet;}
export async function renderAdcnMemory(parent){
    const status=el('p','Loading ADCN maintenance…',parent);status.setAttribute('role','status');
    try{
        const catalog=await request();if(!parent.isConnected)return;status.textContent=catalog.note;
        el('p','Nothing is deleted automatically. Review the impact, then type the confirmation. Retirement applies globally to the selected archived fields; history deletion can be limited below. Current decisions, their evidence and checkpoints are protected.',parent);
        const search=el('input','',parent);search.type='search';search.placeholder='Search ADCN fields';search.setAttribute('aria-label','Search ADCN fields');
        const rows=el('div','',parent),checks=[];
        for(const field of catalog.fields){
            const row=el('label','',rows);row.className='settings-row';
            const check=el('input','',row);check.type='checkbox';check.disabled=field.protected||field.retired;check.value=field.field;checks.push(check);
            el('span',`${field.field} · ${field.protected?'PROTECTED':field.retired?'RETIRED':'archived'}`,row);row.title=field.reason;
            if(field.retired){const restore=el('button','Restore future storage',row);restore.onclick=async event=>{event.preventDefault();try{await request({action:'restore',field:field.field});parent.replaceChildren();void renderAdcnMemory(parent);}catch(error){status.textContent=error.message;}};}
        }
        search.oninput=()=>{for(const row of rows.children)row.hidden=!row.textContent.toLowerCase().includes(search.value.toLowerCase());};
        const legacyLabel=el('label','Delete obsolete BUY/SELL history only ',parent),legacy=el('input','',legacyLabel);legacy.type='checkbox';legacy.setAttribute('aria-label','Delete obsolete history');
        const symbol=el('input','',parent);symbol.placeholder='Symbol (blank = all)';symbol.setAttribute('aria-label','History symbol');
        const interval=el('input','',parent);interval.placeholder='Timeframe (blank = all)';interval.setAttribute('aria-label','History timeframe');
        const preview=el('button','Preview ADCN cleanup',parent),review=el('pre','',parent);
        const confirm=el('input','',parent);confirm.placeholder=catalog.confirmation;confirm.setAttribute('aria-label','ADCN confirmation');
        const apply=el('button','Confirm permanent ADCN cleanup',parent);apply.disabled=true;
        let plan=null;
        const invalidate=()=>{plan=null;apply.disabled=true;review.textContent='Selection changed. Preview again.';};
        for(const check of [...checks,legacy])check.addEventListener('change',invalidate);
        for(const field of [symbol,interval])field.addEventListener('input',invalidate);
        const selection=()=>({fields:checks.filter(x=>x.checked).map(x=>x.value),delete_legacy:legacy.checked,symbol:symbol.value.trim().toUpperCase(),interval:interval.value.trim()});
        preview.onclick=async()=>{try{plan=await request({action:'preview',...selection()});review.textContent=JSON.stringify(plan,null,2);apply.disabled=false;status.textContent='Preview only. Review counts and selected fields before confirmation.';}catch(error){status.textContent=error.message;apply.disabled=true;}};
        apply.onclick=async()=>{apply.disabled=true;try{if(!plan)return;await request({action:'apply',...plan,confirmation:confirm.value});status.textContent='ADCN cleanup completed. Permanent candle and feature memory are unchanged.';plan=null;confirm.value='';}catch(error){status.textContent=error.message;}};
    }catch(error){status.textContent=error.message;}
}
