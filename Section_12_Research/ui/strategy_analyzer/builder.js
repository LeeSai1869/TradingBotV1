/* Browser configuration and replay orchestration. Rule evaluation stays in Python. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const copy = value => JSON.parse(JSON.stringify(value));
  let catalog, metadata, model, currentReport, currentReportId, inputToken = 0, running = false;
  let reportFields = new Set();
  const draftKey = 'btc-hour-strategy-workspace-draft-v1';
  let previousDraft = null;
  const previousDraftKey=draftKey+'-previous';
  const blankStrategy = () => ({version:'btc-hour-strategy-analyzer-v1',id:'My strategy',branches:[{id:'buy',side:'BUY',expanded:true,when:{all:[defaultLeaf()]}},{id:'sell',side:'SELL',expanded:true,when:{all:[defaultLeaf()]}}]});
  const fields = () => metadata?.fields || [];
  const fieldInfo = name => fields().find(f => f.id === name);
  const human = name => StrategyReport.fieldLabel(name);
  function node(tag, text, parent, attrs = {}) {
    const n = document.createElement(tag); if (text !== undefined) n.textContent = text;
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v)); if (parent) parent.append(n); return n;
  }
  function label(text, parent) { return node('label', text, parent); }
  function button(text, parent, action) { const b = node('button', text, parent, {type: 'button'}); b.onclick = action; return b; }
  function error(message = '') { $('workspace-error').hidden = !message; $('workspace-error').textContent = message; }
  async function api(path, body) {
    const response = await fetch(path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const result = await response.json(); if (!response.ok) throw Error(result.error || `Request failed (${response.status})`); return result;
  }
  function guard(action) { return async (...args) => { try { error(); await action(...args); } catch (e) { error(e.message); } }; }
  function remember() {
    try { localStorage.setItem(draftKey, JSON.stringify({model, reportFields: [...reportFields],inputId:$('input-source').value,symbols:[...$('memory-coins').selectedOptions].map(o=>o.value),baselineKey:$('baseline-preset').value,since:$('replay-since').value,until:$('replay-until').value})); } catch (_) { /* Downloads remain available if storage is unavailable. */ }
  }
  function stageExpression(expr,stage){
    if(expr.all||expr.any){const key=expr.all?'all':'any',children=expr[key].map(e=>stageExpression(e,stage)).filter(Boolean);return children.length?{[key]:children}:null;}
    if(expr.not){const child=stageExpression(expr.not,stage);return child?{not:child}:null;}
    return (expr.stage||'activate')===stage?expr:null;
  }
  function configuredExpression(expr){return !!(expr && (expr.field || (expr.all||expr.any||[]).some(configuredExpression) || (expr.not&&configuredExpression(expr.not))));}
  function positionTrail(branch){return branch.side==='SELL'&&branch.action==='TRAILING_SELL'&&(branch.condition_mode==='position'||(!branch.condition_mode&&(!configuredExpression(branch.when)||(branch.when?.field==='price.close'&&branch.when?.op==='available'&&!branch.when?.lag))));}
  document.addEventListener('click',e=>{for(const menu of document.querySelectorAll('.field-dropdown[open]'))if(!menu.contains(e.target))menu.open=false;});
  function configuration() {
    const config = {version: 'btc-hour-strategy-analyzer-v1', id: $('strategy-name').value.trim(),
      execution: {fee_bps_per_side: Number($('fee').value), slippage_bps_per_side: Number($('slippage').value), initial_capital: Number($('capital').value),intrabar_path:$('intrabar-path').value},
      branches: model.branches.filter(b => b.enabled !== false).map(branch => {const {id, side, when,action,trail,target_profit_pct}=branch;return ({id, side,...(branch.activation_timing==='later'&&!positionTrail(branch)?{activation_timing:'later'}:{}), when: positionTrail(branch)?{field:'price.close',op:'available'}:copy(when),...(side==='SELL'&&action?{action,...(trail?{trail:copy(trail)}:{}),...(target_profit_pct!==undefined?{target_profit_pct}:{})}:{})});})};
    if (!config.id) throw Error('Give your strategy a name.');
    if (!config.branches.some(b => b.side === 'BUY') || !config.branches.some(b => b.side === 'SELL')) throw Error('Enable at least one BUY and one SELL branch.');
    function validateRule(expr, side) {
      if (expr.all || expr.any) {
        const children=expr.all || expr.any;
        if (!children.length) throw Error(`${side}: add a condition.`);
        children.forEach(child=>validateRule(child,side));return;
      }
      if (expr.not) { validateRule(expr.not,side);return; }
      if (!expr.field) throw Error(`${side}: choose an indicator or stored input.`);
      if (!expr.op) throw Error(`${side}: choose a comparison.`);
      if ('other_field' in expr && !expr.other_field) throw Error(`${side}: choose the other input to compare.`);
      if (!['available','missing'].includes(expr.op) && !('other_field' in expr) && (expr.value==='' || expr.value===undefined || (Array.isArray(expr.value)&&expr.value.some(v=>v==='')))) throw Error(`${side}: enter a comparison value.`);
      if (typeof expr.value==='number' && !Number.isFinite(expr.value)) throw Error(`${side}: enter a valid number.`);
    }
    config.branches.forEach(branch=>{validateRule(branch.when,branch.side);if(stageExpression(branch.when,'trigger')&&!stageExpression(branch.when,'activate'))throw Error(`${branch.side}: add at least one Activate condition after your Trigger conditions.`);});
    return config;
  }
  function setModel(config) {
    model = copy(config); $('strategy-name').value = model.id;
    $('fee').value = model.execution?.fee_bps_per_side ?? 4; $('slippage').value = model.execution?.slippage_bps_per_side ?? 2; $('capital').value = model.execution?.initial_capital ?? 100;
    $('intrabar-path').value=model.execution?.intrabar_path||'low_first';
    renderBranches(); remember();
  }
  function fieldSelect(selected, parent, changed) {
    const menu=node('details',undefined,parent,{class:'field-dropdown'});
    const identity='field-options-'+Math.random().toString(36).slice(2);
    const trigger=node('summary',undefined,menu,{role:'combobox','aria-label':'Choose condition field','aria-haspopup':'listbox','aria-expanded':'false','aria-controls':identity});
    const panel=node('div',undefined,menu,{class:'field-dropdown-panel'});
    const search=node('input',undefined,panel,{type:'search',placeholder:'Search indicators and stored inputs…','aria-label':'Search fields',autocomplete:'off'});
    const results=node('div',undefined,panel,{id:identity,role:'listbox','aria-label':'Available fields'});
    const note=node('small','',panel,{role:'status'});
    const availability=node('small','',parent);
    // The native value remains a change-event bridge for existing integrations.
    const select=node('select',undefined,parent,{'aria-label':'Condition field','aria-hidden':'true',tabindex:'-1'});select.hidden=true;
    node('option','Choose an indicator or input…',select,{value:''});
    if(selected)node('option',human(selected),select,{value:selected});
    function updateSelection(){
      if(selected&&![...select.options].some(o=>o.value===selected))node('option',human(selected),select,{value:selected});
      select.value=selected||'';trigger.textContent=selected?human(selected):'Choose an indicator or input…';
      const info=fieldInfo(selected);
      availability.textContent=selected&&!info?'This input is absent from the selected data.':info?.sample_present===0?'No values in this input sample. Check coverage before replay.':'';
    }
    function choose(value){selected=value;updateSelection();menu.open=false;changed(value);}
    function render(){
      results.replaceChildren();
      const normalize=text=>text.toLowerCase().replace(/previous/g,'prev').replace(/di\+/g,'di_plus').replace(/di[-−]/g,'di_minus').replaceAll('_',' ');
      const words=normalize(search.value).split(/\s+/).filter(Boolean);
      const found=fields().filter(f=>words.every(word=>normalize(f.id+' '+human(f.id)).includes(word)));
      let groupName,group;
      for(const f of found.slice(0,200)){
        if(f.group!==groupName){groupName=f.group;group=node('div',undefined,results,{role:'group','aria-label':groupName||'Inputs'});node('strong',groupName||'Inputs',group);}
        const option=button(human(f.id),group,()=>choose(f.id));option.setAttribute('role','option');option.setAttribute('aria-selected',String(f.id===selected));option.dataset.field=f.id;
        option.onkeydown=e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();const options=[...results.querySelectorAll('[role="option"]')],i=options.indexOf(option);options[(i+(e.key==='ArrowDown'?1:-1)+options.length)%options.length]?.focus();}};
      }
      note.textContent=found.length?`${found.length.toLocaleString()} matching inputs${found.length>200?' · showing 200; narrow your search':''}`:'No matching inputs. Try another name.';
    }
    search.oninput=render;
    search.onkeydown=e=>{if(e.key==='ArrowDown'){e.preventDefault();results.querySelector('[role="option"]')?.focus();}};
    menu.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();menu.open=false;trigger.focus();}});
    menu.ontoggle=()=>{
      trigger.setAttribute('aria-expanded',String(menu.open));
      if(menu.open&&menu.isConnected){
        for(const other of document.querySelectorAll('.field-dropdown[open]'))if(other!==menu)other.open=false;
        render();panel.style.left='0px';const overflow=panel.getBoundingClientRect().right-innerWidth+12;if(overflow>0)panel.style.left=-overflow+'px';search.focus();
      }
    };
    select.onchange=()=>choose(select.value);updateSelection();return select;
  }
  function defaultLeaf() { return {field:'',op:'',value:''}; }
  function expressionText(expr) {
    if (expr.all || expr.any) return '(' + (expr.all || expr.any).map(expressionText).join(expr.all ? ' AND ' : ' OR ') + ')';
    if (expr.not) return 'NOT ' + expressionText(expr.not);
    if (!expr.field || !expr.op) return 'Choose an indicator, comparison and value.';
    const ops = {eq: 'equals', ne: 'does not equal', gt: '>', gte: '≥', lt: '<', lte: '≤', in: 'is one of', available: 'is available', missing: 'is missing'};
    return `${expr.stage==='trigger'?'[Trigger] ':'[Activate] '}${human(expr.field)}${expr.lag ? ' ' + expr.lag + ' candles ago' : ''} ${ops[expr.op]} ${expr.other_field ? human(expr.other_field) + (expr.other_lag ? ' ' + expr.other_lag + ' candles ago' : '') : expr.value === undefined ? '' : Array.isArray(expr.value) ? expr.value.join(', ') : String(expr.value)}`;
  }
  function renderExpression(expr, parent, replace, remove, preview) {
    const changed = () => { preview(); remember(); };
    const redraw = () => { renderBranches(); remember(); };
    if (expr.all || expr.any || expr.not) {
      const group = node('div', undefined, parent, {class: 'logic-group'}); const heading = node('div', undefined, group, {class: 'group-heading'});
      const select = node('select', undefined, heading, {'aria-label': 'Group logic'});
      for (const [v, t] of [['all', 'AND · all conditions'], ['any', 'OR · any condition'], ['not', 'NOT · inverse']]) node('option', t, select, {value: v});
      const key = expr.all ? 'all' : expr.any ? 'any' : 'not'; select.value = key;
      select.onchange = () => { const children = expr.all || expr.any || [expr.not]; replace(select.value === 'not' ? {not: children.length === 1 ? children[0] : {all: children}} : {[select.value]: key === 'not' ? [expr.not] : children}); redraw(); };
      if (key !== 'not') {
        button('+ Condition', heading, () => { expr[key].push(defaultLeaf()); redraw(); });
        button('+ AND group', heading, () => { expr[key].push({all: [defaultLeaf()]}); redraw(); });
        button('+ OR group', heading, () => { expr[key].push({any: [defaultLeaf()]}); redraw(); });
      }
      if (remove) button('Remove group', heading, () => { remove(); redraw(); });
      const children = key === 'not' ? [expr.not] : expr[key];
      children.forEach((child, index) => renderExpression(child, group, value => { if (key === 'not') expr.not = value; else children[index] = value; },
        key === 'not' ? null : () => { children.splice(index, 1); if (!children.length) children.push(defaultLeaf()); }, preview));
      return;
    }
    const row = node('div', undefined, parent, {class: 'predicate'});
    const stage=node('select',undefined,label('Condition role',row),{'aria-label':'Condition role'});
    node('option','Activate · fire the BUY/SELL',stage,{value:'activate'});node('option','Trigger · remember setup',stage,{value:'trigger'});stage.value=expr.stage||'activate';stage.onchange=()=>{expr.stage=stage.value;renderBranches();remember();};
    fieldSelect(expr.field, node('label', 'Input', row, {class: 'field'}), value => {
      expr.field = value; if (!('other_field' in expr) && expr.op !== 'in' && !['available', 'missing'].includes(expr.op)) {
        expr.value = '';
      } redraw();
    });
    const op = node('select', undefined, label('Comparison', row)); op.setAttribute('aria-label', 'Condition comparison');
    for (const [v, t] of [['eq', '= equals'], ['ne', '≠ not equal'], ['gt', '> greater than'], ['gte', '≥ at least'], ['lt', '< less than'], ['lte', '≤ at most'], ['in', 'One of'], ['available', 'Available'], ['missing', 'Missing']]) node('option', t, op, {value: v});
    if (!expr.op) node('option','Choose comparison…',op,{value:''});
    op.value = expr.op;
    op.onchange = () => {
      expr.op = op.value;
      if (['available', 'missing'].includes(expr.op)) { delete expr.value; delete expr.other_field; delete expr.other_lag; }
      else if (expr.op === 'in') { expr.value = Array.isArray(expr.value) ? expr.value : [expr.value ?? fieldInfo(expr.field)?.options[0] ?? '']; delete expr.other_field; delete expr.other_lag; }
      else if (!('other_field' in expr)) { expr.value = Array.isArray(expr.value) ? expr.value[0] : expr.value ?? ''; if (expr.value!=='' && ['gt','gte','lt','lte'].includes(expr.op)) expr.value = Number(expr.value); }
      redraw();
    };
    if (!['available', 'missing'].includes(expr.op)) {
      const mode = node('select', undefined, label('Compare with', row)); node('option', 'A value', mode, {value: 'literal'}); if (expr.op !== 'in') node('option', 'Another input', mode, {value: 'field'});
      mode.value = 'other_field' in expr ? 'field' : 'literal'; mode.onchange = () => { if (mode.value === 'field') { expr.other_field = ''; delete expr.value; } else { delete expr.other_field; delete expr.other_lag; expr.value = ''; } redraw(); };
      const operand = node('label', 'Value / input', row, {class: 'operand'});
      if ('other_field' in expr) {
        fieldSelect(expr.other_field, operand, value => { expr.other_field = value; changed(); });
        const lag = node('input', undefined, node('label', 'Other candle: 0=current, 1=previous, 2=two ago', row, {class: 'lag'}), {type: 'number', min: 0, max: 1000,'aria-label':'Other lag'}); lag.value = expr.other_lag || 0; lag.onchange = () => { expr.other_lag = Number(lag.value); changed(); };
      } else {
        const info = fieldInfo(expr.field); let value;
        if (info?.kind === 'boolean' && expr.op !== 'in') { value = node('select', undefined, operand); node('option','Choose a value…',value,{value:''}); node('option', 'true', value); node('option', 'false', value); value.value = String(expr.value); }
        else { value = node('input', undefined, operand, {type: 'text', 'aria-label': 'Condition value'}); value.value = Array.isArray(expr.value) ? expr.value.join(', ') : expr.value ?? ''; if (info?.options.length && expr.op !== 'in') { const id = 'options-' + Math.random().toString(36).slice(2); value.setAttribute('list', id); const dl = node('datalist', undefined, operand, {id}); info.options.forEach(v => node('option', String(v), dl, {value: String(v)})); } }
        value.onchange = () => {
          const convert = v => info?.kind === 'boolean' ? v === 'true' : info?.kind === 'number' || ['gt','gte','lt','lte'].includes(expr.op) ? Number(v) : v;
          expr.value = value.value.trim()==='' ? '' : expr.op === 'in' ? value.value.split(',').map(v => v.trim()===''?'':convert(v.trim())) : convert(value.value); changed();
        };
      }
    }
    const lag = node('input', undefined, node('label', 'Candle: 0=current, 1=previous, 2=two ago', row, {class: 'lag'}), {type: 'number', min: 0, max: 1000,'aria-label':'Lag (candles)'}); lag.value = expr.lag || 0; lag.onchange = () => { expr.lag = Number(lag.value); changed(); };
    button('Group AND', row, () => { replace({all: [copy(expr), defaultLeaf()]}); redraw(); });
    button('Group OR', row, () => { replace({any: [copy(expr), defaultLeaf()]}); redraw(); });
    if (remove) button('Remove', row, () => { remove(); redraw(); });
  }
  function renderBranches() {
    const root = $('branches-editor'); root.replaceChildren();
    model.branches.forEach((branch, index) => {
      const box = node('article', undefined, root, {class: 'branch ' + (branch.side === 'SELL' ? 'sell ' : '') + (branch.enabled === false ? 'disabled' : '')});
      const heading = node('div', undefined, box, {class: 'branch-heading'});
      const enabled = node('input', undefined, node('label', 'Include', heading, {class: 'enable'}), {type: 'checkbox'}); enabled.checked = branch.enabled !== false;
      enabled.onchange = () => { branch.enabled = enabled.checked; renderBranches(); remember(); };
      const name = node('input', undefined, node('label', branch.side==='BUY'?'Entry rule name':'Exit rule name', heading, {class: 'branch-name'})); name.value = branch.id; name.onchange = () => { branch.id = name.value.trim(); remember(); };
      const side = node('select', undefined, label('Signal', heading)); node('option', 'BUY', side); node('option', 'SELL', side); side.value = branch.side;
      side.onchange = () => { branch.side = side.value;if(branch.side==='BUY'){delete branch.action;delete branch.trail;delete branch.target_profit_pct;}renderBranches(); remember(); };
      if(branch.side==='SELL'){
        const action=node('select',undefined,label('Sell action',heading));node('option','SELL at next open',action,{value:'MARKET_SELL'});node('option','Trailing SELL',action,{value:'TRAILING_SELL'});node('option','Take profit',action,{value:'TAKE_PROFIT'});action.value=branch.action||'MARKET_SELL';
        action.onchange=()=>{branch.action=action.value;if(branch.action==='TRAILING_SELL')branch.trail=branch.trail||{distance_pct:.5,activation_profit_pct:1};else delete branch.trail;if(branch.action==='TAKE_PROFIT')branch.target_profit_pct=branch.target_profit_pct??1;else delete branch.target_profit_pct;renderBranches();remember();};
        if(branch.action==='TAKE_PROFIT'){const value=node('input',undefined,label('Take profit at net (%)',heading),{type:'number',min:.001,step:.1});value.value=branch.target_profit_pct??1;value.onchange=()=>{branch.target_profit_pct=Number(value.value);remember();};}
        if(branch.action==='TRAILING_SELL'){
          const activation=node('select',undefined,label('Trailing activation',heading),{'aria-label':'Trailing activation'});
          node('option','Profit threshold only · no indicator needed',activation,{value:'position'});node('option','Profit threshold + indicator conditions',activation,{value:'conditions'});
          activation.value=positionTrail(branch)?'position':'conditions';activation.onchange=()=>{branch.condition_mode=activation.value;renderBranches();remember();};
          branch.trail=branch.trail||{distance_pct:.5,activation_profit_pct:1};
          for(const [key,title,min]of[['activation_profit_pct','Activate at net profit (%)',0],['distance_pct','Trail below highest since entry (%)',.001]]){const value=node('input',undefined,label(title,heading),{type:'number',min,step:.1});value.value=branch.trail[key];value.onchange=()=>{branch.trail[key]=Number(value.value);remember();};}
        }
      }
      button('Move up', heading, () => { if (index) { [model.branches[index-1], model.branches[index]] = [branch, model.branches[index-1]]; renderBranches(); remember(); } }).disabled = !index;
      button('Duplicate', heading, () => { const b = copy(branch); b.id += '_copy_' + Date.now().toString(36); model.branches.splice(index+1, 0, b); renderBranches(); remember(); });
      button('Delete branch', heading, () => { model.branches.splice(index, 1); renderBranches(); remember(); });
      if(!positionTrail(branch)&&stageExpression(branch.when,'trigger')){
        const timing=node('select',undefined,label('Activate after trigger',heading),{'aria-label':'Activation timing'});node('option','Same or a later candle close',timing,{value:'same_or_later'});node('option','Later candle close only',timing,{value:'later'});timing.value=branch.activation_timing||'same_or_later';timing.onchange=()=>{branch.activation_timing=timing.value;remember();};
      }
      const preview = node('p', undefined, box, {class: 'rule-preview'}); const refresh = () => {const trigger=stageExpression(branch.when,'trigger'),activation=stageExpression(branch.when,'activate');preview.textContent = positionTrail(branch)?'While a position is open, arm the trailing exit at the profit threshold above. No indicator condition is required.':trigger?'Trigger: '+expressionText(trigger)+' → remember setup → Activate: '+(activation?expressionText(activation):'add an Activate condition'):expressionText(branch.when); }; refresh();
      if(positionTrail(branch))return;
      const details=node('details',undefined,box);node('summary','Edit conditions',details);details.open=branch.expanded??index===0;details.ontoggle=()=>{branch.expanded=details.open;remember();};renderExpression(branch.when, details, value => { branch.when = value; }, null, refresh);
    });
  }
  function renderFields() {
    const root = $('report-fields'), search = $('report-field-search').value.toLowerCase(); root.replaceChildren();
    const matching=[...fields(),...[...reportFields].filter(id=>!fieldInfo(id)).map(id=>({id,absent:true}))].filter(f => (f.id + ' ' + human(f.id)).toLowerCase().includes(search));
    node('p',`${matching.length.toLocaleString()} fields match · showing up to 200; type to find any stored field.`,root,{class:'muted compact'});
    matching.slice(0,200).forEach(f => {
      const l = node('label', undefined, root, {class: 'field-choice'}), c = node('input', undefined, l, {type: 'checkbox', value: f.id}); c.checked = reportFields.has(f.id);
      node('span', human(f.id)+(f.absent?' (not in this input export)':''), l); c.onchange = () => { if (c.checked) reportFields.add(f.id); else reportFields.delete(f.id); remember(); };
    });
  }
  function selectOptions(select, entries, selected, none) {
    select.replaceChildren(); if (none !== undefined) node('option', none, select, {value: ''});
    entries.forEach(([value, text]) => node('option', text, select, {value}));
    if ([...select.options].some(o => o.value === selected)) select.value = selected;
  }
  async function refreshCatalog() {
    const input = $('input-source').value, preset = $('strategy-preset').value, baseline = $('baseline-preset').value, report = $('saved-report').value;
    catalog = await api('/api/catalog');
    selectOptions($('input-source'), catalog.inputs.map(i => [i.id, i.name]), input || catalog.default_input);
    const oldSymbols=new Set([...$('memory-coins').selectedOptions].map(o=>o.value));
    selectOptions($('memory-symbol'),(catalog.memory?.symbols||[]).map(s=>[s,s]),$('memory-symbol').value||'BTCUSDT');
    selectOptions($('memory-timeframe'),(catalog.memory?.timeframes||[]).map(s=>[s,s]),$('memory-timeframe').value||'15m');
    selectOptions($('memory-coins'),(catalog.memory?.symbols||[]).map(s=>[s,s]));for(const o of $('memory-coins').options)o.selected=oldSymbols.has(o.value);
    $('memory-universe').textContent=catalog.memory?.error||`${catalog.memory?.symbols.length||0} stored coins · ${catalog.memory?.feature_columns||0} feature columns · ${catalog.memory?.adcn_columns||0} ADCN columns`;
    const configs = catalog.configurations.map(c => [c.key, c.config.id + ' · ' + c.key.slice(0,6)]);
    selectOptions($('strategy-preset'), configs, preset, 'Choose a saved strategy (optional)');
    $('load-preset').disabled=!$('strategy-preset').value;
    selectOptions($('baseline-preset'), configs, baseline, 'No comparison');
    selectOptions($('saved-report'), catalog.reports.map(r => [r.id, r.name]), report);
  }
  async function loadInput() {
    const token = ++inputToken; $('run-strategy').disabled = true; $('input-status').textContent = 'Reading selected input…';
    const result = await api('/api/input?id=' + encodeURIComponent($('input-source').value)); if (token !== inputToken) return;
    metadata = result; $('input-status').textContent = `${result.symbol} · ${result.timeframe} · ${result.candles.toLocaleString()} candles · ${new Date(result.first).toISOString().slice(0,10)} to ${new Date(result.last).toISOString().slice(0,10)} · ${result.feature_columns} stored feature columns`;
    $('input-heading').textContent = `${result.symbol} · ${result.timeframe} · SPOT RESEARCH`;
    $('memory-batch').hidden=result.mode!=='memory';
    if(result.mode==='memory'){$('memory-symbol').value=result.symbol;$('memory-timeframe').value=result.timeframe;if(!$('memory-coins').selectedOptions.length)for(const o of $('memory-coins').options)o.selected=o.value===result.symbol;}
    $('risk-scope').textContent = result.risk_budget_pct == null ? 'Legacy snapshot: original signal-rule replay, without the 0.5% stop. Choose a new spot research snapshot for the loss-budget replay.' : 'A 0.5% net loss budget is active from entry, including configured costs. Candle OHLC models stop touches; adverse opens can exceed the budget. SELL branches define your other exits.';
    if(currentReport && (currentReport.contract.source_id!==result.source_id || currentReport.contract.observed_as_of!==result.last)) {
      currentReport=currentReportId=null;$('report-area').replaceChildren();
      $('result-scope').textContent='Run a replay for this input, or explicitly open a saved report.';
      $('use-report-config').disabled=$('pin-baseline').disabled=true;$('download-report').hidden=$('download-html').hidden=true;
    }
    window.dispatchEvent(new CustomEvent('research-input', {detail: {id: $('input-source').value, metadata: result}}));
    const coverage = $('input-coverage'); coverage.replaceChildren(); node('p', result.note, coverage);
    const t = node('table', undefined, node('div', undefined, coverage, {class: 'scroll'})); let tr = node('tr', undefined, t); ['Context history',result.mode==='memory'?'Rows in recent preview':'Stored rows'].forEach(v=>node('th',v,tr));
    Object.entries(result.context_rows).forEach(([key,count]) => { const r=node('tr',undefined,t); node('td',key,r); node('td',count.toLocaleString(),r); });
    if (model) renderBranches(); renderFields(); $('run-strategy').disabled = running;
  }
  function download(value, name) { const url = URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})); const a=node('a',undefined,document.body,{href:url,download:name});a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000); }
  async function loadReport(id) {
    currentReport = await api('/api/report?id=' + encodeURIComponent(id)); currentReportId = id;
    StrategyReport.mount($('report-area'), currentReport);
    $('result-scope').textContent = `Showing ${currentReport.config.id} · ${currentReport.workspace?.input_name || 'frozen published input'} · ${currentReport.candles_scanned ?? currentReport.candles_evaluated} candles scanned. Changes in the editor take effect only when you run a replay.`;
    $('use-report-config').disabled = $('pin-baseline').disabled = false;
    for (const [key, format] of [['download-report','json'],['download-html','html']]) { $(key).hidden=false; $(key).href='/api/download?id='+encodeURIComponent(id)+'&format='+format; }
  }
  async function poll(id) {
    const job = await api('/api/job?id=' + encodeURIComponent(id)); $('run-status').textContent = job.stage + (job.total ? ` · ${job.complete.toLocaleString()} / ${job.total.toLocaleString()} candles` : '');
    $('run-progress').value = job.total ? job.complete/job.total*100 : 0;
    if(job.coins){const root=$('batch-results');root.replaceChildren();const t=node('table',undefined,root),head=node('tr',undefined,t);['Coin','Status','Closed trades','Win rate','Average net','Report'].forEach(v=>node('th',v,head));for(const coin of job.coins){const tr=node('tr',undefined,t);[coin.symbol,coin.error||coin.state,coin.summary?.closed??'—',coin.summary?.win_rate_pct==null?'—':coin.summary.win_rate_pct.toFixed(2)+'%',coin.summary?.mean_net_pct==null?'—':coin.summary.mean_net_pct.toFixed(3)+'%'].forEach(v=>node('td',String(v),tr));const cell=node('td',undefined,tr);if(coin.report_id)button('Open report',cell,guard(()=>loadReport(coin.report_id)));}}
    if (job.state === 'failed') throw Error(job.error);
    if (job.state === 'complete') { await refreshCatalog(); $('saved-report').value = job.report_id; await loadReport(job.report_id); return; }
    await new Promise(resolve => setTimeout(resolve, 600)); return poll(id);
  }
  $('strategy-preset').onchange=()=>{$('load-preset').disabled=!$('strategy-preset').value;};
  $('load-preset').onclick = guard(() => {
    const selected=catalog.configurations.find(c=>c.key===$('strategy-preset').value);
    if (!selected) throw Error('Choose a saved strategy first.');
    setModel(selected.config);$('strategy-status').textContent='Editable copy loaded: '+selected.config.id;
  });
  $('new-strategy').onclick=()=>{
    previousDraft={model:copy(model),reportFields:[...reportFields],baseline:$('baseline-preset').value};
    try { localStorage.setItem(previousDraftKey,JSON.stringify(previousDraft)); } catch (_) {}
    reportFields=new Set();$('baseline-preset').value='';$('strategy-preset').value='';$('load-preset').disabled=true;
    setModel(blankStrategy());renderFields();$('undo-new-strategy').hidden=false;
    $('strategy-status').textContent='New strategy · no preset conditions. Choose your BUY and SELL conditions below.';
    $('run-status').textContent='';error();$('strategy-name').focus();
    $('result-scope').textContent=currentReport?'Previous report remains below; run your new strategy to produce new results.':'';
  };
  $('undo-new-strategy').onclick=()=>{
    if(!previousDraft)return;
    reportFields=new Set(previousDraft.reportFields);$('baseline-preset').value=previousDraft.baseline;
    setModel(previousDraft.model);renderFields();previousDraft=null;$('undo-new-strategy').hidden=true;
    try { localStorage.removeItem(previousDraftKey); } catch (_) {}
    $('strategy-status').textContent='Previous draft restored.';
  };
  $('add-buy').onclick = () => { model.branches.push({id:'buy_branch_'+Date.now().toString(36),side:'BUY',when:{all:[defaultLeaf()]}});renderBranches();remember(); };
  $('add-sell').onclick = () => { model.branches.push({id:'sell_branch_'+Date.now().toString(36),side:'SELL',when:{all:[defaultLeaf()]}});renderBranches();remember(); };
  $('add-trailing-sell').onclick=()=>{model.branches.push({id:'trailing_sell_'+Date.now().toString(36),side:'SELL',action:'TRAILING_SELL',trail:{distance_pct:.5,activation_profit_pct:1},when:{all:[defaultLeaf()]}});renderBranches();remember();};
  $('load-memory').onclick=guard(async()=>{$('input-source').value=`memory:${$('memory-symbol').value}:${$('memory-timeframe').value}`;if(!$('input-source').value)throw Error('This coin/timeframe has no stored feature scope yet.');await loadInput();remember();});
  $('memory-all').onclick=()=>{for(const o of $('memory-coins').options)o.selected=true;remember();};
  $('memory-current').onclick=()=>{for(const o of $('memory-coins').options)o.selected=o.value===metadata?.symbol;remember();};
  $('memory-coins').onchange=remember;
  $('strategy-name').onchange = () => { model.id = $('strategy-name').value;remember(); };
  for (const id of ['fee','slippage','capital','intrabar-path']) $(id).onchange = () => { model.execution={fee_bps_per_side:Number($('fee').value),slippage_bps_per_side:Number($('slippage').value),initial_capital:Number($('capital').value),intrabar_path:$('intrabar-path').value};remember(); };
  $('save-config').onclick = guard(async () => { const saved=await api('/api/config',{config:configuration()});await refreshCatalog();$('strategy-preset').value=saved.key;$('run-status').textContent='Strategy saved. Previous versions are retained.'; });
  $('export-config').onclick = guard(() => download(configuration(), $('strategy-name').value.replace(/[^a-z0-9_-]/gi,'_')+'.json'));
  $('config-upload').onchange = guard(async e => { const file=e.target.files[0];if(file){const saved=await api('/api/config',{config:JSON.parse(await file.text())});await refreshCatalog();setModel(saved.config);$('strategy-preset').value=saved.key;} });
  $('input-source').onchange = guard(async()=>{await loadInput();remember();});$('refresh-input').onclick=guard(loadInput);for(const id of ['baseline-preset','replay-since','replay-until'])$(id).onchange=remember; $('report-field-search').oninput = renderFields;
  $('input-upload').onchange = guard(async e => { const file=e.target.files[0];if(!file)return;$('input-status').textContent='Importing row-source file…';const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));const uploaded=await api('/api/upload',{data:btoa(binary),name:file.name});await refreshCatalog();$('input-source').value=uploaded.id;await loadInput(); });
  $('load-report').onclick = guard(() => loadReport($('saved-report').value));
  $('use-report-config').onclick = guard(() => { setModel(currentReport.config);reportFields=new Set(currentReport.report_fields||[]);renderFields();for(const [id,key] of [['replay-since','since'],['replay-until','until']])$(id).value=currentReport.contract[key]===null?'':new Date(currentReport.contract[key]).toISOString().slice(0,16);$('strategy-title').scrollIntoView({behavior:'smooth'}); });
  $('pin-baseline').onclick = guard(async () => { const saved=await api('/api/config',{config:currentReport.config});await refreshCatalog();$('baseline-preset').value=saved.key;$('run-status').textContent='Report strategy selected as baseline. It will replay on the same inputs and costs as your next run.'; });
  $('run-strategy').onclick = guard(async () => {
    const config=configuration();const baseline=catalog.configurations.find(c=>c.key===$('baseline-preset').value)?.config;
    const date=id=>$(id).value?Date.parse($(id).value+'Z'):null;
    running=true;$('run-status').textContent='Starting replay…';$('run-strategy').disabled=true;$('run-progress').hidden=false;
    try { const body={config,baseline_config:baseline,input_id:$('input-source').value,since:date('replay-since'),until:date('replay-until'),report_fields:[...reportFields]};if(metadata.mode==='memory'){body.symbols=[...$('memory-coins').selectedOptions].map(o=>o.value);if(!body.symbols.length)throw Error('Select at least one coin to replay.');}$('batch-results').replaceChildren();const job=await api('/api/run',body);await poll(job.id); }
    finally { running=false;$('run-strategy').disabled=!metadata;$('run-progress').hidden=true; }
  });
  guard(async () => {
    await refreshCatalog();let draft;try{draft=JSON.parse(localStorage.getItem(draftKey));previousDraft=JSON.parse(localStorage.getItem(previousDraftKey));}catch(_){}
    $('undo-new-strategy').hidden=!previousDraft?.model;
    setModel(draft?.model || blankStrategy());
    $('strategy-status').textContent=draft?.model?'Your draft was restored. Use Create new strategy to start blank.':'New strategy · choose your BUY and SELL conditions below.';
    reportFields=new Set(draft?.reportFields || []);if(catalog.inputs.some(i=>i.id===draft?.inputId))$('input-source').value=draft.inputId;
    const requested = new URLSearchParams(location.search).get('input');
    if(requested){const id=requested==='default'?catalog.default_input:requested;if(catalog.inputs.some(i=>i.id===id))$('input-source').value=id;history.replaceState(null,'',location.pathname+location.hash);}
    if(catalog.configurations.some(c=>c.key===draft?.baselineKey))$('baseline-preset').value=draft.baselineKey;$('replay-since').value=draft?.since||'';$('replay-until').value=draft?.until||'';await loadInput();if(draft?.symbols?.length)for(const o of $('memory-coins').options)o.selected=draft.symbols.includes(o.value);remember();
  })();
})();
