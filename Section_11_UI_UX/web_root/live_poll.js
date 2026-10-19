// Poll serially: a slow network request must not overlap the next tick.
import * as candles from "../overlays/candles/index.js";
import * as flags from "../panels/flags/index.js";

let timer = null;
let cycle = 0;
let lastRefresh = 0;
let lastGeneration = -1;

async function tick(token) {
    const symbol = document.getElementById("symbol").value;
    const interval = document.getElementById("interval").value;
    const generation = DataCache._reloadGeneration;
    const current = () => token === cycle && !DataCache.loading &&
        generation === DataCache._reloadGeneration &&
        symbol === DataCache.symbol && interval === DataCache.timeframe &&
        symbol === document.getElementById("symbol").value &&
        interval === document.getElementById("interval").value;
    if (!symbol || !interval || !current()) return;
    if (generation !== lastGeneration) {
        lastRefresh = 0;
        lastGeneration = generation;
    }

    try {
        const r = await fetch(
            `/api/live_candle?symbol=${encodeURIComponent(symbol)}` +
            `&interval=${encodeURIComponent(interval)}`,
            { cache: "no-store" }
        );
        const bar = r.ok ? await r.json() : null;
        if (!current()) return;
        if (bar?.time != null && DataCache.atLiveEdge) {
            const last = DataCache.klines.at(-1);
            // Refresh derived rows as well as candles. The ingestion process
            // may commit the newly closed candle after Binance rolls over.
            if (!last || Date.now() - lastRefresh >= 5000 ||
                bar.time * 1000 >= DataCache._shiftMs(last.time * 1000, 2)) {
                await DataCache.refreshLive();
                lastRefresh = Date.now();
                if (!current()) return;
            }
            if (DataCache.atLiveEdge) candles.updateLive(bar);
        }
    } catch (e) {
        console.warn("[live] candle refresh failed:", e);
    }

    if (!current()) return;
    try {
        const r = await fetch(
            `/api/flags_current?symbol=${encodeURIComponent(symbol)}` +
            `&interval=${encodeURIComponent(interval)}`,
            { cache: "no-store" }
        );
        const result = r.ok ? await r.json() : null;
        if (current()) {
            DataCache.flags_current = result;
            flags.update(null, { flags_current: result });
        }
    } catch (e) {
        console.warn("[live] flags refresh failed:", e);
    }
}

async function run(token) {
    try {
        await tick(token);
    } finally {
        if (token === cycle) timer = setTimeout(() => run(token), 1000);
    }
}

export function start() {
    stop();
    void run(cycle);
}

export function stop() {
    ++cycle;
    if (timer !== null) clearTimeout(timer);
    timer = null;
}
