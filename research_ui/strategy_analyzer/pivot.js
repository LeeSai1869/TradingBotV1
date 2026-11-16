/* Historical reference labels, chart inspection and matched feature comparisons. */
(() => {
  'use strict';
  const $ = id => document.getElementById('pivot-' + id);
  const node = (tag, text, parent) => { const n=document.createElement(tag);if(text!==undefined)n.textContent=text;parent?.append(n);return n; };
  const human = name => name.replaceAll('_',' ');
  const fmt = v => typeof v==='number' && Number.isFinite(v) ? v.toLocaleString('en-GB',{maximumFractionDigits:4}) : '—';
  const date = ms => new Date(ms).toLocaleString('en-GB',{timeZone:'Asia/Karachi',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})+' PKT';
  const dateInput = ms => new Date(ms+5*3600000).toISOString().slice(0,16);
  let input, epoch=0, compareToken=0, chartToken=0, page=0, packet, center, busy=false;
  let priceChart, featureChart, candles, line, markers, sync=false;
  let byTime=new Map();
  const fail = e => { $('status').textContent=e.message; };
  async function api(path, params) {
    const response=await fetch(path+'?'+new URLSearchParams(params));const data=await response.json();
    if(!response.ok)throw Error(data.error||'Research request failed');return data;
  }
  function table(parent, headers, rows) {
    parent.replaceChildren();const t=node('table',undefined,parent),h=node('tr',undefined,node('thead',undefined,t));
    headers.forEach(v=>node('th',v,h));const b=node('tbody',undefined,t);
    rows.forEach(values=>{const r=node('tr',undefined,b);values.forEach(v=>{const c=node('td',undefined,r);if(v instanceof Node)c.append(v);else c.textContent=String(v);});});
  }
  function charts() {
    if(priceChart)return;
    const options={layout:{background:{color:'#142032'},textColor:'#a6b7ca'},grid:{vertLines:{color:'#253347'},horzLines:{color:'#253347'}},
      localization:{timeFormatter:t=>date(Number(t)*1000)},timeScale:{timeVisible:true,secondsVisible:false,tickMarkFormatter:t=>new Date(Number(t)*1000).toLocaleString('en-GB',{timeZone:'Asia/Karachi',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})}};
    priceChart=LightweightCharts.createChart($('price-chart'),{...options,width:$('price-chart').clientWidth,height:360});
    featureChart=LightweightCharts.createChart($('feature-chart'),{...options,width:$('feature-chart').clientWidth,height:150});
    candles=priceChart.addSeries(LightweightCharts.CandlestickSeries,{upColor:'#62ddb2',downColor:'#ff929c',wickUpColor:'#62ddb2',wickDownColor:'#ff929c',borderVisible:false,priceLineVisible:false});
    line=featureChart.addSeries(LightweightCharts.LineSeries,{color:'#9ac6ff',lineWidth:2,priceLineVisible:false});
    markers=LightweightCharts.createSeriesMarkers(candles,[]);
    for(const [a,b] of [[priceChart,featureChart],[featureChart,priceChart]]) {
      a.timeScale().subscribeVisibleLogicalRangeChange(range=>{if(sync||!range)return;sync=true;try{b.timeScale().setVisibleLogicalRange(range);}finally{sync=false;}});
      a.subscribeClick(param=>{if(param.time!==undefined)inspect(Number(param.time));});
    }
    const resize=new ResizeObserver(()=>{priceChart.applyOptions({width:$('price-chart').clientWidth});featureChart.applyOptions({width:$('feature-chart').clientWidth});});
    resize.observe($('price-chart'));resize.observe($('feature-chart'));
  }
  function inspect(time) {
    const bar=byTime.get(time);if(!bar)return;
    const ctx=bar.context;
    $('readout').textContent=`${date(time*1000)} · O ${fmt(bar.open)} H ${fmt(bar.high)} L ${fmt(bar.low)} C ${fmt(bar.close)} · ${human(packet.feature)} ${fmt(bar.feature)} · Regime ${ctx[0]} ${ctx[1]} · Trend ${ctx[2]}`;
    table($('candle-values'),['Stored feature','Value'],Object.entries(bar.features).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>[human(k),typeof v==='number'?fmt(v):String(v??'—')]));
  }
  async function loadChart(at=center) {
    if(!input)return;
    const token=++chartToken,version=epoch;
    const params={id:input.id,feature:$('feature').value};if(at!=null)params.center=String(at);
    const data=await api('/api/chart',params);if(token!==chartToken||version!==epoch)return;
    packet=data;center=data.center;charts();byTime=new Map(data.bars.map(b=>[b.time,b]));
    const last=data.bars.at(-1)?.close||1,precision=last<10?6:last<1000?4:2;
    candles.applyOptions({priceFormat:{type:'price',precision,minMove:10**(-precision)}});
    candles.setData(data.bars.map(({time,open,high,low,close})=>({time,open,high,low,close})));
    line.setData(data.bars.map(b=>b.feature==null?{time:b.time}:{time:b.time,value:b.feature}));
    markers.setMarkers(data.markers.map(({known_time,...m})=>m));
    priceChart.timeScale().fitContent();featureChart.timeScale().fitContent();
    $('date').value=dateInput(center);
    $('main-chart').href='http://localhost:8000/?'+new URLSearchParams({symbol:data.symbol,interval:data.timeframe,at:String(center)});
    const selected=data.bars.find(b=>b.time*1000===center)||data.bars.at(-1);if(selected)inspect(selected.time);
  }
  async function compare() {
    if(!input)return;
    const token=++compareToken,version=epoch;busy=true;$('compare').disabled=true;
    $('status').textContent='Comparing pivot properties with matched controls…';
    try {
      const params={id:input.id,side:$('side').value,control:$('control').value,regime:$('regime').value,trend:$('trend').value,offset:$('offset').value,page:String(page)};
      for(const name of ['since','until'])if($(name).value)params[name]=String(Date.parse($(name).value+'T00:00:00+05:00'));
      const data=await api('/api/discovery',params);
      if(token!==compareToken||version!==epoch)return;
      $('status').textContent=`${data.symbol} ${data.timeframe} · ${data.total_candles.toLocaleString()} candles · ${data.native_pivots.toLocaleString()} native pivots · selected side/condition: ${(data.labels.GE_1||0).toLocaleString()} ≥1% / ${(data.labels.LT_1||0).toLocaleString()} below 1% / ${(data.labels.CENSORED||0).toLocaleString()} censored · ${data.matched_pairs.toLocaleString()} matched pairs`;
      $('method').textContent=`${data.matching} ${data.timing} ${data.unmatched_targets.toLocaleString()} qualifying reference candles have no matched control. Snapshot through ${date(data.observed_as_of)}.`;
      const interval=s=>s.n?`${fmt(s.median)} [${fmt(s.p10)} – ${fmt(s.p90)}]`:'—';
      table($('differences'),['Feature','≥1% pivot median [10–90%]','Control median [10–90%]','Available pivot / control','Mean difference / pooled SD'],data.features.map(f=>{
        const button=node('button',human(f.feature));button.type='button';button.onclick=()=>{selectFeature(f.feature);loadChart().catch(fail);};
        return [button,interval(f.pivot),interval(f.control),`${f.pivot.n.toLocaleString()} / ${f.control.n.toLocaleString()}`,fmt(f.standardized_difference)];
      }));
      const coverage=s=>s.available?`${fmt(s.pct)}% (${s.count.toLocaleString()} / ${s.available.toLocaleString()})`:'—';
      table($('overlap'),['Condition','≥1% reference pivots','Matched controls'],data.overlap.map(f=>[`${human(f.feature)} ${f.op} ${f.threshold}`,coverage(f.pivot),coverage(f.control)]));
      table($('strata'),['Pivot outcome','Regime','Direction','Trend','Pivots'],data.strata.map(s=>[s.status,s.regime,s.regime_direction,s.trend,s.n.toLocaleString()]));
      table($('cases'),['Pivot origin (PKT)','Later confirmed (PKT)','Move to immediate opposite pivot','Outcome','Regime / Trend','Inspect'],data.cases.map(c=>{
        const button=node('button','Show on chart');button.type='button';button.onclick=()=>loadChart(c.pivot.origin_time).catch(fail);
        return [date(c.pivot.origin_time),date(c.pivot.known_time),fmt(c.move_pct)+(c.move_pct==null?'':'%'),c.status,`${c.context[0]} ${c.context[1]} / ${c.context[2]}`,button];
      }));
      const pages=Math.max(1,Math.ceil(data.case_count/25));$('page').textContent=`Page ${page+1} of ${pages}`;
      $('prev').disabled=page===0;$('next').disabled=page+1>=pages;
    } finally {if(token===compareToken){busy=false;$('compare').disabled=false;}}
  }
  function selectFeature(name) {
    if(![...$('feature').options].some(o=>o.value===name)){const o=node('option',human(name),$('feature'));o.value=name;}
    $('feature').value=name;
  }
  window.addEventListener('research-input',event=>{
    input=event.detail;epoch++;page=0;center=null;
    $('method').textContent='';$('readout').textContent='';
    for(const id of ['differences','overlap','strata','cases','candle-values'])$(id).replaceChildren();
    if(candles){candles.setData([]);line.setData([]);markers.setMarkers([]);}
    loadChart().catch(fail);if(input.metadata.mode==='memory')$('status').textContent='Memory chart ready to load. Choose conditions and press Compare properties to scan historical pivots.';else compare().catch(fail);
  });
  $('compare').onclick=()=>{page=0;compare().catch(fail);};
  for(const id of ['side','control','regime','trend','offset','since','until'])$(id).onchange=()=>{page=0;compare().catch(fail);};
  $('feature').onchange=()=>loadChart().catch(fail);
  $('jump').onclick=()=>{const at=Date.parse($('date').value+':00+05:00');if(Number.isFinite(at))loadChart(at).catch(fail);};
  $('older').onclick=()=>{if(packet)loadChart(Math.max(packet.first,center-160*packet.step)).catch(fail);};
  $('newer').onclick=()=>{if(packet)loadChart(Math.min(packet.last,center+160*packet.step)).catch(fail);};
  $('latest').onclick=()=>{center=null;loadChart().catch(fail);};
  $('prev').onclick=()=>{if(page>0&&!busy){page--;compare().catch(fail);}};
  $('next').onclick=()=>{if(!busy){page++;compare().catch(fail);}};
})();
