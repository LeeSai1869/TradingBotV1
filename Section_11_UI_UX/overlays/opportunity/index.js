// Price bands stay tied to the latest decision reference; no candle/scale writes.
import {getSeries} from '../candles/index.js';
export const name='opportunity';
let primitive,status;
const styles=()=>window.Composer?.config.featureStyles||{};
export function confidenceLabel(bar,side,config){
    const name=side.toUpperCase();if(!config[`confidence_${side}`]?.visible)return name;
    const evidence=bar.confidence;
    const mode=evidence?.[`${side}_mode`],state=evidence?.[`${side}_status`]??evidence?.status;
    return state==='ready'&&Number.isFinite(evidence[`${side}_score`])?
        `${name} · ${mode?mode+' ':''}${evidence[`${side}_score`].toFixed(0)}/100`:`${name} · confidence pending`;
}
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
const price=value=>value.toPrecision(7);
const percent=value=>Number.isFinite(value)?`${value>0?'+':''}${value.toFixed(2)}%`:'unavailable';
export function targetLabel(row){
    const low=row.low??row.price,high=row.high??row.price;
    const role=row.role||(row.side==='buy'?'resistance':'support');
    const lo=row.net_low,hi=row.net_high;
    const state=row.progress?.crossed?(row.progress.current==='inside'?' · retest':' · crossed'):row.progress?.touched?' · tested':'';
    return `${role==='resistance'?'Sell / resistance':'Buy / support'} ${row.layer} · ${price(low)}–${price(high)} · ${row.positive===false?'adverse':'opportunity'} ${percent(lo)} to ${percent(hi)}${state}${row.modeled?' · modeled':''}`;
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
            const at=reference?this.chart.timeScale().timeToCoordinate(reference.open_time/1000):null;
            const left=at===null?0:Math.max(0,Math.min(at,mediaSize.width));
            const stopped=reference&&reference.state==='coverage unknown';
            context.save();context.font='11px sans-serif';context.textBaseline='middle';
            const band=(low,high,color,opacity,borderStyle,label,width=1)=>{
                const a=this.series.priceToCoordinate(high),b=this.series.priceToCoordinate(low);
                if(a===null||b===null)return;
                const top=Math.min(a,b),bottom=Math.max(a,b),y=(top+bottom)/2;
                if(bottom<0||top>mediaSize.height)return;
                if(layer==='bands'){
                    context.fillStyle=color;context.globalAlpha=opacity*(stopped ? .6 : 1);
                    context.fillRect(left,top,mediaSize.width-left,Math.max(.5,bottom-top));context.globalAlpha=1;
                    context.strokeStyle=color;context.lineWidth=width;context.setLineDash(borderStyle===1?[2,3]:borderStyle===2?[6,4]:[]);
                    if(borderStyle!==3)context.strokeRect(left,top,mediaSize.width-left,Math.max(.5,bottom-top));
                }
                if(label)labels.push({y:Math.max(8,Math.min(mediaSize.height-8,y)),text:label,color});
            };
            for(const row of this.rows||[]){
                const style=config[row.key];
                band(row.low??row.price,row.high??row.price,style.color,(style.opacity??20)/100,style.style,style.labels===false?null:targetLabel(row),style.width||1);
            }
            const visible=(this.rows||[]).length>0&&config.opportunity_buy_1?.reference!==false;
            if(reference&&visible){
                const y=this.series.priceToCoordinate(reference.entry);
                if(y!==null&&y>=0&&y<=mediaSize.height){
                    if(layer==='bands'){context.strokeStyle='#d6dde5';context.lineWidth=1;context.setLineDash([3,4]);context.beginPath();context.moveTo(left,y);context.lineTo(mediaSize.width,y);context.stroke();}
                    labels.push({y,text:`${reference.side} reference ${price(reference.entry)}`,color:'#d6dde5'});
                }
            }
            if(layer==='labels')for(const label of layoutLabels(labels,mediaSize.height)){
                const width=context.measureText(label.text).width+8,x=Math.max(4,mediaSize.width-width-8);
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
    primitive.rows=data.atLiveEdge===false?[]:targetRows(bar,config);primitive.reference=reference;primitive.requestUpdate?.();
    const confidence=['buy','sell'].some(side=>config[`confidence_${side}`]?.visible);
    const opportunity=Object.entries(config).some(([key,value])=>key.startsWith('opportunity_')&&value.visible);
    status.hidden=!confidence&&!opportunity;
    const evidence=reference?.confidence||bar?.confidence;
    const scores=['buy','sell'].filter(side=>config[`confidence_${side}`]?.visible).map(side=>confidenceLabel({...bar,confidence:evidence},side,config)).join(' · ');
    const coverage=evidence?` · evidence ${Math.round(evidence.coverage*100)}%`:' · awaiting closed features';
    const progression=reference?.next_area?` · next support ${reference.next_area.support??'none remaining'} / resistance ${reference.next_area.resistance??'none remaining'}`:'';
    const contextText=reference?`${reference.side} reference ${price(reference.entry)}${progression}${reference.state==='coverage unknown'?' · coverage unknown':''}`:'waiting for latest decision reference';
    const asOf=reference?.available_ms??(bar?.client?.close_time+1);
    status.textContent=`${confidence?scores+coverage+' · scores, not probabilities':''}${opportunity?`${confidence?' | ':''}${contextText} · ${primitive.rows.length} opportunity bands${data.atLiveEdge===false?' · return to latest candles':''}${Number.isFinite(asOf)?' · '+new Date(asOf).toISOString().slice(0,16).replace('T',' ')+' UTC':''}`:''}`;
    status.title=JSON.stringify({reference,current_evidence:bar?.confidence},null,2);
}
export function updateLive(){}
