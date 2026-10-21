import {formatValue} from '../../web_root/value_format.js';
export const name='candle_details';
let box, cache, hoverTime=null, positions=new Map();
function render(){
    if(!box || !cache)return;
    const bars=cache.renderBars||cache.bars||[];
    const index=hoverTime===null?bars.length-1:(positions.get(hoverTime)??bars.length-1);
    const bar=bars[index];
    if(!bar){box.textContent='Waiting for candle data…';return;}
    const candle=bar.client, previous=bars[index-1];
    const change=previous?.client.close?((candle.close-previous.client.close)/previous.client.close)*100:null;
    box.replaceChildren();
    const title=document.createElement('strong');title.textContent=`${bar.symbol||cache.symbol} · ${bar.interval||cache.timeframe}`;title.title=`${bar.provisional?'Live':'Closed'} · ${new Date(bar.open_time).toLocaleString()}`;box.append(title);
    const list=document.createElement('dl');
    for(const [label,n] of [['Open',candle.open],['High',candle.high],['Low',candle.low],['Close',candle.close],['Volume',candle.volume],['Change %',change]]){
        const term=document.createElement('dt'),value=document.createElement('dd');term.textContent=({Open:'O',High:'H',Low:'L',Close:'C',Volume:'Vol','Change %':'Δ%'})[label];term.title=label;value.textContent=formatValue(n,`client.${label.toLowerCase()}`)+(label==='Change %' && n!==null?'%':'');list.append(term,value);
    }box.append(list);
}
export function mount(chart){
    box=document.createElement('section');box.id='candle-details';box.setAttribute('aria-label','Candle details');document.getElementById('chart').append(box);
    chart.subscribeCrosshairMove(event=>{hoverTime=typeof event.time==='number'?event.time:null;render();});
}
export function update(chart,data){cache=data;positions=new Map((data.renderBars||data.bars||[]).map((bar,index)=>[bar.time,index]));render();}
export function updateLive(chart,bar){if(cache){cache={...cache,bars:window.DataCache.renderBars,renderBars:window.DataCache.renderBars};positions.set(bar.time,cache.bars.length-1);render();}}
