import {getSeries} from '../candles/index.js';
export const name='pivot_research';
let primitive,lastData;
class PivotVisual {
    attached({chart,series,requestUpdate}){Object.assign(this,{chart,series,requestUpdate});}
    detached(){this.chart=this.series=this.requestUpdate=null;}
    paneViews(){return [this];}renderer(){return this;}zOrder(){return 'top';}
    draw(target){
        if(!this.packet||!this.visible||!this.series)return;
        target.useMediaCoordinateSpace(({context:ctx,mediaSize:size})=>{
            const packet=this.packet,p=packet.pivot,scale=this.chart.timeScale();ctx.save();ctx.font='bold 11px sans-serif';
            const point=(stamp,price,text,color)=>{const x=scale.timeToCoordinate(stamp/1000),y=this.series.priceToCoordinate(price);if(x===null||y===null)return;ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();ctx.fillText(text,x+7,y-9);};
            point(p.origin_time,p.price,p.type.replace('_',' ')+' · retrospective','#bba0f5');
            const detection=packet.bars.find(b=>b.client.open_time===p.confirmation_time);
            if(detection)point(p.confirmation_time,detection.client.close,'PIVOT KNOWN AT CLOSE','#e8c56b');
            const side=p.type==='PIVOT_LOW'?1:-1,price=p.price*(1+side*packet.threshold_pct/100),y=this.series.priceToCoordinate(price);
            const end=packet.case.next_opposite?.origin_time??packet.bars.at(-1)?.client.open_time;
            const startX=scale.timeToCoordinate(p.origin_time/1000),endX=scale.timeToCoordinate(end/1000);
            if(y!==null&&startX!==null){ctx.strokeStyle='#54d5e8';ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(Math.max(0,startX),y);ctx.lineTo(endX??size.width,y);ctx.stroke();ctx.fillStyle='#54d5e8';ctx.fillText(`${side>0?'+':'−'}${packet.threshold_pct}% from pivot`,Math.max(4,startX+8),y-5);}
            ctx.restore();
        });
    }
}
export function mount(){primitive=new PivotVisual();getSeries().attachPrimitive(primitive);window.addEventListener('pivot-research-case',event=>{primitive.packet=event.detail;primitive.visible=!!event.detail&&lastData?.symbol===event.detail.symbol&&lastData?.timeframe===event.detail.timeframe;primitive.requestUpdate?.();});}
export function update(chart,data){lastData=data;primitive.visible=primitive.packet?.symbol===data.symbol&&primitive.packet?.timeframe===data.timeframe;primitive.requestUpdate?.();}
