// Paste into chart DevTools in BOTH desktop and browser; pan for ten seconds.
// Observes this sample only. Does not alter chart settings or market data.
(async () => {
    const samples=[],started=performance.now();let last=started;
    const renders=[],requests=[],longTasks=[],restores=[];
    let resourceObserver,longObserver;
    const supported=typeof PerformanceObserver!=='undefined'?(PerformanceObserver.supportedEntryTypes||[]):[];
    const collectResources=list=>requests.push(...list.getEntries());
    if(supported.includes('resource')){
        resourceObserver=new PerformanceObserver(collectResources);
        resourceObserver.observe({type:'resource',buffered:false});
    }
    if(supported.includes('longtask')){
        longObserver=new PerformanceObserver(list=>longTasks.push(...list.getEntries().map(e=>({ms:Math.round(e.duration),start:Math.round(e.startTime-started)}))));
        longObserver.observe({type:'longtask',buffered:false});
    }
    // Original timing lists can predate this test, and the global resource buffer
    // may already be full. Observe new work without clearing shared diagnostics.
    for(const name of ['updateAll','updateLive','updateLiquidity']){
        const owner=window.Composer,original=owner?.[name];if(typeof original!=='function')continue;
        function measured(...args){
            const at=performance.now();
            try{return original.apply(this,args);}
            finally{if(renders.length<1000)renders.push({method:name,op:args[2]||name,
                start_ms:Math.round(at-started),ms:Math.round((performance.now()-at)*100)/100,
                bars:args[1]?.bars?.length??0});}
        }
        owner[name]=measured;
        restores.push(()=>{if(owner[name]===measured)owner[name]=original;});
    }
    try{
        await new Promise(resolve=>{
            const frame=now=>{samples.push(now-last);last=now;if(now-started<10000)requestAnimationFrame(frame);else resolve();};
            requestAnimationFrame(frame);
        });
    }finally{
        if(resourceObserver)requests.push(...resourceObserver.takeRecords());
        resourceObserver?.disconnect();longObserver?.disconnect();
        for(const restore of restores)restore();
    }
    const ended=performance.now(),cache=window.DataCache,chart=document.querySelector('#chart');
    const quantile=p=>{const sorted=[...samples].sort((a,b)=>a-b);return Math.round(sorted[Math.min(sorted.length-1,Math.floor(sorted.length*p))]||0);};
    let zones=null;
    try{zones=(await import('/overlays/zones/index.js')).getProjectionStats?.();}catch(error){zones={error:String(error)};}
    const entries=resourceObserver?requests:performance.getEntriesByType('resource');
    const resources=entries.filter(e=>{
        try{return e.startTime>=started&&e.responseEnd<=ended&&new URL(e.name).pathname.startsWith('/api/');}catch{return false;}
    }).slice(-30).map(e=>({route:new URL(e.name).pathname,start_ms:Math.round(e.startTime-started),ms:Math.round(e.duration),transfer_bytes:e.transferSize,decoded_bytes:e.decodedBodySize}));
    const report={version:2,user_agent:navigator.userAgent,desktop:!!(window.__TAURI_INTERNALS__||window.__TAURI__),origin:location.origin,
        visibility:document.visibilityState,dpr:devicePixelRatio,chart_size:chart?{width:chart.clientWidth,height:chart.clientHeight}:null,
        sample_seconds:Math.round((ended-started)/1000),frames:samples.length,frame_ms:{p50:quantile(.5),p95:quantile(.95),max:Math.round(Math.max(0,...samples))},
        long_task_observer_supported:supported.includes('longtask'),long_tasks:longTasks.slice(-20),
        visible_features:Object.entries(window.Composer?.config?.featureStyles||{}).filter(([,v])=>v.visible).map(([k])=>k).sort(),
        market:{symbol:cache?.symbol,interval:cache?.timeframe,cached_bars:cache?.bars?.length,rendered_bars:cache?.renderBars?.length,
            loading:cache?.loading,live_status:cache?.liveStatus,last_stored_open:cache?.bars?.at(-1)?.open_time,
            last_live_open:cache?.formingBar?.open_time,live_price:cache?.liveQuote?.client?.close},zones,
        render_timings:renders,recent_requests:resources};
    console.log('CHART RUNTIME COMPARISON',JSON.stringify(report));return report;
})();
