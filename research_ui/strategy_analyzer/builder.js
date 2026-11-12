/* Browser configuration and replay orchestration. Rule evaluation stays in Python. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const copy = value => JSON.parse(JSON.stringify(value));
  let catalog, metadata, model, currentReport, currentReportId, inputToken = 0, running = false;
  let reportFields = new Set();
  const draftKey = 'btc-hour-strategy-workspace-draft-v1';
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
    try { localStorage.setItem(draftKey, JSON.stringify({model, reportFields: [...reportFields],inputId:$('input-source').value,baselineKey:$('baseline-preset').value,since:$('replay-since').value,until:$('replay-until').value})); } catch (_) { /* Downloads remain available if storage is unavailable. */ }
  }
  function configuration() {
    const config = {version: 'btc-hour-strategy-analyzer-v1', id: $('strategy-name').value.trim(),
      execution: {fee_bps_per_side: Number($('fee').value), slippage_bps_per_side: Number($('slippage').value), initial_capital: Number($('capital').value)},
      branches: model.branches.filter(b => b.enabled !== false).map(({id, side, when}) => ({id, side, when: copy(when)}))};
    if (!config.id) throw Error('Give your strategy a name.');
    if (!config.branches.some(b => b.side === 'BUY') || !config.branches.some(b => b.side === 'SELL')) throw Error('Enable at least one BUY and one SELL branch.');
    return config;
  }
  function setModel(config) {
    model = copy(config); $('strategy-name').value = model.id;
    $('fee').value = model.execution?.fee_bps_per_side ?? 4; $('slippage').value = model.execution?.slippage_bps_per_side ?? 2; $('capital').value = model.execution?.initial_capital ?? 100;
    renderBranches(); remember();
  }
  function fieldSelect(selected, parent, changed) {
    const select = node('select', undefined, parent); select.setAttribute('aria-label', 'Condition field');
    const grouped = new Map();
    for (const info of fields()) { if (!grouped.has(info.group)) grouped.set(info.group, []); grouped.get(info.group).push(info); }
    if (selected && !fieldInfo(selected)) node('option', human(selected) + ' · absent from selected input', select, {value: selected});
    for (const [group, infos] of grouped) { const optgroup = node('optgroup', undefined, select, {label: group}); for (const info of infos) node('option', human(info.id), optgroup, {value: info.id}); }
    select.value = selected; select.onchange = () => changed(select.value); return select;
  }
  function defaultLeaf() { return {field: 'di.abs_spread', op: 'gte', value: 10}; }
  function expressionText(expr) {
    if (expr.all || expr.any) return '(' + (expr.all || expr.any).map(expressionText).join(expr.all ? ' AND ' : ' OR ') + ')';
    if (expr.not) return 'NOT ' + expressionText(expr.not);
    const ops = {eq: 'equals', ne: 'does not equal', gt: '>', gte: '≥', lt: '<', lte: '≤', in: 'is one of', available: 'is available', missing: 'is missing'};
    return `${human(expr.field)}${expr.lag ? ' ' + expr.lag + ' candles ago' : ''} ${ops[expr.op]} ${expr.other_field ? human(expr.other_field) + (expr.other_lag ? ' ' + expr.other_lag + ' candles ago' : '') : expr.value === undefined ? '' : Array.isArray(expr.value) ? expr.value.join(', ') : String(expr.value)}`;
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
    fieldSelect(expr.field, node('label', 'Input', row, {class: 'field'}), value => {
      expr.field = value; if (!('other_field' in expr) && expr.op !== 'in' && !['available', 'missing'].includes(expr.op)) {
        const info = fieldInfo(value); expr.value = info?.kind === 'boolean' ? true : info?.kind === 'number' ? 0 : info?.options[0] ?? '';
      } redraw();
    });
    const op = node('select', undefined, label('Comparison', row)); op.setAttribute('aria-label', 'Condition comparison');
    for (const [v, t] of [['eq', '= equals'], ['ne', '≠ not equal'], ['gt', '> greater than'], ['gte', '≥ at least'], ['lt', '< less than'], ['lte', '≤ at most'], ['in', 'One of'], ['available', 'Available'], ['missing', 'Missing']]) node('option', t, op, {value: v});
    op.value = expr.op;
    op.onchange = () => {
      expr.op = op.value;
      if (['available', 'missing'].includes(expr.op)) { delete expr.value; delete expr.other_field; delete expr.other_lag; }
      else if (expr.op === 'in') { expr.value = Array.isArray(expr.value) ? expr.value : [expr.value ?? fieldInfo(expr.field)?.options[0] ?? '']; delete expr.other_field; delete expr.other_lag; }
      else if (!('other_field' in expr)) { expr.value = Array.isArray(expr.value) ? expr.value[0] : expr.value ?? 0; if (['gt','gte','lt','lte'].includes(expr.op)) expr.value = Number(expr.value) || 0; }
      redraw();
    };
    if (!['available', 'missing'].includes(expr.op)) {
      const mode = node('select', undefined, label('Compare with', row)); node('option', 'A value', mode, {value: 'literal'}); if (expr.op !== 'in') node('option', 'Another input', mode, {value: 'field'});
      mode.value = expr.other_field ? 'field' : 'literal'; mode.onchange = () => { if (mode.value === 'field') { expr.other_field = 'feature.ema50'; delete expr.value; } else { delete expr.other_field; delete expr.other_lag; expr.value = fieldInfo(expr.field)?.kind === 'number' ? 0 : ''; } redraw(); };
      const operand = node('label', 'Value / input', row, {class: 'operand'});
      if (expr.other_field) {
        fieldSelect(expr.other_field, operand, value => { expr.other_field = value; changed(); });
        const lag = node('input', undefined, node('label', 'Other lag', row, {class: 'lag'}), {type: 'number', min: 0, max: 1000}); lag.value = expr.other_lag || 0; lag.onchange = () => { expr.other_lag = Number(lag.value); changed(); };
      } else {
        const info = fieldInfo(expr.field); let value;
        if (info?.kind === 'boolean' && expr.op !== 'in') { value = node('select', undefined, operand); node('option', 'true', value); node('option', 'false', value); value.value = String(expr.value); }
        else { value = node('input', undefined, operand, {type: 'text', 'aria-label': 'Condition value'}); value.value = Array.isArray(expr.value) ? expr.value.join(', ') : expr.value ?? ''; if (info?.options.length && expr.op !== 'in') { const id = 'options-' + Math.random().toString(36).slice(2); value.setAttribute('list', id); const dl = node('datalist', undefined, operand, {id}); info.options.forEach(v => node('option', String(v), dl, {value: String(v)})); } }
        value.onchange = () => {
          const convert = v => info?.kind === 'boolean' ? v === 'true' : info?.kind === 'number' || ['gt','gte','lt','lte'].includes(expr.op) ? Number(v) : v;
          expr.value = expr.op === 'in' ? value.value.split(',').map(v => convert(v.trim())) : convert(value.value); changed();
        };
      }
    }
    const lag = node('input', undefined, node('label', 'Lag (candles)', row, {class: 'lag'}), {type: 'number', min: 0, max: 1000}); lag.value = expr.lag || 0; lag.onchange = () => { expr.lag = Number(lag.value); changed(); };
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
      const name = node('input', undefined, node('label', 'Branch name', heading, {class: 'branch-name'})); name.value = branch.id; name.onchange = () => { branch.id = name.value.trim(); remember(); };
      const side = node('select', undefined, label('Signal', heading)); node('option', 'BUY', side); node('option', 'SELL', side); side.value = branch.side;
      side.onchange = () => { branch.side = side.value; renderBranches(); remember(); };
      button('Move up', heading, () => { if (index) { [model.branches[index-1], model.branches[index]] = [branch, model.branches[index-1]]; renderBranches(); remember(); } }).disabled = !index;
      button('Duplicate', heading, () => { const b = copy(branch); b.id += '_copy_' + Date.now().toString(36); model.branches.splice(index+1, 0, b); renderBranches(); remember(); });
      button('Delete branch', heading, () => { model.branches.splice(index, 1); renderBranches(); remember(); });
      const preview = node('p', undefined, box, {class: 'rule-preview'}); const refresh = () => { preview.textContent = expressionText(branch.when); }; refresh();
      const details=node('details',undefined,box);node('summary','Edit conditions',details);details.open=branch.expanded??index===0;details.ontoggle=()=>{branch.expanded=details.open;remember();};renderExpression(branch.when, details, value => { branch.when = value; }, null, refresh);
    });
  }
  function renderFields() {
    const root = $('report-fields'), search = $('report-field-search').value.toLowerCase(); root.replaceChildren();
    [...fields(),...[...reportFields].filter(id=>!fieldInfo(id)).map(id=>({id,absent:true}))].filter(f => (f.id + ' ' + human(f.id)).toLowerCase().includes(search)).forEach(f => {
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
    const configs = catalog.configurations.map(c => [c.key, c.config.id + ' · ' + c.key.slice(0,6)]);
    selectOptions($('strategy-preset'), configs, preset || catalog.configurations.find(c => c.config.id === 'multi_branch_v1')?.key);
    selectOptions($('baseline-preset'), configs, baseline, 'No comparison');
    selectOptions($('saved-report'), catalog.reports.map(r => [r.id, r.name]), report);
  }
  async function loadInput() {
    const token = ++inputToken; $('run-strategy').disabled = true; $('input-status').textContent = 'Reading selected input…';
    const result = await api('/api/input?id=' + encodeURIComponent($('input-source').value)); if (token !== inputToken) return;
    metadata = result; $('input-status').textContent = `${result.symbol} · ${result.timeframe} · ${result.candles.toLocaleString()} candles · ${new Date(result.first).toISOString().slice(0,10)} to ${new Date(result.last).toISOString().slice(0,10)} · ${result.feature_columns} stored feature columns`;
    const coverage = $('input-coverage'); coverage.replaceChildren(); node('p', result.note, coverage);
    const t = node('table', undefined, node('div', undefined, coverage, {class: 'scroll'})); let tr = node('tr', undefined, t); ['Context history','Stored rows'].forEach(v=>node('th',v,tr));
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
    if (job.state === 'failed') throw Error(job.error);
    if (job.state === 'complete') { await refreshCatalog(); $('saved-report').value = job.report_id; await loadReport(job.report_id); return; }
    await new Promise(resolve => setTimeout(resolve, 600)); return poll(id);
  }
  $('load-preset').onclick = guard(() => { setModel(catalog.configurations.find(c => c.key === $('strategy-preset').value).config); });
  $('add-buy').onclick = () => { model.branches.push({id:'buy_branch_'+Date.now().toString(36),side:'BUY',when:{all:[defaultLeaf()]}});renderBranches();remember(); };
  $('add-sell').onclick = () => { model.branches.push({id:'sell_branch_'+Date.now().toString(36),side:'SELL',when:{all:[defaultLeaf()]}});renderBranches();remember(); };
  $('strategy-name').onchange = () => { model.id = $('strategy-name').value;remember(); };
  for (const id of ['fee','slippage','capital']) $(id).onchange = () => { model.execution=configuration().execution;remember(); };
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
    try { const job=await api('/api/run',{config,baseline_config:baseline,input_id:$('input-source').value,since:date('replay-since'),until:date('replay-until'),report_fields:[...reportFields]});await poll(job.id); }
    finally { running=false;$('run-strategy').disabled=!metadata;$('run-progress').hidden=true; }
  });
  guard(async () => {
    await refreshCatalog();let draft;try{draft=JSON.parse(localStorage.getItem(draftKey));}catch(_){}
    setModel(draft?.model || catalog.configurations.find(c=>c.key===$('strategy-preset').value)?.config || {version:'btc-hour-strategy-analyzer-v1',id:'My strategy',branches:[]});
    reportFields=new Set(draft?.reportFields || []);if(catalog.inputs.some(i=>i.id===draft?.inputId))$('input-source').value=draft.inputId;if(catalog.configurations.some(c=>c.key===draft?.baselineKey))$('baseline-preset').value=draft.baselineKey;$('replay-since').value=draft?.since||'';$('replay-until').value=draft?.until||'';await loadInput();remember();if(catalog.reports.length)await loadReport($('saved-report').value);
  })();
})();
