// Latest closed-bar scenarios: primitive drawing never changes candle geometry
// or autoscale and is not presented as a historical filled/executed trade.
import {getSeries} from '../candles/index.js';
export const name='opportunity';
let primitive,status;
const styles=()=>window.Composer?.config.featureStyles||{};
export function confidenceLabel(bar,side,config){
    const name=side.toUpperCase();if(!config[`confidence_${side}`]?.visible)return name;
    const evidence=bar.confidence;
    return evidence?.status==='ready'&&Number.isFinite(evidence[`${side}_score`])?
        `${name} · ${evidence[`${side}_score`].toFixed(0)}/100`:`${name} · confidence pending`;
}
export function targetRows(bar,config){
    if(!bar||bar.provisional||bar.opportunity?.status!=='ready')return [];
    return ['buy','sell'].flatMap(side=>(bar.opportunity[side]?.targets||[]).flatMap((target,i)=>{
        const key=`opportunity_${side}_${i+1}`;
        return config[key]?.visible&&Number.isFinite(target.price)?[{...target,key,side,layer:i+1,plan:bar.opportunity[side]}]:[];
    }));
}
export function targetLabel(row){
    const rr=Number.isFinite(row.reward_risk)?`${row.reward_risk.toFixed(2)}R`:'R unavailable';
    return `${row.side.toUpperCase()} T${row.layer} · net ${row.net_reward_pct.toFixed(2)}% · ${rr}`;
}
class Opportunity {
    attached({chart,series,requestUpdate}){Object.assign(this,{chart,series,requestUpdate});}
    detached(){this.chart=this.series=this.requestUpdate=null;}
    paneViews(){return [this];}renderer(){return this;}zOrder(){return 'bottom';}
    draw(target){
        if(!this.series)return;
        target.useMediaCoordinateSpace(({context,mediaSize})=>{
            context.save();context.font='12px sans-serif';context.textBaseline='bottom';
            const line=(price,label,color,width=1,dash=[])=>{
                const y=this.series.priceToCoordinate(price);if(y===null||y<0||y>mediaSize.height)return;
                context.strokeStyle=color;context.fillStyle=color;context.lineWidth=width;context.setLineDash(dash);
                context.beginPath();context.moveTo(0,y);context.lineTo(mediaSize.width,y);context.stroke();
                const x=Math.max(4,mediaSize.width-context.measureText(label).width-10);
                context.fillText(label,x,y-3);
            };
            const seen=new Set();
            for(const row of this.rows||[]){
                const style=styles()[row.key];line(row.price,targetLabel(row),style.color,style.width,style.style===1?[2,3]:style.style===2?[6,4]:[]);
                if(!seen.has(row.side)){
                    seen.add(row.side);
                    line(row.plan.invalidation,`${row.side.toUpperCase()} invalidation · risk ${row.plan.risk_pct.toFixed(2)}%`,'#f59e0b',1,[3,4]);
                }
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
    const config=styles(),bar=(data.bars||[]).filter(b=>!b.provisional).at(-1);
    primitive.rows=data.atLiveEdge===false?[]:targetRows(bar,config);primitive.requestUpdate?.();
    const confidence=['buy','sell'].some(side=>config[`confidence_${side}`]?.visible);
    const opportunity=Object.entries(config).some(([key,value])=>key.startsWith('opportunity_')&&value.visible);
    status.hidden=!confidence&&!opportunity;
    const evidence=bar?.confidence,plan=bar?.opportunity;
    const scores=['buy','sell'].filter(side=>config[`confidence_${side}`]?.visible).map(side=>confidenceLabel(bar||{},side,config)).join(' · ');
    const coverage=evidence?` · evidence ${Math.round(evidence.coverage*100)}%`:' · awaiting closed features';
    const costs=plan?.costs?` · assumed round-trip ${plan.costs.round_trip_bps} bps` : '';
    status.textContent=`${confidence?scores+coverage+' · scores, not probabilities':''}${opportunity?`${confidence?' | ':''}Opportunity scenarios${costs} · ${primitive.rows.length} known targets${data.atLiveEdge===false?' · return to latest candles':''} · as of ${bar?new Date(bar.client.close_time+1).toISOString().slice(0,16).replace('T',' '):'unavailable'} UTC`:''}`;
    status.title=JSON.stringify({confidence:evidence,opportunity:plan},null,2);
}
export function updateLive(){} // Intrabar prices never rewrite closed evidence.
