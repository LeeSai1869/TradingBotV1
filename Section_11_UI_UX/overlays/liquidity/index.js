// Observed perpetual depth has its own market identity and availability clock.
// Draw only on actual chart times; no synthetic pre-collection heatmap/history.
import {getSeries} from '../candles/index.js';
export const name='liquidity';
let primitive,status,tooltip,bookTable,snapshot=null,expiryTimer=null;
const keys=['liquidity_bids','liquidity_asks','liquidity_heatmap'];
const styles=()=>window.Composer?.config.featureStyles||{};
const staleMs=10000;
export function fresh(snapshot,now=Date.now()){
    const latest=snapshot?.latest;
    return snapshot?.status==='live'&&latest&&now>=latest.book_received_ms&&now-latest.book_received_ms<=staleMs&&now>=latest.available_ms&&now-latest.available_ms<=staleMs?latest:null;
}
export function currentBookVisible(sample,bars,following=true,range=null){
    const last=bars.at(-1);if(!sample||following===false||!last)return false;
    if(range&&typeof range.from==='number'&&(last.time<range.from||last.time>range.to))return false;
    const duration=last.client?.close_time+1-last.open_time;
    const time=sample.sampled_ms??sample.available_ms;
    // A fresh book belongs at the latest edge throughout the next forming
    // interval, even if that provisional candle is disabled/unavailable.
    // Historical heatmap cells still require exact candle-time alignment.
    return Number.isFinite(duration)&&duration>0&&time>=last.open_time&&
        time<last.client.close_time+1+duration;
}
export function bookGutter(paneWidth,candleX,spacing){
    if(!Number.isFinite(candleX)||!Number.isFinite(spacing))return null;
    const left=Math.max(8,candleX+spacing/2+8),right=paneWidth-8;
    return right-left>=20?{left,right,origin:right,maxWidth:right-left}:null;
}
export function heatmapSpans(x,width,candleX,spacing){
    if(!(width>0))return [];
    if(!Number.isFinite(candleX))return [{x,width}];
    const left=candleX-spacing/2-1,right=candleX+spacing/2+1,end=x+width,result=[];
    if(x<left)result.push({x,width:Math.min(end,left)-x});
    if(end>right)result.push({x:Math.max(x,right),width:end-Math.max(x,right)});
    return result.filter(span=>span.width>0);
}
export function bandRows(sample,config){
    if(!sample?.observed||sample.market!=='usdt_perpetual')return [];
    return (sample.bands||[]).filter(b=>Number.isFinite(b.notional_usdt)&&b.notional_usdt>0&&b.high>b.low&&config[`liquidity_${b.side==='bid'?'bids':'asks'}`]?.visible);
}
export function bandLabel(band){return `${band.side==='bid'?'Resting bids':'Resting asks'} · ${band.low.toPrecision(7)}–${band.high.toPrecision(7)} · ${band.notional_usdt.toLocaleString(undefined,{maximumFractionDigits:0})} USDT · Binance perpetual${band.observed_ms?' · '+new Date(band.observed_ms).toLocaleTimeString():''}`;}
class Liquidity {
    attached({chart,series,requestUpdate}){
        Object.assign(this,{chart,series,requestUpdate});
        this.views=['heatmap','profile'].map(layer=>({zOrder:()=>layer==='heatmap'?'bottom':'top',renderer:()=>({draw:target=>this.draw(target,layer)})}));
    }
    detached(){this.chart=this.series=this.requestUpdate=null;}
    paneViews(){return this.views||[];}
    get hitboxes(){return [...(this.heatmapBoxes||[]),...(this.profileBoxes||[])];}
    xAt(ms){
        let lo=0,hi=this.bars.length;
        while(lo<hi){const mid=(lo+hi)>>1;if(this.bars[mid].open_time<=ms)lo=mid+1;else hi=mid;}
        const bar=this.bars[lo-1];if(!bar||ms>bar.client?.close_time+1)return null;
        const x=this.chart.timeScale().timeToCoordinate(bar.time);if(x===null)return null;
        const spacing=this.chart.timeScale().options().barSpacing;
        return x-spacing/2+spacing*(ms-bar.open_time)/(bar.client.close_time+1-bar.open_time);
    }
    draw(target,layer){
        if(!this.series||!snapshot)return;
        target.useMediaCoordinateSpace(({context,mediaSize})=>{
            const config=styles(),latest=fresh(snapshot),boxes=[];
            this[layer==='heatmap'?'heatmapBoxes':'profileBoxes']=boxes;
            const spacing=this.chart.timeScale().options().barSpacing,last=this.bars.at(-1);
            const candleX=last?this.chart.timeScale().timeToCoordinate(last.time):null;
            const protectedX=last?.provisional?candleX:null;
            const history=snapshot.history||[],max=Math.max(1,...history.flatMap(s=>bandRows(s,config).map(b=>b.notional_usdt)));
            const paint=(band,box,opacity,observed_ms)=>{
                if(box.x+box.width<0||box.x>mediaSize.width||box.y+box.height<0||box.y>mediaSize.height)return false;
                context.fillStyle=config[`liquidity_${band.side==='bid'?'bids':'asks'}`].color;
                context.globalAlpha=opacity;context.fillRect(box.x,box.y,box.width,Math.max(.5,box.height));
                boxes.push({...box,height:Math.max(.5,box.height),band:{...band,observed_ms}});
                return true;
            };
            const bounds=(sample,band)=>{
                // Near the spread, one logarithmic band may contain both sides.
                // Clip each side at the observed midpoint, preserving price meaning.
                const mid=sample.metrics.mid,low=band.side==='ask'?Math.max(band.low,mid):band.low;
                const high=band.side==='bid'?Math.min(band.high,mid):band.high;
                const top=this.series.priceToCoordinate(high),bottom=this.series.priceToCoordinate(low);
                return top===null||bottom===null?null:{y:Math.min(top,bottom),height:Math.abs(bottom-top)};
            };
            context.save();
            if(layer==='heatmap'&&config.liquidity_heatmap?.visible)for(const sample of history){
                const t=sample.sampled_ms??sample.available_ms,x=this.xAt(t),end=this.xAt(t+5000);
                if(x===null||end===null)continue;
                for(const band of bandRows(sample,config)){
                    const vertical=bounds(sample,band);if(!vertical)continue;
                    for(const span of heatmapSpans(x,end-x,protectedX,spacing))paint(band,{...span,...vertical},(config.liquidity_heatmap.opacity??40)/100*Math.sqrt(band.notional_usdt/max),sample.book_received_ms);
                }
            }
            const projected=layer==='profile'&&currentBookVisible(latest,this.bars,this.following,this.chart.timeScale().getVisibleRange());
            const gutter=bookGutter(mediaSize.width,candleX,spacing);
            let painted=0,currentRows=0;
            if(projected){
                const rows=bandRows(latest,config);currentRows=rows.length;
                const maximum=Math.max(1,...rows.map(b=>b.notional_usdt));
                if(gutter&&rows.length){
                    // Dedicated current-book gutter, above the live-price ray
                    // but entirely outside the latest candle body and wick.
                    context.globalAlpha=1;context.fillStyle='#101820';
                    context.fillRect(gutter.left,0,gutter.right-gutter.left,mediaSize.height);
                    context.strokeStyle='#475569';context.lineWidth=1;context.beginPath();
                    context.moveTo(gutter.left,0);context.lineTo(gutter.left,mediaSize.height);context.stroke();
                }
                for(const band of rows){
                    const vertical=bounds(latest,band);if(!vertical)continue;
                    if(!gutter)continue;
                    const width=gutter.maxWidth*band.notional_usdt/maximum;
                    if(paint(band,{x:gutter.origin-width,width,...vertical},(config[`liquidity_${band.side==='bid'?'bids':'asks'}`].opacity??65)/100,latest.book_received_ms))painted++;
                }
            }
            if(layer==='profile'){
                this.projectionHint=latest&&!projected?' · current book in table; go to latest candles':projected&&currentRows&&!gutter?' · add right-side space for depth bars':projected&&currentRows&&!painted?' · depth outside visible price range':'';
                statusText();
            }
            context.restore();
        });
    }
}
export function mount(){
    primitive=new Liquidity();getSeries().attachPrimitive(primitive);
    status=document.createElement('div');status.className='liquidity-status';status.setAttribute('role','status');
    Object.assign(status.style,{position:'absolute',right:'8px',top:'52px',fontSize:'11px',color:'#c3ccd6',pointerEvents:'none',zIndex:2,background:'#101820cc',padding:'3px'});
    tooltip=document.createElement('div');tooltip.className='liquidity-tooltip';tooltip.hidden=true;
    Object.assign(tooltip.style,{position:'absolute',left:'8px',bottom:'30px',background:'#101820ee',color:'#fff',fontSize:'12px',padding:'6px',pointerEvents:'none',zIndex:3});
    bookTable=document.createElement('details');bookTable.className='liquidity-book';bookTable.hidden=true;
    Object.assign(bookTable.style,{position:'absolute',right:'8px',top:'78px',fontSize:'11px',color:'#c3ccd6',zIndex:2,background:'#101820ee',padding:'5px',maxHeight:'280px',overflow:'auto'});
    document.getElementById('chart').append(status,tooltip,bookTable);
    primitive.chart?.subscribeCrosshairMove(param=>{
        const hit=param.point?[...(primitive.hitboxes||[])].reverse().find(b=>param.point.x>=b.x&&param.point.x<=b.x+b.width&&param.point.y>=b.y&&param.point.y<=b.y+b.height):null;
        tooltip.hidden=!hit;if(hit)tooltip.textContent=bandLabel(hit.band);
    });
}
function updateTable(current){
    const open=bookTable.open;bookTable.replaceChildren();bookTable.open=open;bookTable.hidden=!current;
    if(!current)return;
    const title=document.createElement('summary');title.textContent='Live perpetual price bands · bids / asks (USDT)';bookTable.append(title);
    const coverage=document.createElement('div');coverage.textContent=`Snapshot coverage: bid ${current.coverage.bid_bps.toFixed(0)} / ask ${current.coverage.ask_bps.toFixed(0)} bps`;bookTable.append(coverage);
    const table=document.createElement('table'),head=table.createTHead().insertRow();
    for(const name of ['Price band','Bid USDT','Ask USDT']){const cell=document.createElement('th');cell.textContent=name;head.append(cell);}
    const grouped=new Map();
    for(const band of bandRows(current,styles())){
        const key=band.low;let row=grouped.get(key);
        if(!row){row={low:band.low,high:band.high};grouped.set(key,row);}row[band.side]=band.notional_usdt;
    }
    const body=table.createTBody();
    for(const band of [...grouped.values()].sort((a,b)=>b.low-a.low)){
        const row=body.insertRow();
        for(const value of [`${band.low.toPrecision(6)}–${band.high.toPrecision(6)}`,band.bid,band.ask]){
            const cell=row.insertCell();cell.textContent=typeof value==='number'?value.toLocaleString(undefined,{maximumFractionDigits:0}):value??'—';cell.style.padding='2px 5px';
        }
    }
    bookTable.append(table);
}
export function feedState(snapshot,now=Date.now()){return fresh(snapshot,now)?'live':snapshot?.status==='live'?'stale':snapshot?.status||'not recording';}
function statusText(){
    const current=fresh(snapshot),state=feedState(snapshot);
    const text=current?`Binance USDT perpetual · observed orders (USDT) · spot candles · spread ${current.metrics.spread_bps.toFixed(2)} bps${primitive.projectionHint||''}`:
        `Perpetual liquidity: ${state} · ${snapshot?.reason||(state==='stale'?'Waiting for a fresh synchronized update':'Start the liquidity recorder')}`;
    if(status.textContent!==text)status.textContent=text;
    if(!current)bookTable.hidden=true;
}
export function update(chart,data){
    const enabled=keys.some(k=>styles()[k]?.visible);
    snapshot=enabled?data.liquidity:null;primitive.bars=data.bars||[];primitive.following=data.atLiveEdge!==false;primitive.projectionHint='';status.hidden=!enabled;tooltip.hidden=true;
    if(!enabled){primitive.heatmapBoxes=[];primitive.profileBoxes=[];}
    clearTimeout(expiryTimer);
    if(enabled)statusText();updateTable(enabled?fresh(snapshot):null);primitive.requestUpdate?.();
    if(enabled&&snapshot?.latest){
        const deadline=Math.min(snapshot.latest.book_received_ms,snapshot.latest.available_ms)+staleMs+1;
        expiryTimer=setTimeout(()=>{statusText();primitive.requestUpdate?.();},Math.max(0,deadline-Date.now()));
    }
}
export function updateLive(){if(snapshot){statusText();if(!fresh(snapshot))bookTable.hidden=true;primitive.requestUpdate?.();}}
export function getSnapshot(){return snapshot;}
