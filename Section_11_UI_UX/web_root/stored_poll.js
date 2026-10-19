// One local combined-stream request: stored bars plus the server's provisional
// live snapshot. Exchange I/O is independent of HTTP/history requests.
let timer = null;
let cycle = 0;

async function run(token, interval) {
    try {
        await DataCache.refreshStored();
    } catch (error) {
        console.warn("[stored bars] refresh failed:", error);
    } finally {
        if (token === cycle) timer = setTimeout(() => run(token, interval), interval);
    }
}
export function stop() {
    ++cycle;
    if (timer !== null) clearTimeout(timer);
    timer = null;
}
export function start(interval = 5000) {
    stop();
    if (Number.isFinite(interval) && interval > 0) {
        const token = cycle;
        timer = setTimeout(() => run(token, interval), interval);
    }
}
