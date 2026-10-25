// Read the established engine range. Missing/invalidated structure ends coverage;
// bounds are never inferred from recent highs/lows or smoothed into new levels.
export function structureSegments(bars,config){
    const key='structure_range_zones';if(!config[key]?.visible)return [];
    const result=[];let current=null;
    for(const bar of bars){
        if(bar.provisional)continue;
        const f=bar.features||{},low=f.structure_range_low,high=f.structure_range_high;
        if(!f.current_structure||!Number.isFinite(low)||!Number.isFinite(high)||high<=low){current=null;continue;}
        const identity=f.structure_origin_bar??f.structure_start_bar;
        if(identity==null){current=null;continue;}
        if(!current||current.identity!==identity){current={key,identity,low,high,start:bar.time,end:bar.time,history:[{time:bar.time,low,high}]};result.push(current);}
        else if(current.low!==low||current.high!==high){current.history.push({time:bar.time,low,high});current.low=low;current.high=high;}
        current.end=bar.time;
    }
    return result;
}
