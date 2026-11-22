// Observed perpetual depth has its own market identity and availability clock.
// Draw only on actual chart times; no synthetic pre-collection heatmap/history.
import {getSeries} from '../candles/index.js';
import {PaintCache,viewportKey} from '../../chart/paint_cache.js';
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
    // Keep genuinely narrow observed price bins legible when zoomed out.
    // Price bounds/notional in the sample and tooltip remain exact.
    const rawHeight=Math.abs(bottom-top),height=Math.max(1,rawHeight),y=(top+bottom-height)/2;
    let x=paneWidth-5-width;const result=[];
    for(const side of ['bid','ask']){
        const size=width*row[side]/row.total;
        if(size>0)result.push({x,width:size,y,height,band:row[side+'Band']});
        x+=size;
    }
    return result;
}
export function bandLabel(band){return `${band.side==='bid'?'Resting bids':'Resting asks'} · ${band.low.toPrecision(7)}–${band.high.toPrecision(7)} · ${band.notional_usdt.toLocaleString(undefined,{maximumFractionDigits:0})} USDT · Binance perpetual · sampled presence ${Math.floor((band.sampled_presence_ms||0)/1000)}s${band.observed_ms?' · '+new Date(band.observed_ms).toLocaleTimeString():''}`;}
// Candle assignment is data-dependent, not pointer/viewport-dependent.
export function samplePosition(bars,ms){
    let lo=0,hi=bars.length;
    while(lo<hi){const mid=(lo+hi)>>1;if(bars[mid].open_time<=ms)lo=mid+1;else hi=mid;}
    const bar=bars[lo-1],end=bar?.client?.close_time+1;
    if(!bar||!Number.isFinite(end)||end<=bar.open_time||ms>end)return null;
    return {time:bar.time,fraction:(ms-bar.open_time)/(end-bar.open_time)};
}
export function sampleX(position,scale,spacing,coordinates){
    if(!position)return null;
    if(!coordinates.has(position.time))coordinates.set(position.time,scale.timeToCoordinate(position.time));
    const x=coordinates.get(position.time);
    return x===null?null:x-spacing/2+spacing*position.fraction;
}
class Liquidity {
    constructor(){this.paintCaches={heatmap:new PaintCache(),profile:new PaintCache()};this.paintRevision=0;}
    attached({chart,series,requestUpdate}){
        Object.assign(this,{chart,series,requestUpdate});
        this.views=['heatmap','profile'].map(layer=>({zOrder:()=>layer==='profile'?'normal':'bottom',renderer:()=>({draw:target=>this.draw(target,layer)})}));
    }
    detached(){for(const cache of Object.values(this.paintCaches))cache.clear();this.chart=this.series=this.requestUpdate=null;}
    paneViews(){return this.views||[];}
    setHistory(history, config) {
        let maximum = 1;
        this.history = config.liquidity_heatmap?.visible ? history.map(sample => {
            const bands = bandRows(sample, config);
            for (const band of bands) maximum = Math.max(maximum, band.notional_usdt);
            const t=sample.sampled_ms??sample.available_ms;
            return {sample,bands,start:samplePosition(this.bars,t),stop:samplePosition(this.bars,t+5000)};
        }) : [];
        this.historyMaximum = maximum;
    }
    hitAt({x,y}) {
        const profile = this.profileBoxes || [];
        const columns = this.heatmapColumns || [];
        for (let columnIndex = columns.length; columnIndex >= 0; columnIndex--) {
            const column = columns[columnIndex];
            if (column && (x < column.left || x > column.right)) continue;
            const boxes = column?.boxes ?? profile;
            for (let i = boxes.length - 1; i >= 0; i--) {
                const b = boxes[i];
                if (x >= b.x && x <= b.x + b.width && y >= b.y && y <= b.y + b.height) return b;
            }
        }
        return null;
    }
    draw(target,layer){
        if(!this.series||!snapshot)return;
        const latest=fresh(snapshot),reference=latest?.metrics.mid??snapshot.history?.[0]?.metrics?.mid??1;
        const key=[this.paintRevision,!!latest,...viewportKey(this.chart,this.series,reference)];
        target.useMediaCoordinateSpace(scope=>this.paintCaches[layer].draw(scope,key,({context,mediaSize})=>{
            const config=styles(),boxes=[];
            const columns = [];
            if (layer === 'heatmap') this.heatmapColumns = columns;
            else this.profileBoxes = boxes;
            const spacing=this.chart.timeScale().options().barSpacing,last=this.bars.at(-1);
            const candleX=last?this.chart.timeScale().timeToCoordinate(last.time):null;
            const protectedX=last?.provisional?candleX:null;
            const coordinates = new Map();
            const coordinate = price => {
                if (!coordinates.has(price)) coordinates.set(price, this.series.priceToCoordinate(price));
                return coordinates.get(price);
            };
            const paint=(band,box,opacity,observed_ms,hits=boxes)=>{
                if(box.x+box.width<0||box.x>mediaSize.width||box.y+box.height<0||box.y>mediaSize.height)return false;
                context.fillStyle=config[`liquidity_${band.side==='bid'?'bids':'asks'}`].color;
                context.globalAlpha=opacity;context.fillRect(box.x,box.y,box.width,box.height);
                hits.push({...box,band,observed_ms});
                return true;
            };
            const bounds=(sample,band)=>{
                // Near the spread, one logarithmic band may contain both sides.
                // Clip each side at the observed midpoint, preserving price meaning.
                const mid=sample.metrics.mid,low=band.side==='ask'?Math.max(band.low,mid):band.low;
                const high=band.side==='bid'?Math.min(band.high,mid):band.high;
                const top=coordinate(high),bottom=coordinate(low);
                return top===null||bottom===null?null:{y:Math.min(top,bottom),height:Math.abs(bottom-top)};
            };
            context.save();
            const visibleSamples = new Map();
            const timeCoordinates=new Map(),scale=this.chart.timeScale();
            if (layer === 'heatmap') for (const {sample,bands,start:begin,stop:finish} of this.history) {
                const start=sampleX(begin,scale,spacing,timeCoordinates),stop=sampleX(finish,scale,spacing,timeCoordinates);
                if (start === null || stop === null || stop <= start || stop <= 0 || start >= mediaSize.width) continue;
                // Several book observations can fall inside one pixel at 5m/15m.
                // Draw the latest observation per pixel until zoom reveals the rest.
                const x = stop - start < 1 ? Math.floor(start) : start;
                visibleSamples.set(x, {sample, bands, x, end: Math.max(x + 1, stop)});
            }
            for (const {sample, bands, x, end} of visibleSamples.values()) {
                const spans = heatmapSpans(x, end - x, protectedX, spacing);
                if (!spans.length) continue;
                const column = {left: x, right: end, boxes: []};
                columns.push(column);
                for (const band of bands) {
                    const vertical = bounds(sample, band);
                    if (!vertical) continue;
                    const opacity = (config.liquidity_heatmap.opacity ?? 40) / 100;
                    for (const span of spans) paint(band, {...span,...vertical},
                        opacity * Math.sqrt(band.notional_usdt / this.historyMaximum), sample.book_received_ms, column.boxes);
                }
            }
            const projected=layer==='profile'&&currentBookVisible(latest,this.bars,this.following,this.chart.timeScale().getVisibleRange());
            let painted=0,currentRows=0;
            if(projected){
                const rows=profileRows(latest,config);currentRows=rows.length;
                const maximum=Math.max(0,...rows.map(row=>row.total));
                for(const row of rows)for(const segment of stackedSegments(row,maximum,value=>this.series.priceToCoordinate(value),mediaSize.width,config.liquidity_bids?.lengthPercent??45)){
                    const {band,...box}=segment;
                    for(const span of heatmapSpans(box.x,box.width,protectedX,spacing))if(paint(band,{...box,...span},(config[`liquidity_${band.side==='bid'?'bids':'asks'}`].opacity??65)/100,latest.book_received_ms))painted++;
                }
            }
            if(layer==='profile'){
                this.projectionHint=latest&&!projected?' · go to latest candles for current depth':projected&&currentRows&&!painted?' · depth outside visible price range':'';
                statusText();
            }
            context.restore();
        }));
    }
}
export function mount(){
    primitive=new Liquidity();getSeries().attachPrimitive(primitive);
    status=document.createElement('div');status.className='liquidity-status';status.setAttribute('role','status');
    Object.assign(status.style,{position:'absolute',right:'8px',top:'52px',fontSize:'11px',color:'#c3ccd6',pointerEvents:'none',zIndex:2,background:'#101820cc',padding:'3px',maxWidth:'75%',whiteSpace:'normal'});
    tooltip=document.createElement('div');tooltip.className='liquidity-tooltip';tooltip.hidden=true;
    Object.assign(tooltip.style,{position:'absolute',left:'8px',bottom:'30px',background:'#101820ee',color:'#fff',fontSize:'12px',padding:'6px',pointerEvents:'none',zIndex:3});
    document.getElementById('chart').append(tooltip);
    primitive.chart?.subscribeCrosshairMove(param=>{
        const hit = param.point ? primitive.hitAt(param.point) : null;
        tooltip.hidden = !hit;
        if (hit) {
            const label = bandLabel({...hit.band, observed_ms: hit.observed_ms});
            if (tooltip.textContent !== label) tooltip.textContent = label;
        }
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
    primitive.paintRevision++;
    for(const cache of Object.values(primitive.paintCaches))cache.invalidate();
    snapshot=enabled?data.liquidity:null;primitive.bars=data.bars||[];primitive.following=data.atLiveEdge!==false;primitive.projectionHint='';status.hidden=!enabled;tooltip.hidden=true;
    primitive.setHistory(snapshot?.history || [], styles());
    if(!enabled){primitive.heatmapColumns=[];primitive.profileBoxes=[];for(const cache of Object.values(primitive.paintCaches))cache.clear();}
    clearTimeout(expiryTimer);
    if(enabled)statusText();primitive.requestUpdate?.();
    if(enabled&&snapshot?.latest){
        const deadline=Math.min(snapshot.latest.book_received_ms,snapshot.latest.available_ms)+staleMs+1;
        expiryTimer=setTimeout(()=>{statusText();primitive.requestUpdate?.();},Math.max(0,deadline-Date.now()));
    }
}
export function updateLive(){if(snapshot){statusText();primitive.requestUpdate?.();}}
export function getSnapshot(){return snapshot;}

export function getPaintStats(){return Object.fromEntries(Object.entries(primitive?.paintCaches||{}).map(([key,value])=>[key,{...value.stats}]));}
