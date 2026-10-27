// Stored zone lifecycles share the existing combined bar stream.
import {getSeries} from '../candles/index.js';
import {fvgSegments} from './fvg.js';
import {structureSegments} from './structure.js';
import {srSegments,institutionalProjection,srRole} from './sr.js';
import {obSegments} from './ob.js';
export const name='zones';
export function zoneScoreLabel(item){
    const name=item.key.includes('_ob_')||item.key.includes('_breaker_')?'OB formation strength (ATR)':item.key.includes('fvg')?'FVG reaction':'S/R score';
    const details=item.key.includes('support')||item.key.includes('resistance')?`${item.source?' · '+item.source.toUpperCase():''}${item.role==='both'?' · S/R':''}${Number.isFinite(item.touches)?' · tests '+item.touches:''}${Number.isFinite(item.scoreTime)?' · as of '+new Date(item.scoreTime*1000).toISOString().slice(0,16).replace('T',' ')+' UTC':''}`:'';
    return `${name}: ${Number.isFinite(item.score)?item.score.toFixed(2):'unavailable'}${details}`;
}
const definitions={
    support_zones:['support_zone_low','support_zone_high','nearest_support_zone_id'],
    resistance_zones:['resistance_zone_low','resistance_zone_high','nearest_resistance_zone_id'],
    inst_support_zones:['inst_support_zone_low','inst_support_zone_high','nearest_inst_support_zone_id'],
    inst_resistance_zones:['inst_resistance_zone_low','inst_resistance_zone_high','nearest_inst_resistance_zone_id'],
    bull_fvg_zones:['nearest_bull_fvg_low','nearest_bull_fvg_high','nearest_bull_fvg_created_bar'],
    bear_fvg_zones:['nearest_bear_fvg_low','nearest_bear_fvg_high','nearest_bear_fvg_created_bar'],
};
let primitive,axis=[];
const styles=()=>window.Composer.config.featureStyles||{};
export function segments(bars,config,frames={},target=''){
    const result=[];
    result.push(...srSegments(bars,config,frames.sr),...obSegments(bars,config,frames.sr),...structureSegments(bars,config));
    for(const [source,frame] of Object.entries(frames.institutional||{}))result.push(...institutionalProjection(bars,config,frame,source));
    for(const item of result)if(/^(inst_)?(support|resistance)_zones$/.test(item.key))item.role=srRole(item,bars);
    const endTime=bars.at(-1)?.time;
    result.push(...fvgSegments(bars,config,{target,endTime,seeds:frames.current?.active}));
    for(const [source,frame] of Object.entries(frames))if(source!=='current'&&source!=='sr'&&source!=='institutional')result.push(...fvgSegments(frame.bars||[],config,{source,target,endTime,seeds:frame.active}));
    return result;
}
class Zones {
    attached({chart,series,requestUpdate}){Object.assign(this,{chart,series,requestUpdate});}
    detached(){this.chart=this.series=this.requestUpdate=null;}
    timeAt(time,ceil){
        const times=this.times||[];let lo=0,hi=times.length;
        while(lo<hi){const mid=(lo+hi)>>1;if(times[mid]<time)lo=mid+1;else hi=mid;}
        const index=ceil?lo:(times[lo]===time?lo:lo-1);
        return times[Math.max(0,Math.min(times.length-1,index))]??time;
    }
    paneViews(){return [this];}renderer(){return this;}zOrder(){return 'bottom';}
    draw(target){
        if(!this.series)return;
        target.useMediaCoordinateSpace(({context,mediaSize})=>{
            const spacing=this.chart.timeScale().options().barSpacing;
            const range=this.chart.timeScale().getVisibleRange();
            for(const item of this.items||[]){
                if(range&&typeof range.from==='number'&&(item.end<range.from||item.start>range.to))continue;
                const selected=styles()[item.key];if(!selected?.visible)continue;
                const style={...selected,color:item.role==='both'?(selected.dualColor||'#eab308'):selected.color};
                const x1=this.chart.timeScale().timeToCoordinate(this.timeAt(item.start,true)),x2=this.chart.timeScale().timeToCoordinate(this.timeAt(item.end,false));
                const y1=this.series.priceToCoordinate(item.high),y2=this.series.priceToCoordinate(item.low);
                if([x1,x2,y1,y2].some(x=>x===null)||x2<x1||x2<0||x1>mediaSize.width)continue;
                const left=x1-spacing/2,width=Math.max(spacing,x2-x1+spacing);
                context.save();context.fillStyle=style.color;context.globalAlpha=(style.opacity??20)/100;
                context.beginPath();
                const points=item.history||[{time:item.start,low:item.low,high:item.high}];
                const edges=points.map((p,i)=>({left:i?this.chart.timeScale().timeToCoordinate(this.timeAt(p.time,true))-spacing/2:left,
                    right:i+1<points.length?this.chart.timeScale().timeToCoordinate(this.timeAt(points[i+1].time,true))-spacing/2:left+width,
                    top:this.series.priceToCoordinate(p.high),bottom:this.series.priceToCoordinate(p.low)}));
                context.moveTo(edges[0].left,edges[0].top);
                for(const e of edges){context.lineTo(e.left,e.top);context.lineTo(e.right,e.top);}
                for(const e of [...edges].reverse()){context.lineTo(e.right,e.bottom);context.lineTo(e.left,e.bottom);}
                context.closePath();context.fill();context.globalAlpha=1;
                context.strokeStyle=style.color;context.lineWidth=style.width||2;context.setLineDash(style.style===1?[2,3]:style.style===2?[6,4]:[]);
                if(style.style!==3)context.stroke();
                if(style.scores!==false&&item.key!=='structure_range_zones'){
                    context.font='12px sans-serif';
                    const text=zoneScoreLabel(item);
                    const x=Math.max(2,Math.min(mediaSize.width-context.measureText(text).width-12,x2-4));
                    const y=this.series.priceToCoordinate((item.low+item.high)/2);
                    if(y!==null&&y>=0&&y<=mediaSize.height){
                        context.font='12px sans-serif';context.textBaseline='middle';
                        const width=context.measureText(text).width+8;
                        context.fillStyle='#101820';context.globalAlpha=.9;context.fillRect(x-4,y-9,width,18);
                        context.globalAlpha=1;context.fillStyle=style.color;context.fillText(text,x,y);
                    }
                }
                context.restore();
            }
        });
    }
}
export function mount(){primitive=new Zones();getSeries().attachPrimitive(primitive);}
export function update(chart,data){
    primitive.times=(data.bars||[]).map(b=>b.time);
    primitive.items=segments(data.bars||[],styles(),{...data.fvgFrames,sr:data.srSnapshot,institutional:data.srFrames},data.timeframe);primitive.requestUpdate?.();
    // Labels use the last actually calculated closed candle, never fabricated levels.
    const series=getSeries();for(const line of axis)series.removePriceLine(line);axis=[];
    const last=data.bars?.at(-1),f=last?.features||{};
    for(const [key,[low,high]] of Object.entries(definitions))if(styles()[key]?.visible){
        const prices=Number.isFinite(f[low])&&Number.isFinite(f[high])&&f[high]>f[low]?[f[low],f[high]]:[];
        for(const price of new Set(prices))axis.push(series.createPriceLine({price,color:styles()[key].color,lineVisible:false,axisLabelVisible:true,title:''}));
    }
}
export function updateLive(chart,bar){
    if(!bar)return;
    if(primitive.times?.at(-1)<bar.time)primitive.times.push(bar.time);
    for(const item of primitive.items||[])if(!item.invalidated&&!item.truncated&&Number.isFinite(item.until))item.end=Math.max(item.end,Math.min(bar.time,item.until??bar.time));
    primitive.requestUpdate?.();
}
export function getSegments(){return primitive?.items||[];}
