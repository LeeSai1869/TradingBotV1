'use strict';
const $=id=>document.getElementById(id),csrf=document.querySelector('meta[name=dashboard-token]').content;
let initialSelection='';try{initialSelection=decodeURIComponent(location.hash.slice(1));}catch{}
let packet={accounts:[],fills:[],intervals:['5m']},selected=initialSelection,busy=false,refreshing=false,again=false;
let edit=null,closePreview=null,lastDiagnostic=0,lastFillSignature='',lastNavSignature='',diagnosticGeneration=0;
const form=$('allocation-form'),dialog=$('allocation-dialog');
const editable=['capital_cap','stop_loss_pct','take_profit_pct','fee_bps','slippage_bps','max_signal_age_seconds'];
const labels={STRATEGY_BUY:'Strategy BUY',STRATEGY_SELL:'Strategy SELL',STOP_LOSS:'Stop-loss',TAKE_PROFIT:'Take-profit',MANUAL_CLOSE:'Manual paper exit'};
const explanations={WAITING_FOR_SHARED_CASH:'Shared cash is in use. This slot needs available funds and a new confirmed BUY.',WAITING_FOR_NEW_CONFIRMED_BUY:'Waiting for a new confirmed BUY. No position is open.',DECISION_WORKER_BEHIND:'Decision processing is behind the latest stored candle.',FEATURE_WORKER_BEHIND:'Feature processing is behind the latest stored candle.',MARKET_DATA_STALE:'Stored market candles are stale.',QUOTE_UNAVAILABLE_OR_STALE:'A fresh worker quote is not available.',STRATEGY_FEED_UNAVAILABLE:'The strategy feed is unavailable.',HALTED_REVIEW_REQUIRED:'This allocation is halted and needs review.',FRESH_BUY_PENDING:'A fresh BUY is waiting for a worker turn.',RECENT_BUY_TOO_OLD_TO_EXECUTE:'A recent BUY is too old to execute.',POSITION_OPEN_MONITORING_EXITS:'Position open. The worker monitors strategy and protective exits.',ENTRIES_PAUSED:'New entries are paused.'};
const active=()=>packet.accounts.find(a=>a.name===selected);
function text(id,value){const next=String(value??'—');if($(id).textContent!==next)$(id).textContent=next;}
function number(value,digits=6){if(value===null||value===undefined||!Number.isFinite(Number(value)))return '—';return new Intl.NumberFormat('en-US',{maximumFractionDigits:digits}).format(Number(value));}
function stamp(value){return value==null?'—':new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Karachi',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(value));}
function message(value,error=false,kind='action'){$('message').dataset.kind=kind;$('message').hidden=!value;$('message').className='message'+(error?' error':'');text('message',value);}
async function api(path,data){
    const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),8000);
    try{
        const response=await fetch(path,{cache:'no-store',signal:controller.signal,...(data?{method:'POST',headers:{'Content-Type':'application/json','X-Dashboard-Token':csrf},body:JSON.stringify(data)}:{})});
        const result=await response.json();if(!response.ok)throw Error(result.error||'Request failed');return result;
    }finally{clearTimeout(timeout);}
}
function profit(id,value){text(id,number(value));$(id).classList.toggle('positive',value!=null&&Number(value)>0);$(id).classList.toggle('negative',value!=null&&Number(value)<0);}
function render(){
    $('new').disabled=$('empty-new').disabled=busy;
    const navSignature=JSON.stringify(packet.accounts.map(a=>[a.name,a.config.symbol,a.config.interval,a.state.enabled,a.state.halted]));
    if(navSignature!==lastNavSignature){
        lastNavSignature=navSignature;
        const existing=new Map([...$('allocations').children].map(b=>[b.dataset.name,b]));
        for(const account of packet.accounts){
            let button=existing.get(account.name);
            if(!button){button=document.createElement('button');button.className='allocation-button';button.dataset.name=account.name;
                button.append(document.createElement('strong'),document.createElement('small'));button.onclick=()=>choose(account.name);$('allocations').append(button);}
            button.children[0].textContent=account.config.symbol+' · '+account.config.interval;
            button.children[1].textContent=account.name+' · '+(account.state.halted?'Halted':account.state.enabled?'Enabled':'Paused');existing.delete(account.name);
        }
        for(const button of existing.values())button.remove();
    }
    for(const button of $('allocations').children)button.setAttribute('aria-current',String(button.dataset.name===selected));
    const account=active();$('empty').hidden=!!account;$('detail').hidden=!account;if(!account)return;
    const cfg=account.config,s=account.state,open=Number(s.quantity)>0;
    text('market',cfg.symbol+' / '+cfg.interval);text('account-name',account.name+' · strategy slot in one paper bot');
    text('state-badge',s.halted?'HALTED':s.enabled?'ENTRIES ENABLED':'ENTRIES PAUSED');$('state-badge').className='badge '+(s.halted?'bad':s.enabled?'good':'');
    const wallet=packet.wallet||{};
    text('equity',number(wallet.estimated_equity));text('equity-estimate',wallet.quotes_fresh?'':'· last observed');
    text('cash',number(wallet.cash));profit('pnl',wallet.realized_pnl);profit('unrealized',wallet.unrealized_pnl);
    text('position',open?number(s.quantity,9)+' '+cfg.symbol.slice(0,-4):'No open position');
    text('entry',open?number(s.entry,9)+' USDT':'—');
    text('quote',s.last_bid!=null?number(s.last_bid,9)+' / '+number(s.last_ask,9)+' USDT':'Not yet reported by this worker');
    text('quote-age',account.quote_age_seconds==null?'No successful quote yet':number(account.quote_age_seconds,1)+' seconds'+(account.quote_fresh?' · fresh':' · stale'));
    $('quote-age').classList.toggle('negative',!account.quote_fresh&&(s.enabled||open));
    text('exits',cfg.stop_loss_pct+'% / '+cfg.take_profit_pct+'% · live price');
    const divisor=1-Number(cfg.slippage_bps)/10000;
    text('thresholds',open?number(Number(s.entry)*(1-Number(cfg.stop_loss_pct)/100)/divisor,9)+' / '+number(Number(s.entry)*(1+Number(cfg.take_profit_pct)/100)/divisor,9)+' USDT':'Shown after entry');
    text('strategy',cfg.strategy_source==='current'?'Current live strategy':'Selected strategy instance');
    text('initial',number(packet.wallet?.initial_capital)+' USDT');text('cap',number(cfg.capital_cap)+' USDT');
    text('costs',cfg.fee_bps+' / '+cfg.slippage_bps+' bps per side');text('signal-age',cfg.max_signal_age_seconds+' seconds');text('worker-status',s.status);
    text('worker-activity',account.activity_age_seconds==null?'No activity reported':number(account.activity_age_seconds,1)+' seconds ago');
    $('enable').disabled=busy||s.enabled||s.halted;$('pause').disabled=busy||!s.enabled;$('close-position').disabled=busy||!open;
    $('settings').disabled=busy||s.enabled||open;
    $('settings').title=s.enabled||open?'Pause entries and close the position before editing settings':'Edit cap, exits and modeled costs';
    const fills=packet.fills_account===selected?packet.fills:[];
    const signature=JSON.stringify([selected,fills]);
    if(signature!==lastFillSignature){
        lastFillSignature=signature;$('fills').replaceChildren();
        if(!fills.length){const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=7;cell.textContent='No paper executions yet. New confirmed signals will appear here.';row.append(cell);$('fills').append(row);}
        for(const fill of fills){const row=document.createElement('tr');
            for(const [i,value] of [stamp(fill.at_ms),fill.side,labels[fill.reason]||fill.reason,number(fill.price,9),number(fill.quantity,9),number(fill.fee,6),fill.pnl==null?'—':number(fill.pnl)].entries()){
                const cell=document.createElement('td');cell.textContent=value;
                if(i===1)cell.className=fill.side==='BUY'?'positive':'negative';
                if(i===6&&fill.pnl!=null)cell.className=Number(fill.pnl)>=0?'positive':'negative';row.append(cell);
            }$('fills').append(row);
        }
    }
    text('fill-count',fills.length+' recent');
}
async function refresh(){
    if(refreshing){again=true;return;}refreshing=true;
    let requested=selected;
    try{
        let next=await api('/api/state'+(requested?'?name='+encodeURIComponent(requested):''));
        if(selected!==requested){again=true;return;}
        if(!next.accounts.some(a=>a.name===selected)){
            selected=next.accounts[0]?.name||'';history.replaceState(null,'',selected?'#'+encodeURIComponent(selected):location.pathname);
            requested=selected;
            if(selected)next=await api('/api/state?name='+encodeURIComponent(selected));
        }
        if(selected!==requested){again=true;return;}
        if($('message').dataset.kind==='refresh')message('');
        packet=next;render();text('refreshed','Updated '+stamp(next.server_time_ms)+' PKT');
        if(selected&&Date.now()-lastDiagnostic>30000&&!document.hidden)void checkDiagnostics();
    }catch(error){message('Dashboard refresh failed: '+error.message+'. Displayed values may be stale.',true,'refresh');}
    finally{refreshing=false;if(again){again=false;void refresh();}}
}
function choose(name){if(selected===name)return;selected=name;history.replaceState(null,'','#'+encodeURIComponent(name));
    diagnosticGeneration++;lastDiagnostic=0;$('diagnose').disabled=false;packet.fills=[];lastFillSignature='';text('diagnosis','Checking selected allocation…');$('pipeline').replaceChildren();render();void refresh();}
async function checkDiagnostics(){
    if(!selected)return;const name=selected,generation=++diagnosticGeneration;lastDiagnostic=Date.now();$('diagnose').disabled=true;
    try{
        const result=(await api('/api/diagnostics?name='+encodeURIComponent(name)))[0];
        if(selected!==name||generation!==diagnosticGeneration)return;
        text('diagnosis',(explanations[result.diagnosis]||result.diagnosis)+(result.error?' '+result.error:''));
        $('pipeline').replaceChildren();
        const p=result.pipeline||{},signal=p.latest_signal_last_24h;
        for(const value of ['Candle: '+stamp(p.raw_open_ms),'Features: '+stamp(p.feature_through_ms),'Decisions: '+stamp(p.decision_through_ms),
            'Decision lag: '+(p.decision_lag_seconds==null?'—':number(p.decision_lag_seconds)+'s'),
            'Recent signal: '+(signal?signal.side+' · '+stamp(signal.close_time):'None in last 24h')]){
            const span=document.createElement('span');span.textContent=value;$('pipeline').append(span);
        }text('diagnostic-time','Checked '+stamp(Date.now())+' PKT · quote activity is reported by the separate worker');
    }catch(error){if(selected===name)text('diagnosis','Diagnostic unavailable: '+error.message);}
    finally{if(selected===name)$('diagnose').disabled=false;}
}
async function action(data){
    if(busy)return;busy=true;render();
    try{const result=await api('/api/action',data);message(result.message||'Paper allocation updated.');lastDiagnostic=0;await refresh();return result;}
    finally{busy=false;render();}
}
for(const [id,actionName] of [['enable','enable'],['pause','pause']])$(id).onclick=async()=>{
    const account=active();try{await action({action:actionName,name:account.name,expected_config:account.config_token});}catch(error){message(error.message,true);}
};
function openForm(account=null){
    if(busy)return;
    edit=account?{name:account.name,token:account.config_token}:null;form.reset();text('form-error','');
    const choices=packet.intervals||['5m'];form.elements.interval.replaceChildren(...choices.map(value=>{const option=document.createElement('option');option.value=value;option.textContent=value;return option;}));
    form.elements.interval.value=account?.config.interval||'5m';
    const cfg=account?.config||{name:'ena-5m',symbol:'ENAUSDT',initial_capital:'100',capital_cap:'200',stop_loss_pct:'2',take_profit_pct:'4',fee_bps:'10',slippage_bps:'5',max_signal_age_seconds:180};
    for(const name of ['name','symbol','initial_capital',...editable])form.elements[name].value=cfg[name];
    for(const name of ['name','symbol','interval','strategy'])form.elements[name].disabled=!!account;
    const funding=!account&&!packet.wallet;form.elements.initial_capital.disabled=!funding;form.elements.initial_capital.parentElement.hidden=!funding;
    text('form-title',account?'Edit allocation settings':'New paper allocation');text('save',account?'Save settings':'Create paused allocation');
    text('form-help',account?'Changes preserve the balance and fill history. Use a new allocation to change its coin, timeframe, or strategy.':'Uses the existing strategy for an active coin/timeframe. Slots share the bot wallet and start paused. Starting funds are set only for the first slot.');
    dialog.showModal();
}
$('new').onclick=$('empty-new').onclick=()=>openForm();$('settings').onclick=()=>openForm(active());
$('form-close').onclick=$('form-cancel').onclick=()=>{if(!busy)dialog.close();};
dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
form.onsubmit=async event=>{
    event.preventDefault();if(busy)return;
    const values={};for(const name of editable)values[name]=name==='max_signal_age_seconds'?Number(form.elements[name].value):form.elements[name].value;
    const data=edit?{action:'configure',name:edit.name,expected_config:edit.token,changes:values}:
        {action:'create',config:{...values,name:form.elements.name.value,symbol:form.elements.symbol.value.trim().toUpperCase(),interval:form.elements.interval.value,...(!packet.wallet?{initial_capital:form.elements.initial_capital.value}:{})}};
    for(const id of ['save','form-close','form-cancel','form-fields'])$(id).disabled=true;
    text('save','Saving…');text('form-error','');
    try{const result=await action(data);if(result){selected=result.name;history.replaceState(null,'','#'+encodeURIComponent(selected));dialog.close();lastDiagnostic=0;void refresh();}}
    catch(error){text('form-error',error.message);}finally{for(const id of ['save','form-close','form-cancel','form-fields'])$(id).disabled=false;text('save',edit?'Save settings':'Create paused allocation');}
};
$('close-position').onclick=()=>{
    const account=active();closePreview={name:account.name,expected_position:account.position_token};
    text('close-summary','Close '+number(account.state.quantity,9)+' '+account.config.symbol.slice(0,-4)+' in '+account.name+'?');text('close-error','');$('close-dialog').showModal();
};
$('close-cancel').onclick=()=>{if(!busy)$('close-dialog').close();};
$('close-dialog').addEventListener('cancel',event=>{if(busy)event.preventDefault();});
$('close-confirm').onclick=async()=>{
    if(busy)return;$('close-confirm').disabled=$('close-cancel').disabled=true;text('close-error','');
    try{await action({action:'close',...closePreview});$('close-dialog').close();}
    catch(error){text('close-error',error.message);}finally{$('close-confirm').disabled=$('close-cancel').disabled=false;}
};
$('refresh').onclick=()=>void refresh();$('diagnose').onclick=()=>void checkDiagnostics();
document.addEventListener('visibilitychange',()=>{if(!document.hidden)void refresh();});
(async function poll(){if(!document.hidden)await refresh();setTimeout(poll,2000);})();
