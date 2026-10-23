// One current closed-candle profile, projected from the runner's stored bins.
import {getSeries} from '../candles/index.js';
export const name='volumeProfile';
let primitive,axis=[],status,profile=null;
const styles=()=>window.Composer.config.featureStyles||{};
export function histogramRows(snapshot,config){
    if(snapshot?.status!=='ready')return [];
    const maximum=Math.max(0,...snapshot.bins.map(b=>b.volume));
    if(!maximum)return [];
    return snapshot.bins.filter(b=>Number.isFinite(b.volume)&&b.volume>0&&b.high>b.low).map(b=>{
        const node=b.node==='high'?'vp_hvn_nodes':b.node==='low'?'vp_lvn_nodes':'vp_histogram';
        const key=config[node]?.visible?node:config.vp_histogram?.visible?'vp_histogram':null;
        return key?{...b,key,fraction:b.volume/maximum}:null;
    }).filter(Boolean);
}
class Profile {
    attached({series,requestUpdate}){this.series=series;this.requestUpdate=requestUpdate;}
    detached(){this.series=null;this.requestUpdate=null;}
    paneViews(){return [this];}renderer(){return this;}zOrder(){return 'bottom';}
    draw(target){
        if(!this.series||!profile)return;
        target.useMediaCoordinateSpace(({context,mediaSize})=>{
            const config=styles(),width=mediaSize.width*.1*(config.vp_histogram?.width||2),right=mediaSize.width-5;
            const area=config.vp_value_area;
            if(area?.visible){
                const y1=this.series.priceToCoordinate(profile.levels.vp_va_high),y2=this.series.priceToCoordinate(profile.levels.vp_va_low);
                if(y1!==null&&y2!==null){context.save();context.fillStyle=area.color;context.globalAlpha=area.opacity/100;context.fillRect(right-width,y1,width,y2-y1);
                    context.globalAlpha=1;context.strokeStyle=area.color;context.lineWidth=area.width;context.setLineDash(area.style===1?[2,3]:area.style===2?[6,4]:[]);context.strokeRect(right-width,y1,width,y2-y1);context.restore();}
            }
            for(const row of histogramRows(profile,config)){
                const y1=this.series.priceToCoordinate(row.high),y2=this.series.priceToCoordinate(row.low);
                if(y1===null||y2===null||y2<0||y1>mediaSize.height)continue;
                const style=config[row.key],length=width*row.fraction;
                context.save();context.fillStyle=style.color;context.globalAlpha=style.opacity/100;
                context.fillRect(right-length,y1,length,Math.max(1,y2-y1-1));context.restore();
            }
        });
    }
}
export function mount(){
    primitive=new Profile();getSeries().attachPrimitive(primitive);
    status=document.createElement('div');status.className='volume-profile-status';status.setAttribute('role','status');
    Object.assign(status.style,{position:'absolute',right:'8px',top:'30px',fontSize:'11px',color:'#aab4c2',pointerEvents:'none',zIndex:2});
    document.getElementById('chart').append(status);
}
export function update(chart,data){
    const config=styles(),enabled=Object.entries(config).some(([k,v])=>k.startsWith('vp_')&&v.visible);
    const latest=(data.bars||[]).findLast(b=>!b.provisional),candidate=data.volumeProfile;
    profile=enabled&&candidate?.status==='ready'&&candidate.as_of===latest?.open_time?candidate:null;
    for(const line of axis)getSeries().removePriceLine(line);axis=[];
    if(enabled){
        const levels=profile?.levels||latest?.features||{};
        for(const key of ['vp_poc','vp_va_high','vp_va_low'])if(config[key]?.visible&&Number.isFinite(levels[key])){
            const s=config[key];axis.push(getSeries().createPriceLine({price:levels[key],color:s.color,lineWidth:s.width,lineStyle:s.style,lineVisible:true,axisLabelVisible:true,title:''}));
        }
    }
    status.hidden=!enabled;
    status.textContent=profile?`Volume profile · ${profile.lookback} closed candles`:'Waiting for closed-candle volume profile';
    primitive.requestUpdate?.();
}
export function updateLive(){/* Current profile changes on committed closed candles only. */}
export function getProfile(){return profile;}
