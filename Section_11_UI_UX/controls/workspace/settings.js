import {catalog} from './index.js';
import {normalizeHud} from './preferences.js';
function el(tag,text,parent) {const node=document.createElement(tag);node.textContent=text;parent.append(node);return node;}
export async function renderHudSettings(container,draft) {
    const loading=el('p','Loading HUD settings…',container);
    let choices;
    try {choices=await catalog();} catch(error) {
        if(!container.isConnected)return;
        loading.textContent=error.message;
        const retry=el('button','Retry HUD settings',container);
        retry.onclick=()=>{loading.remove();retry.remove();void renderHudSettings(container,draft);};return;
    }
    if(!loading.isConnected)return;
    loading.remove();draft.hud=normalizeHud(draft.hud);
    const state=draft.hud;
    const note=el('p','Choose a reference coin, 1–8 timeframe columns and up to 20 feature rows. Values use the latest stored closed candle for each timeframe, independently of chart navigation.',container);
    note.className='settings-note';
    const label=el('label','Reference coin ',container);
    const select=el('select','',label);select.setAttribute('aria-label','HUD reference coin');
    const symbols=[...new Set([state.symbol,...choices.symbols].filter(Boolean))];
    for(const symbol of ['',...symbols]){const option=el('option',symbol||'Follow current chart',select);option.value=symbol;}
    select.value=state.symbol;select.onchange=()=>{state.symbol=select.value;};
    const timeframes=el('fieldset','',container);el('legend','Timeframe columns (1–8)',timeframes);
    const controls=[];
    for(const interval of choices.intervals) {
        const row=el('label','',timeframes);row.className='hud-timeframe-choice';
        const check=el('input','',row);check.type='checkbox';check.checked=state.intervals.includes(interval);
        check.setAttribute('aria-label',`HUD timeframe ${interval}`);el('span',interval,row);controls.push(check);
        check.onchange=()=>{
            if(check.checked && state.intervals.length<8)state.intervals.push(interval);
            else if(!check.checked && state.intervals.length>1)state.intervals=state.intervals.filter(x=>x!==interval);
            sync();
        };
    }
    function sync(){for(const check of controls){const interval=check.getAttribute('aria-label').replace('HUD timeframe ','');check.checked=state.intervals.includes(interval);check.disabled=check.checked?state.intervals.length===1:state.intervals.length>=8;}}
    sync();
    el('p','Columns appear in selection order. Uncheck and reselect to move a column to the end.',container).className='settings-note';
    const fields=el('section','',container);el('h4','Feature rows',fields);
    const rows=el('div','',fields), addLabel=el('label','Add feature ',fields), addSelect=el('select','',addLabel);
    addSelect.setAttribute('aria-label','HUD feature to add');
    for(const [key,title] of Object.entries(choices.fields)){const option=el('option',title,addSelect);option.value=key;}
    const add=el('button','Add feature row',fields);
    function renderRows(){
        rows.replaceChildren();
        state.fields.forEach((field,index)=>{
            const row=el('div','',rows);row.className='settings-row';el('span',choices.fields[field]||field,row);
            const actions=el('span','',row);
            const up=el('button','↑',actions);up.setAttribute('aria-label',`Move ${choices.fields[field]||field} up`);up.disabled=index===0;
            up.onclick=()=>{[state.fields[index-1],state.fields[index]]=[state.fields[index],state.fields[index-1]];renderRows();};
            const remove=el('button','Remove',actions);remove.setAttribute('aria-label',`Remove ${choices.fields[field]||field}`);remove.disabled=state.fields.length===1;
            remove.onclick=()=>{state.fields.splice(index,1);renderRows();};
        });
        for(const option of addSelect.options)option.disabled=state.fields.includes(option.value);
        const available=[...addSelect.options].find(option=>!option.disabled);
        if(addSelect.selectedOptions[0]?.disabled && available)addSelect.value=available.value;
        add.disabled=state.fields.length>=20 || !available;
    }
    add.onclick=()=>{if(!state.fields.includes(addSelect.value)&&state.fields.length<20){state.fields.push(addSelect.value);renderRows();}};
    renderRows();
}
