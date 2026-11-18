// Stored history and live prices have independent, nonoverlapping poll loops.
let timers = [];
let cycle = 0;
async function run(token, interval, live) {
    try { await (live ? DataCache.refreshLive() : DataCache.refreshStored()); }
    catch(error) { console.warn(live ? '[live candle]' : '[stored bars]',error); }
    finally {
        if(token===cycle)timers[live?1:0]=setTimeout(()=>run(token,interval,live),interval);
    }
}
export function stop() {
    ++cycle;for(const timer of timers)clearTimeout(timer);timers=[];
}
export function start(interval=5000, live=false) {
    stop();
    if(Number.isFinite(interval)&&interval>0){
        const token=cycle;
        timers[0]=setTimeout(()=>run(token,interval,false),interval);
        if(live)timers[1]=setTimeout(()=>run(token,1000,true),1000);
    }
}
