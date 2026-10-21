export const name='candle_details';
let box, cache, hoverTime=null, positions=new Map();
const format=n=>Number.isFinite(n)?new Intl.NumberFormat(undefined,{maximumSignificantDigits:9}).format(n):'—';
function render(){
    if(!box || !cache)return;
    const bars=cache.renderBars||cache.bars||[];
    const index=hoverTime===null?bars.length-1:(positions.get(hoverTime)??bars.length-1);
    const bar=bars[index];
    if(!bar){box.textContent='Waiting for candle data…';return;}
    const candle=bar.client, previous=bars[index-1];
    const change=previous?.client.close?((candle.close-previous.client.close)/previous.client.close)*100:null;
    box.replaceChildren();
    const title=document.createElement('strong');title.textContent=`${bar.symbol||cache.symbol} · ${bar.interval||cache.timeframe} · ${bar.provisional?'Live':'Closed'}`;box.append(title);
    const time=document.createElement('div');time.textContent=new Date(bar.open_time).toLocaleString();box.append(time);
    const list=document.createElement('dl');
    for(const [label,n] of [['Open',candle.open],['High',candle.high],['Low',candle.low],['Close',candle.close],['Volume',candle.volume],['Change %',change]]){
        const term=document.createElement('dt'),value=document.createElement('dd');term.textContent=label;value.textContent=format(n)+(label==='Change %' && n!==null?'%':'');list.append(term,value);
    }box.append(list);
}
export function mount(chart){
    box=document.createElement('section');box.id='candle-details';box.setAttribute('aria-label','Candle details');document.getElementById('chart').append(box);
    const place=()=>{
        const pane=chart.panes()[0]?.getHTMLElement();if(!pane)return;
        const bounds=pane.getBoundingClientRect(), outer=document.getElementById('chart').getBoundingClientRect();
        const hud=document.getElementById('chart-hud');
        const belowHud=hud && !hud.hidden && hud.dataset.position==='top-left';
        box.style.top=Math.max(12,belowHud?bounds.bottom-outer.top-box.offsetHeight-8:12)+'px';box.style.bottom='auto';
    };
    new ResizeObserver(place).observe(document.getElementById('chart'));
    const pane=chart.panes()[0]?.getHTMLElement();if(pane)new ResizeObserver(place).observe(pane);
    window.addEventListener('chart-settings-change',()=>requestAnimationFrame(place));
    requestAnimationFrame(place);
    chart.subscribeCrosshairMove(event=>{hoverTime=typeof event.time==='number'?event.time:null;render();});
}
export function update(chart,data){cache=data;positions=new Map((data.renderBars||data.bars||[]).map((bar,index)=>[bar.time,index]));render();}
export function updateLive(chart,bar){if(cache){cache={...cache,bars:window.DataCache.renderBars,renderBars:window.DataCache.renderBars};positions.set(bar.time,cache.bars.length-1);render();}}
