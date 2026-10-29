// Observed perpetual depth has its own market identity and availability clock.
// Draw only on actual chart times; no synthetic pre-collection heatmap/history.
import {getSeries} from '../candles/index.js';
export const name='liquidity';
let primitive,status,tooltip,snapshot=null,expiryTimer=null;
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
export function profileRows(sample,config){
    const grouped=new Map();
    for(const band of bandRows(sample,config)){
        const id=`${band.low}:${band.high}`;
        if(!grouped.has(id))grouped.set(id,{low:band.low,high:band.high,bid:0,ask:0});
        const row=grouped.get(id);row[band.side]+=band.notional_usdt;
        row[band.side+'Band']={...band,notional_usdt:row[band.side]};
    }
    return [...grouped.values()].map(row=>({...row,total:row.bid+row.ask}));
}
export function stackedSegments(row,maximum,coordinate,paneWidth,lengthPercent=45){
    const top=coordinate(row.high),bottom=coordinate(row.low);
    if(top===null||bottom===null||top===bottom||!(maximum>0)||!(row.total>0))return [];
    const width=paneWidth*lengthPercent/100*row.total/maximum;
    let x=paneWidth-5-width;const result=[];
    for(const side of ['bid','ask']){
        const size=width*row[side]/row.total;
        if(size>0)result.push({x,width:size,y:Math.min(top,bottom),height:Math.abs(bottom-top),band:row[side+'Band']});
        x+=size;
    }
    return result;
}
export function bandLabel(band){return `${band.side==='bid'?'Resting bids':'Resting asks'} · ${band.low.toPrecision(7)}–${band.high.toPrecision(7)} · ${band.notional_usdt.toLocaleString(undefined,{maximumFractionDigits:0})} USDT · Binance perpetual · sampled presence ${Math.floor((band.sampled_presence_ms||0)/1000)}s${band.observed_ms?' · '+new Date(band.observed_ms).toLocaleTimeString():''}`;}
class Liquidity {
    attached({chart,series,requestUpdate}){
        Object.assign(this,{chart,series,requestUpdate});
        this.views=['heatmap','profile'].map(layer=>({zOrder:()=>'bottom',renderer:()=>({draw:target=>this.draw(target,layer)})}));
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
                context.globalAlpha=opacity;context.fillRect(box.x,box.y,box.width,box.height);
                boxes.push({...box,height:box.height,band:{...band,observed_ms}});
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
            let painted=0,currentRows=0;
            if(projected){
                const rows=profileRows(latest,config);currentRows=rows.length;
                const maximum=Math.max(0,...rows.map(row=>row.total));
                for(const row of rows)for(const segment of stackedSegments(row,maximum,value=>this.series.priceToCoordinate(value),mediaSize.width,config.liquidity_bids?.lengthPercent??45)){
                    const {band,...box}=segment;
                    if(paint(band,box,(config[`liquidity_${band.side==='bid'?'bids':'asks'}`].opacity??65)/100,latest.book_received_ms))painted++;
                }
            }
            if(layer==='profile'){
                this.projectionHint=latest&&!projected?' · go to latest candles for current depth':projected&&currentRows&&!painted?' · depth outside visible price range':'';
                statusText();
            }
            context.restore();
        });
    }
}
export function mount(){
    primitive=new Liquidity();getSeries().attachPrimitive(primitive);
    status=document.createElement('div');status.className='liquidity-status';status.setAttribute('role','status');
    Object.assign(status.style,{position:'absolute',right:'8px',top:'52px',fontSize:'11px',color:'#c3ccd6',pointerEvents:'none',zIndex:2,background:'#101820cc',padding:'3px',maxWidth:'75%',whiteSpace:'normal'});
    tooltip=document.createElement('div');tooltip.className='liquidity-tooltip';tooltip.hidden=true;
    Object.assign(tooltip.style,{position:'absolute',left:'8px',bottom:'30px',background:'#101820ee',color:'#fff',fontSize:'12px',padding:'6px',pointerEvents:'none',zIndex:3});
    document.getElementById('chart').append(status,tooltip);
    primitive.chart?.subscribeCrosshairMove(param=>{
        const hit=param.point?[...(primitive.hitboxes||[])].reverse().find(b=>param.point.x>=b.x&&param.point.x<=b.x+b.width&&param.point.y>=b.y&&param.point.y<=b.y+b.height):null;
        tooltip.hidden=!hit;if(hit)tooltip.textContent=bandLabel(hit.band);
    });
}
export function feedState(snapshot,now=Date.now()){return fresh(snapshot,now)?'live':snapshot?.status==='live'?'stale':snapshot?.status||'not recording';}
export function healthLabel(current){
    const coverage=current.coverage||{},health=current.health,flow=current.analytics?.['60s'];
    const depth=`depth ${Math.floor(coverage.bid_bps||0)}/${Math.floor(coverage.ask_bps||0)} bps`;
    if(!health)return depth;
    const delta=flow?.complete?`60s delta ${Math.round(flow.delta_usdt).toLocaleString()} USDT`:'flow warming up / partial';
    return `${depth} · book ${Math.max(0,Date.now()-current.book_received_ms)} ms old · ${delta} · OI ${health.open_interest_fresh?'fresh':'unavailable/stale'} · mark/funding ${health.mark_context_fresh?'fresh':'unavailable/stale'}`;
}
function statusText(){
    const current=fresh(snapshot),state=feedState(snapshot);
    const text=current?`Binance USDT perpetual · observed orders (USDT) · spot candles · spread ${current.metrics.spread_bps.toFixed(2)} bps${styles().liquidity_bids?.details===false?'':' · '+healthLabel(current)}${primitive.projectionHint||''}`:
        `Perpetual liquidity: ${state} · ${snapshot?.reason||(state==='stale'?'Waiting for a fresh synchronized update':'Start the liquidity recorder')}`;
    status.title=text;
    const coverage=current?.coverage||{},health=current?.health;
    const compact=current?`LQ · PERP · ${current.metrics.spread_bps.toFixed(2)}bp${styles().liquidity_bids?.details===false?'':` · D${Math.floor(coverage.bid_bps||0)}/${Math.floor(coverage.ask_bps||0)}bp · OI${health?.open_interest_fresh?'✓':'—'} F${health?.mark_context_fresh?'✓':'—'}`}${primitive.projectionHint?' · ↕':''}`:`LQ · ${state.toUpperCase()}`;
    if(status.textContent!==compact)status.textContent=compact;
}
export function update(chart,data){
    const enabled=keys.some(k=>styles()[k]?.visible);
    snapshot=enabled?data.liquidity:null;primitive.bars=data.bars||[];primitive.following=data.atLiveEdge!==false;primitive.projectionHint='';status.hidden=!enabled;tooltip.hidden=true;
    if(!enabled){primitive.heatmapBoxes=[];primitive.profileBoxes=[];}
    clearTimeout(expiryTimer);
    if(enabled)statusText();primitive.requestUpdate?.();
    if(enabled&&snapshot?.latest){
        const deadline=Math.min(snapshot.latest.book_received_ms,snapshot.latest.available_ms)+staleMs+1;
        expiryTimer=setTimeout(()=>{statusText();primitive.requestUpdate?.();},Math.max(0,deadline-Date.now()));
    }
}
export function updateLive(){if(snapshot){statusText();primitive.requestUpdate?.();}}
export function getSnapshot(){return snapshot;}
