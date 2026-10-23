// One current closed-candle profile, projected from the runner's stored bins.
import {getSeries} from '../candles/index.js';
export const name='volumeProfile';
let primitive,status,profile=null;
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
// Pixel presentation does not subdivide or otherwise change the stored bins.
export function barGeometry(row,coordinate,paneWidth,config){
    const a=coordinate(row.high),b=coordinate(row.low);
    if(a===null||b===null)return null;
    const available=Math.abs(b-a);
    if(!available)return null;
    const height=Math.min(available*.8,config.vp_histogram?.thickness??3);
    const width=paneWidth*(config.vp_histogram?.lengthPercent??45)/100*row.fraction;
    return {left:paneWidth-5-width,top:(a+b)/2-height/2,width,height};
}
class Profile {
    attached({series,requestUpdate}){this.series=series;this.requestUpdate=requestUpdate;}
    detached(){this.series=null;this.requestUpdate=null;}
    paneViews(){return [this];}renderer(){return this;}zOrder(){return 'bottom';}
    draw(target){
        if(!this.series||!profile)return;
        target.useMediaCoordinateSpace(({context,mediaSize})=>{
            const config=styles();
            for(const row of histogramRows(profile,config)){
                const box=barGeometry(row,value=>this.series.priceToCoordinate(value),mediaSize.width,config);
                if(!box||box.top+box.height<0||box.top>mediaSize.height)continue;
                const style=config[row.key];
                context.save();context.fillStyle=style.color;context.globalAlpha=style.opacity/100;
                context.fillRect(box.left,box.top,box.width,box.height);context.restore();
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
    const config=styles(),enabled=['vp_histogram','vp_hvn_nodes','vp_lvn_nodes'].some(key=>config[key]?.visible);
    const latest=(data.bars||[]).findLast(b=>!b.provisional),candidate=data.volumeProfile;
    profile=enabled&&candidate?.status==='ready'&&candidate.as_of===latest?.open_time?candidate:null;
    status.hidden=!enabled;
    status.textContent=profile?`Volume profile · ${profile.lookback} closed candles`:'Waiting for closed-candle volume profile';
    primitive.requestUpdate?.();
}
export function updateLive(){/* Current profile changes on committed closed candles only. */}
export function getProfile(){return profile;}
