// Strategy administration; all validation and scoped deletion belong to Core.
import {isAdmin} from './admin_controls.js';
const API='/api/settings/strategies';
function el(tag,text,parent){const node=document.createElement(tag);node.textContent=text;parent.append(node);return node;}
async function request(data,path=API){
    const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{cache:'no-store'});
    const packet=await response.json();if(!response.ok)throw Error(packet.error||'Strategy request failed');return packet;
}
function select(parent,label,values,current){
    const row=el('label',label+' ',parent),field=el('select','',row);field.setAttribute('aria-label',label);
    for(const [value,text] of values){const option=el('option',text,field);option.value=value;}
    if(values.some(([v])=>v===current))field.value=current;return field;
}
const stamp=value=>value==null?'Not calculated':new Date(value).toLocaleString();

export async function renderStrategies(parent,initial={}){
    if(!isAdmin()){el('p','Administrator access required for strategy management.',parent);return;}
    const status=el('p','Loading strategies…',parent);status.setAttribute('role','status');
    try{
        const data=await request();if(!status.isConnected)return;status.textContent=data.note;
        const symbol=select(parent,'Strategy coin',data.symbols.map(v=>[v,v]),initial.symbol??document.getElementById('symbol')?.value);
        const interval=select(parent,'Strategy timeframe',data.intervals.map(v=>[v,v]),initial.interval??document.getElementById('interval')?.value);
        const definition=select(parent,'Production strategy',data.strategies.map(v=>[`${v.strategy_id}:${v.version}`,v.name]));
        const label=el('label','Optional history start ',parent),start=el('input','',label);start.type='datetime-local';start.setAttribute('aria-label','Strategy history start');
        el('p','Blank starts now. A past start requests bounded backfill. Existing legacy history is retained separately. Re-enabling a paused strategy resumes from now, retaining its previous history.',parent);
        const enable=el('button','Enable and select strategy',parent),pause=el('button','Deactivate all for this pair',parent),list=el('div','',parent);
        const pair=()=>({symbol:symbol.value,interval:interval.value});
        const refreshChart=()=>{if(window.DataCache?.symbol===symbol.value&&window.DataCache?.timeframe===interval.value)document.getElementById('reload')?.click();};
        async function update(action,extra={}){
            const scope=pair();const result=await request({action,...scope,...extra});
            if(status.isConnected){refreshChart();parent.replaceChildren();void renderStrategies(parent,scope);}
            return result;
        }
        enable.onclick=async()=>{enable.disabled=true;try{
            const [strategy_id,version]=definition.value.split(':');const extra={strategy_id,version:Number(version)};
            if(start.value)extra.start_at=new Date(start.value).getTime();await update('enable',extra);
        }catch(error){status.textContent=error.message;enable.disabled=false;}};
        pause.onclick=async()=>{pause.disabled=true;try{await update('pause_pair');}catch(error){status.textContent=error.message;pause.disabled=false;}};
        function draw(){
            list.replaceChildren();const rows=data.instances.filter(item=>item.symbol===symbol.value&&item.interval===interval.value);
            const binding=data.pairs.find(item=>item.symbol===symbol.value&&item.interval===interval.value);
            if(!rows.length)el('p',binding?'No enabled/selected strategy for this managed pair.':'This pair still uses the legacy DI rule. Enabling or deactivating it here makes the pair explicitly managed.',list);
            for(const item of rows){
                const group=el('fieldset','',list);el('legend',`${item.strategy_id} v${item.version} · ${item.selected?'Selected':item.enabled?'Comparison':'Inactive'}`,group);
                if(item.market_active===false)el('p','Coin or timeframe is inactive; no new calculations are running.',group);
                if(item.source_available===false)el('p','Pinned strategy source is unavailable. Calculation is stopped; select a registered version.',group);
                el('p',`${item.events} saved events (${item.buys} BUY / ${item.sells} SELL). Calculated through ${stamp(item.through)}. Counts include retained calculation generations.`,group);
                const history=el('button','View saved signals',group),details=el('pre','',group);
                history.onclick=async()=>{try{const result=await request(null,API+'/history?instance_id='+encodeURIComponent(item.id));details.textContent=result.events.map(event=>`${stamp(event.open_time)} · ${event.side} · ${event.price}`).join('\n')||'No saved BUY/SELL events.';}catch(error){status.textContent=error.message;}};
                const choose=el('button',item.enabled?'Select for chart':'Enable and select',group);choose.disabled=!!item.selected;
                choose.onclick=async()=>{try{await update(item.enabled?'select':'enable',item.enabled?{instance_id:item.id}:{strategy_id:item.strategy_id,version:item.version});}catch(error){status.textContent=error.message;}};
                const deactivate=el('button','Deactivate',group);deactivate.disabled=!item.enabled;
                deactivate.onclick=async()=>{try{await update('deactivate',{instance_id:item.id});}catch(error){status.textContent=error.message;}};
                const preview=el('button','Preview strategy deletion',group);preview.disabled=!!item.enabled;
                const confirmationLabel=el('label','Deletion confirmation ',group),confirmation=el('input','',confirmationLabel);confirmation.setAttribute('aria-label','Strategy deletion confirmation');
                const remove=el('button','Delete this strategy and its memory',group);remove.disabled=true;let plan=null;
                preview.onclick=async()=>{try{plan=await request({action:'preview_delete',instance_id:item.id});details.textContent=`Delete ${plan.events} events and this strategy checkpoint for ${plan.symbol} ${plan.interval} / ${plan.strategy_id} v${plan.version}. Other histories and market data are retained.\nType: ${plan.required_confirmation}`;remove.disabled=false;}catch(error){status.textContent=error.message;}};
                remove.onclick=async()=>{remove.disabled=true;try{await update('delete',{...plan,confirmation:confirmation.value});}catch(error){status.textContent=error.message;remove.disabled=false;}};
            }
        }
        symbol.onchange=draw;interval.onchange=draw;draw();
    }catch(error){status.textContent=error.message;}
}
