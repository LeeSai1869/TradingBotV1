// Project confirmed feature events with the same touch + close invalidation rule
// as fair_value_gaps.py. Nearest selection changes never end another gap.
export const HTF={ '4h':14400000,'1d':86400000,'1w':604800000 };
export function intervalMs(interval){
    if(interval==='1M')return 31*86400000;
    const m=/^(\d+)([mhdw])$/.exec(interval||'');
    return m?Number(m[1])*({m:60000,h:3600000,d:86400000,w:604800000}[m[2]]):0;
}
export function fvgSegments(bars,config,{source='',target='',endTime=null,seeds=[]}={}){
    const confirmed=bars.filter(b=>!b.provisional&&b.client),result=[],active=new Map(),retired=new Set();
    const higher=!!source&&source!==target,step=intervalMs(target||source);
    if(higher&&(!HTF[source]||HTF[source]<=step))return [];
    const keyFor=side=>higher?`${side}_fvg_${source}_zones`:HTF[target]&&config[`${side}_fvg_${target}_zones`]?.visible?`${side}_fvg_${target}_zones`:`${side}_fvg_zones`;
    let previous=null;
    for(let i=0;i<confirmed.length;i++){
        const bar=confirmed[i],f=bar.features||{},c=bar.client;
        if(previous&&c.open_time!==undefined&&previous.close_time!==undefined&&c.open_time!==previous.close_time+1){
            // Unknown source history cannot be treated as uninterrupted validity.
            for(const zone of active.values()){zone.truncated=true;zone.until=zone.end;}
            active.clear();
        }
        const end=higher?Math.floor(c.close_time/step)*step/1000:bar.time;
        for(const [id,zone] of active){
            zone.end=end;
            const touched=c.low<=zone.high&&c.high>=zone.low;
            if(touched&&(zone.side==='bull'?c.close<zone.low:c.close>zone.high)){
                zone.invalidated=true;active.delete(id);retired.add(id);
            }
        }
        for(const side of ['bull','bear']){
            const key=keyFor(side);if(!config[key]?.visible)continue;
            const add=(identity,low,high,start)=>{
                const id=side+':'+identity;
                if(active.has(id)||retired.has(id)||!Number.isFinite(low)||!Number.isFinite(high)||high<=low)return;
                const zone={key,identity:id,side,source,low,high,start,end:Math.max(start,end),invalidated:false};
                result.push(zone);active.set(id,zone);
            };
            const available=higher?(c.close_time+1)/1000:bar.time;
            if(f[`qualified_${side}_fvg`]===true||f[`qualified_${side}_fvg`]===1){
                add(bar.time,f[`${side}_fvg_low`],f[`${side}_fvg_high`],available);
            }
            const prefix=`nearest_${side}_fvg_`,created=f[prefix+'created_bar'],age=f[prefix+'age'];
            if(created==null)continue;
            const birth=Number.isInteger(age)&&age>=0&&i-age>=0?confirmed[i-age]:null;
            // A nearest observation can seed an older gap omitted by the loaded
            // window, but is never evidence of a gap's invalidation.
            const identity=birth?birth.time:`prior:${created}`;
            const low=f[prefix+'low'],high=f[prefix+'high'];
            if([...active.values()].some(z=>z.side===side&&z.low===low&&z.high===high))continue;
            const start=birth?(higher?(birth.client.close_time+1)/1000:birth.time):available;
            add(identity,low,high,start);
        }
        for(const side of ['bull','bear']){
            const score=f[`nearest${side}_fvg_reaction_score`];
            const low=f[`nearest_${side}_fvg_low`],high=f[`nearest_${side}_fvg_high`];
            if(Number.isFinite(score))for(const zone of active.values())if(zone.side===side&&zone.low===low&&zone.high===high){zone.score=score;zone.scoreTime=bar.time;}
        }
        previous=c;
    }
    for(const seed of seeds){
        const key=keyFor(seed.side),identity=seed.side+':'+(seed.older?`prior:${seed.created}`:seed.time);
        if(!config[key]?.visible||retired.has(identity))continue;
        const existing=result.find(z=>z.identity===identity||!z.invalidated&&z.side===seed.side&&z.low===seed.low&&z.high===seed.high);
        if(existing){existing.score=seed.score;existing.scoreTime=seed.score_time;continue;}
        if(!Number.isFinite(seed.low)||!Number.isFinite(seed.high)||seed.high<=seed.low)continue;
        const start=higher&&!seed.older?(seed.close_time+1)/1000:seed.time;
        const zone={key,identity,score:seed.score,scoreTime:seed.score_time,side:seed.side,source,low:seed.low,high:seed.high,start,end:start,invalidated:false};
        result.push(zone);active.set(identity,zone);
    }
    const last=confirmed.at(-1);
    if(last){
        const knownEnd=higher?(last.client.close_time+1+HTF[source])/1000:(Number.isFinite(last.client.close_time)?(last.client.close_time+1)/1000:last.time);
        for(const zone of active.values()){zone.until=knownEnd;zone.end=Math.max(zone.end,Math.min(endTime??last.time,knownEnd));}
    }
    return result.filter(z=>endTime==null||z.start<=endTime);
}
