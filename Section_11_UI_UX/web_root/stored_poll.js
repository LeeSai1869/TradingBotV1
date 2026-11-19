// Stored history and live quotes have independent schedules and timeouts.
let storedTimer = null;
let liveTimer = null;
let cycle = 0;

async function run(token, interval, live) {
    try {
        if (live) await DataCache.refreshLive();
        else await DataCache.refreshStored({includeLive: false});
    } catch (error) {
        console.warn(live ? "[live quote] refresh failed:" : "[stored bars] refresh failed:", error);
    } finally {
        if (token === cycle) schedule(token, interval, live);
    }
}

function schedule(token, interval, live) {
    const timer = setTimeout(() => run(token, interval, live), interval);
    if (live) liveTimer = timer;
    else storedTimer = timer;
}

export function stop() {
    ++cycle;
    if (storedTimer !== null) clearTimeout(storedTimer);
    if (liveTimer !== null) clearTimeout(liveTimer);
    storedTimer = liveTimer = null;
}
export function start(interval = 5000, live = false) {
    stop();
    if (Number.isFinite(interval) && interval > 0) {
        schedule(cycle, interval, false);
        if (live) schedule(cycle, 1000, true);
    }
}
