// Price bands stay tied to the latest decision reference; no candle/scale writes.
import {getSeries} from '../candles/index.js';
export const name='opportunity';
let primitive,status;
const styles=()=>window.Composer?.config.featureStyles||{};
import {confidenceLabel} from '../markers/labels.js';
export {confidenceLabel} from '../markers/labels.js';
export function targetRows(bar,config){
    const context=bar?.signal_context;if(!bar||bar.provisional||!context)return [];
    const map=context.area_map||context.opportunity?.areas||{
        resistance:context.opportunity?.buy?.targets||(context.side==='BUY'?context.plan?.targets:[])||[],
        support:context.opportunity?.sell?.targets||(context.side==='SELL'?context.plan?.targets:[])||[]};
    const entry=context.entry??context.plan?.entry;
    return ['resistance','support'].flatMap(role=>(map[role]||[]).flatMap((area,i)=>{
        const side=role==='resistance'?'buy':'sell',key=`opportunity_${side}_${i+1}`;
        if(!config[key]?.visible||!Number.isFinite(area.price))return [];
        const positive=context.side==='BUY'?role==='resistance':role==='support';
        const outcome=area.outcomes?.[context.side]||(positive?{net_low:area.net_reward_pct,net_high:area.net_reward_far_pct??area.net_reward_pct}:{});
        return [{...area,key,side,role,layer:i+1,plan:context.plan,entry,anchorSide:context.side,anchorTime:context.open_time,
            positive,net_low:outcome.net_low,net_high:outcome.net_high,
            progress:context.area_progress?.[role]?.[i],state:context.state}];
    }));
}
const percent=value=>Number.isFinite(value)?`${value>0?'+':''}${value.toFixed(2)}%`:'unavailable';
export function targetLabel(row,style={}){
    const parts=[`OZ${row.layer}`];
    if(style.scores!==false){
        const score=Number.isFinite(row.confluence_families)?row.confluence_families:row.families?.length;
        parts.push(Number.isFinite(score)?`${score}F`:'—F');
    }
    if(style.returns){
        const lo=row.net_low,hi=row.net_high;
        parts.push(Number.isFinite(lo)&&Number.isFinite(hi)?`${percent(lo)}…${percent(hi)}`:'—%');
    }
    return parts.join(' · ');
}

// Use candle edges in time; never project the band into the chart's empty margin.
export function bandSpan(reference,endTime,firstTime,scale,width){
    if(!reference||!Number.isFinite(endTime)||reference.open_time/1000>endTime)return null;
    let start=scale.timeToCoordinate(reference.open_time/1000);
    const end=scale.timeToCoordinate(endTime),half=(scale.options().barSpacing||0)/2;
    if(start===null&&reference.open_time/1000<firstTime)start=0;
    if(start===null||end===null)return null;
    const left=Math.max(0,start-half),right=Math.min(width,end+half);
    return right>left?{left,right}:null;
}

export function layoutLabels(labels,height){
    const result=labels.filter(l=>l.y>=0&&l.y<=height).sort((a,b)=>a.y-b.y).map(l=>({...l}));
    for(let i=0;i<result.length;i++)result[i].textY=Math.max(result[i].y,i?result[i-1].textY+18:12);
    if(result.length&&result.at(-1).textY>height-6){
        result.at(-1).textY=height-6;
        for(let i=result.length-2;i>=0;i--)result[i].textY=Math.min(result[i].textY,result[i+1].textY-18);
    }
    return result;
}
class Opportunity {
    attached({chart,series,requestUpdate}){
        Object.assign(this,{chart,series,requestUpdate});
        this.views=['bands','labels'].map(layer=>({zOrder:()=>layer==='bands'?'bottom':'top',renderer:()=>({draw:target=>this.draw(target,layer)})}));
    }
    detached(){this.chart=this.series=this.requestUpdate=null;}
    paneViews(){return this.views||[];}
    draw(target,layer){
        if(!this.series)return;
        target.useMediaCoordinateSpace(({context,mediaSize})=>{
            const labels=[],reference=this.reference,config=styles();
            const span=bandSpan(reference,this.endTime,this.firstTime,this.chart.timeScale(),mediaSize.width);
            if(!span)return;
            const {left,right}=span;
            const stopped=reference&&reference.state==='coverage unknown';
            context.save();context.font='11px sans-serif';context.textBaseline='middle';
            const band=(low,high,color,opacity,borderStyle,label,width=1)=>{
                const a=this.series.priceToCoordinate(high),b=this.series.priceToCoordinate(low);
                if(a===null||b===null)return;
                const top=Math.min(a,b),bottom=Math.max(a,b),y=(top+bottom)/2;
                if(bottom<0||top>mediaSize.height)return;
                if(layer==='bands'){
                    context.fillStyle=color;context.globalAlpha=opacity*(stopped ? .6 : 1);
                    context.fillRect(left,top,right-left,Math.max(.5,bottom-top));context.globalAlpha=1;
                    context.strokeStyle=color;context.lineWidth=width;context.setLineDash(borderStyle===1?[2,3]:borderStyle===2?[6,4]:[]);
                    if(borderStyle!==3)context.strokeRect(left,top,right-left,Math.max(.5,bottom-top));
                }
                if(label)labels.push({y:Math.max(8,Math.min(mediaSize.height-8,y)),text:label,color});
            };
            for(const row of this.rows||[]){
                const style=config[row.key];
                band(row.low??row.price,row.high??row.price,style.color,(style.opacity??20)/100,style.style,style.labels===false?null:targetLabel(row,style),style.width||1);
            }
            const visible=(this.rows||[]).length>0&&config.opportunity_buy_1?.reference!==false;
            if(reference&&visible){
                const y=this.series.priceToCoordinate(reference.entry);
                if(y!==null&&y>=0&&y<=mediaSize.height){
                    if(layer==='bands'){context.strokeStyle='#d6dde5';context.lineWidth=1;context.setLineDash([3,4]);context.beginPath();context.moveTo(left,y);context.lineTo(right,y);context.stroke();}
                    labels.push({y,text:`REF`,color:'#d6dde5'});
                }
            }
            if(layer==='labels')for(const label of layoutLabels(labels,mediaSize.height)){
                const width=context.measureText(label.text).width+8,x=Math.max(4,Math.min(right-8,mediaSize.width-8)-width);
                context.globalAlpha=.9;context.fillStyle='#101820';context.fillRect(x-4,label.textY-8,width+4,16);context.globalAlpha=1;
                context.strokeStyle=label.color;context.setLineDash([]);
                if(Math.abs(label.textY-label.y)>3){context.beginPath();context.moveTo(x-6,label.y);context.lineTo(x-2,label.textY);context.stroke();}
                context.fillStyle=label.color;context.fillText(label.text,x,label.textY);
            }
            context.restore();
        });
    }
}
export function mount(){
    primitive=new Opportunity();getSeries().attachPrimitive(primitive);
    status=document.createElement('div');status.className='evidence-status';status.setAttribute('role','status');
    Object.assign(status.style,{position:'absolute',left:'8px',bottom:'28px',fontSize:'11px',color:'#c3ccd6',background:'#101820dd',padding:'4px',maxWidth:'80%',zIndex:2});
    document.getElementById('chart').append(status);
}
export function update(chart,data){
    const config=styles(),bar=(data.bars||[]).filter(b=>!b.provisional).at(-1),reference=bar?.signal_context;
    primitive.rows=data.atLiveEdge===false?[]:targetRows(bar,config);primitive.reference=reference;
    primitive.firstTime=data.bars?.[0]?.time;primitive.endTime=data.formingBar?.time??data.bars?.at(-1)?.time??bar?.time;primitive.requestUpdate?.();
    const confidence=['buy','sell'].some(side=>config[`confidence_${side}`]?.visible);
    const opportunity=Object.entries(config).some(([key,value])=>key.startsWith('opportunity_')&&value.visible);
    status.hidden=!confidence&&!opportunity;
    const evidence=reference?.confidence||bar?.confidence;
    const scores=['buy','sell'].filter(side=>config[`confidence_${side}`]?.visible).map(side=>confidenceLabel({...bar,confidence:evidence},side,config)).join(' · ');
    status.textContent=[confidence?scores.replaceAll('\n',' '):'',opportunity?`OZ ${primitive.rows.length}${reference?.state==='coverage unknown'?' · GAP':''}`:''].filter(Boolean).join(' · ');
    status.title=`Evidence scores, not win probabilities. F = contributing feature families.${reference?` Reference: ${reference.side} ${reference.entry}.`:''} Full details in Settings > Features > Data.`;
}
export function updateLive(chart,bar){if(primitive&&bar){primitive.endTime=bar.time;primitive.requestUpdate?.();}}
