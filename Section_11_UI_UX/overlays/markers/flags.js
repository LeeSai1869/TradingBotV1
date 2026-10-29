import {confidenceLabel} from './labels.js';

// Flags belong to signal candles; price-reference values remain in the packet.
export class SignalFlags {
    attached({chart,series,requestUpdate}){Object.assign(this,{chart,series,requestUpdate});}
    detached(){this.chart=this.series=this.requestUpdate=null;}
    paneViews(){return [this];}
    zOrder(){return 'top';}
    renderer(){return this;}
    draw(target){
        if(!this.series)return;
        target.useMediaCoordinateSpace(({context,mediaSize})=>{
            context.save();context.font='bold 11px sans-serif';context.textAlign='center';context.textBaseline='middle';
            for(const {bar,side} of this.signals||[]){
                const style=this.styles?.[`momentum_${side}`]||{},buy=side==='buy',direction=buy?1:-1;
                const x=this.chart.timeScale().timeToCoordinate(bar.time);
                const price=buy?bar.client?.low:bar.client?.high;
                if(!Number.isFinite(price))continue;
                const y=this.series.priceToCoordinate(price);
                if(x===null||y===null||x<0||x>mediaSize.width||y<0||y>mediaSize.height)continue;
                const color=style.color||(buy?'#26a69a':'#ef5350'),tip=y+direction*5,base=tip+direction*7;
                const shape=style.shape||(buy?'arrowUp':'arrowDown');
                context.fillStyle=color;context.strokeStyle=color;context.lineWidth=style.width||1.5;context.beginPath();
                if(shape==='circle')context.arc(x,base,3.5,0,Math.PI*2);
                else if(shape==='square')context.rect(x-3.5,base-3.5,7,7);
                else {
                    const up=shape==='arrowUp',top=Math.min(tip,base),bottom=Math.max(tip,base);
                    context.moveTo(x,up?top:bottom);context.lineTo(x-4,up?bottom:top);context.lineTo(x+4,up?bottom:top);context.closePath();
                }
                context.fill();
                if(style.label===false)continue;
                const lines=confidenceLabel(bar,side,this.styles||{}).split('\n');
                const width=Math.max(42,...lines.map(text=>context.measureText(text).width+12)),height=lines.length*14+6;
                const left=Math.max(1,Math.min(mediaSize.width-width-1,x-width/2));
                const wanted=buy?base+8:base-8-height,top=Math.max(1,Math.min(mediaSize.height-height-1,wanted));
                context.beginPath();context.moveTo(x,base);context.lineTo(left+width/2,buy?top:top+height);context.stroke();
                context.beginPath();context.roundRect(left,top,width,height,3);context.fill();
                context.fillStyle='#fff';
                lines.forEach((text,i)=>context.fillText(text,left+width/2,top+10+i*14));
            }
            context.restore();
        });
    }
}
