// Zone lifetimes come from committed engine events, after its merge/invalidation
// rules. Nearest selection is a price label, never evidence of zone destruction.
export function srSegments(bars,config,snapshot=null){
    const result=[],active=new Map(),state=new Map();
    const rows=bars.filter(b=>!b.provisional);
    const decoded=rows.map(bar=>{
        try{const events=JSON.parse(bar.features?.sr_zone_events??'null');return Array.isArray(events)?events:null;}
        catch{return null;}
    });
    if(!decoded.some(Boolean))return legacySegments(rows,config);
    // Undo events to recover zones born before the loaded window. Removals
    // retain their prior bounds, so retired zones can also be reconstructed.
    if(snapshot){
        for(const [id,z] of Object.entries(snapshot.zones||{}))state.set(id,z);
        for(let i=rows.length-1;i>=0;i--){
            if(rows[i].time>snapshot.through)continue;
            for(const event of [...(decoded[i]||[])].reverse()){
                if(event.before)state.set(event.id,event.before);else state.delete(event.id);
            }
        }
    }
    const keys=z=>[`${z.institutional?'inst_':''}${z.side}_zones`];
    function sync(time){
        const seen=new Set();
        for(const [id,z] of state){
            if(!Number.isFinite(z.low)||!Number.isFinite(z.high)||z.high<=z.low)continue;
            for(const key of keys(z)){
                if(!config[key]?.visible)continue;
                const identity=key+':'+id;seen.add(identity);
                let item=active.get(identity);
                if(!item){item={key,identity,low:z.low,high:z.high,start:time,end:time,history:[{time,low:z.low,high:z.high}]};result.push(item);active.set(identity,item);}
                if(item.low!==z.low||item.high!==z.high){item.history.push({time,low:z.low,high:z.high});item.low=z.low;item.high=z.high;}
                item.end=time;
            }
        }
        for(const [id,item] of active)if(!seen.has(id)){item.end=time;item.invalidated=true;active.delete(id);}
    }
    if(rows.length)sync(rows[0].time);
    let previous=null;
    for(let i=0;i<rows.length;i++){
        const bar=rows[i],events=decoded[i];
        if(events===null||previous?.client?.close_time!==undefined&&bar.client?.open_time!==previous.client.close_time+1){
            // Unknown history or a masked repair is not continued validity.
            for(const item of active.values())item.truncated=true;
            active.clear();state.clear();previous=bar;continue;
        }
        for(const event of events){if(event.removed)state.delete(event.id);else state.set(event.id,event);}
        sync(bar.time);previous=bar;
    }
    for(const item of active.values())item.until=previous?.client?.close_time!==undefined?(previous.client.close_time+1)/1000:item.end;
    return result;
}

function legacySegments(bars,config){
    // Old rows lack lifecycle evidence: join repeated observations of one ID,
    // without extending past its last observation or inventing invalidation.
    const result=[];
    for(const side of ['support','resistance','inst_support','inst_resistance']){
        const key=side+'_zones';if(!config[key]?.visible)continue;
        const seen=new Map();
        for(const bar of bars){
            const f=bar.features||{},low=f[side+'_zone_low'],high=f[side+'_zone_high'],id=f['nearest_'+side+'_zone_id'];
            if(!Number.isFinite(low)||!Number.isFinite(high)||high<=low)continue;
            const identity=id??`${low}:${high}`;let item=seen.get(identity);
            if(!item){item={key,identity,low,high,start:bar.time,end:bar.time};result.push(item);seen.set(identity,item);}
            if(item.low!==low||item.high!==high){item.history??=[{time:item.start,low:item.low,high:item.high}];item.history.push({time:bar.time,low,high});item.low=low;item.high=high;}
            item.end=bar.time;
        }
    }
    return result;
}
