export function fieldValue(bar,field){
    if(!bar)return null;
    const [group,key]=field.split('.'),context=bar.signal_context||{},confidence=bar.confidence||context.confidence||{};
    if(group==='signal_context')return context[key]??null;
    if(group==='confidence')return (key==='signal_score'?confidence[`${context.side?.toLowerCase()}_score`]:confidence[key])??null;
    if(group==='opportunity'){
        const [side,level,...parts]=key.split('_'),metric=parts.join('_');
        const rows=(bar.opportunity||context.opportunity)?.areas?.[side==='sell'?'resistance':'support']||[];
        return rows[Number(level)-1]?.[metric==='families'?'confluence_families':metric]??null;
    }
    return bar[group]?.[key]??null;
}
// Project the same canonical bar already delivered to the chart. No I/O.
export function chartColumn(cache, symbol, interval, fields, now=Date.now()) {
    if(!cache || cache.loading || !cache.atLiveEdge || cache.symbol!==symbol || cache.timeframe!==interval || !cache.latestBar)return null;
    const bar=cache.liveStatus==='live' && cache.formingBar ? cache.formingBar : cache.latestBar;
    const values=Object.fromEntries(fields.map(field=>{
        const value=fieldValue(['confidence','signal_context','opportunity'].includes(field.split('.')[0])?cache.latestBar:bar,field);
        return [field,typeof value==='number' && !Number.isFinite(value)?null:value];
    }));
    const close=bar.client.close_time, duration=close-bar.open_time+1;
    return {interval,open_time:bar.open_time,close_time:close,values,
        active:cache.liveStatus!=='inactive',stale:now-close>2*duration,
        status:bar.provisional?'live provisional candle':'stored closed candle',source:'chart cache'};
}
