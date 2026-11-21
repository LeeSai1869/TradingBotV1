// Paste this entire file into chart DevTools in BOTH desktop and browser.
// Keep BTC 5m visible, then pan/zoom for ten seconds. No chart settings/data change.
(async () => {
    const samples=[],started=performance.now();let last=started;
    const longTasks=[];let observer;
    try {observer=new PerformanceObserver(list=>longTasks.push(...list.getEntries().map(e=>({ms:Math.round(e.duration),start:Math.round(e.startTime)}))));observer.observe({type:'longtask',buffered:false});}catch{}
    await new Promise(resolve=>{
        const frame=now=>{samples.push(now-last);last=now;if(now-started<10000)requestAnimationFrame(frame);else resolve();};
        requestAnimationFrame(frame);
    });
    observer?.disconnect();
    const cache=window.DataCache,chart=document.querySelector('#chart');
    const quantile=p=>{const sorted=[...samples].sort((a,b)=>a-b);return Math.round(sorted[Math.min(sorted.length-1,Math.floor(sorted.length*p))]||0);};
    let zones=null;
    try {zones=(await import('/overlays/zones/index.js')).getProjectionStats?.();}catch(error){zones={error:String(error)};}
    const resources=performance.getEntriesByType('resource').filter(e=>{
        try{return new URL(e.name).pathname.startsWith('/api/');}catch{return false;}
    }).slice(-20).map(e=>({route:new URL(e.name).pathname,ms:Math.round(e.duration),transfer_bytes:e.transferSize,decoded_bytes:e.decodedBodySize}));
    const report={user_agent:navigator.userAgent,desktop:!!(window.__TAURI_INTERNALS__||window.__TAURI__),origin:location.origin,
        visibility:document.visibilityState,dpr:devicePixelRatio,chart_size:chart?{width:chart.clientWidth,height:chart.clientHeight}:null,
        sample_seconds:Math.round((performance.now()-started)/1000),frames:samples.length,frame_ms:{p50:quantile(.5),p95:quantile(.95),max:Math.round(Math.max(0,...samples))},
        long_tasks:longTasks.slice(-20),market:{symbol:cache?.symbol,interval:cache?.timeframe,cached_bars:cache?.bars?.length,
            rendered_bars:cache?.renderBars?.length,loading:cache?.loading,live_status:cache?.liveStatus,last_stored_open:cache?.bars?.at(-1)?.open_time,
            last_live_open:cache?.formingBar?.open_time,live_price:cache?.liveQuote?.client?.close},zones,
        render_timings:window.ChartRenderTimings??[],recent_requests:resources};
    console.log('CHART RUNTIME COMPARISON',JSON.stringify(report));
    return report;
})();
