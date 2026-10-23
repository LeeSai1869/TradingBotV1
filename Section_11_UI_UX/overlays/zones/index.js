// Stored S/R and nearest active FVG zones share the existing combined bar stream.
import {getSeries} from '../candles/index.js';
export const name='zones';
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
export function segments(bars,config){
    const result=[];
    for(const [key,[low,high,id]] of Object.entries(definitions)){
        if(!config[key]?.visible)continue;
        let current=null;
        for(const bar of bars){
            const f=bar.features||{};
            let lo=f[low],hi=f[high];
            if(!Number.isFinite(lo)||!Number.isFinite(hi)||hi<=lo){current=null;continue;}
            const identity=f[id]??`${lo}:${hi}`;
            if(current&&current.identity===identity&&current.low===lo&&current.high===hi)current.end=bar.time;
            else{current={key,identity,low:lo,high:hi,start:bar.time,end:bar.time};result.push(current);}
        }
    }
    return result;
}
class Zones {
    attached({chart,series,requestUpdate}){Object.assign(this,{chart,series,requestUpdate});}
    detached(){this.chart=this.series=this.requestUpdate=null;}
    paneViews(){return [this];}renderer(){return this;}zOrder(){return 'bottom';}
    draw(target){
        if(!this.series)return;
        target.useMediaCoordinateSpace(({context,mediaSize})=>{
            const spacing=this.chart.timeScale().options().barSpacing;
            const range=this.chart.timeScale().getVisibleRange();
            for(const item of this.items||[]){
                if(range&&typeof range.from==='number'&&(item.end<range.from||item.start>range.to))continue;
                const style=styles()[item.key];if(!style?.visible)continue;
                const x1=this.chart.timeScale().timeToCoordinate(item.start),x2=this.chart.timeScale().timeToCoordinate(item.end);
                const y1=this.series.priceToCoordinate(item.high),y2=this.series.priceToCoordinate(item.low);
                if([x1,x2,y1,y2].some(x=>x===null)||x2<0||x1>mediaSize.width)continue;
                const left=x1-spacing/2,width=Math.max(spacing,x2-x1+spacing),height=Math.max(1,y2-y1);
                context.save();context.fillStyle=style.color;context.globalAlpha=(style.opacity??20)/100;context.fillRect(left,y1,width,height);context.globalAlpha=1;
                context.strokeStyle=style.color;context.lineWidth=style.width||2;context.setLineDash(style.style===1?[2,3]:style.style===2?[6,4]:[]);
                context.strokeRect(left,y1,width,height);context.restore();
            }
        });
    }
}
export function mount(){primitive=new Zones();getSeries().attachPrimitive(primitive);}
export function update(chart,data){
    primitive.items=segments(data.bars||[],styles());primitive.requestUpdate?.();
    // Labels use the last actually calculated closed candle, never fabricated levels.
    const series=getSeries();for(const line of axis)series.removePriceLine(line);axis=[];
    const last=data.bars?.at(-1),f=last?.features||{};
    for(const [key,[low,high]] of Object.entries(definitions))if(styles()[key]?.visible){
        const prices=Number.isFinite(f[low])&&Number.isFinite(f[high])&&f[high]>f[low]?[f[low],f[high]]:[];
        for(const price of new Set(prices))axis.push(series.createPriceLine({price,color:styles()[key].color,lineVisible:false,axisLabelVisible:true,title:''}));
    }
}
export function updateLive(){/* Permanent zone lifecycles advance on closed candles only. */}
export function getSegments(){return primitive?.items||[];}
