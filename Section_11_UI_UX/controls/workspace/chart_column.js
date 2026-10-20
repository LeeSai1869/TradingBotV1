// Project the same canonical bar already delivered to the chart. No I/O.
export function chartColumn(cache, symbol, interval, fields, now=Date.now()) {
    if(!cache || cache.loading || !cache.atLiveEdge || cache.symbol!==symbol || cache.timeframe!==interval || !cache.latestBar)return null;
    const bar=cache.liveStatus==='live' && cache.formingBar ? cache.formingBar : cache.latestBar;
    const values=Object.fromEntries(fields.map(field=>{
        const [group,key]=field.split('.');const value=bar[group]?.[key]??null;
        return [field,typeof value==='number' && !Number.isFinite(value)?null:value];
    }));
    const close=bar.client.close_time, duration=close-bar.open_time+1;
    return {interval,open_time:bar.open_time,close_time:close,values,
        active:cache.liveStatus!=='inactive',stale:now-close>2*duration,
        status:bar.provisional?'live provisional candle':'stored closed candle',source:'chart cache'};
}
