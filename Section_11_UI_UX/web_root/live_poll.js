// ============================================================
// LIVE POLL — every 1 second:
//   - fetch forming candle, detect bar-close, refetch if needed
//   - fetch current flags, update panel
// ============================================================

import * as candles from "../overlays/candles/index.js";
import * as flags   from "../panels/flags/index.js";

let timer = null;

async function tick() {
    const symbol = document.getElementById("symbol").value;
    const interval = document.getElementById("interval").value;
    if (!symbol || !interval) return;

    // --- 1. Forming candle ---
    let bar = null;
    try {
        const r = await fetch(
            `/api/live_candle?symbol=${symbol}&interval=${interval}&_=` + Date.now(),
            { cache: "no-store" }
        );
        if (r.ok) bar = await r.json();
    } catch (e) { /* silent */ }

    if (bar && bar.time != null) {
        const stepSec = (DataCache._intervalMs[interval] || 60000) / 1000;
        const last = DataCache.klines[DataCache.klines.length - 1];

        // If the forming bar is two or more intervals past the last loaded
        // bar, a bar (or more) has closed and we don't have it yet.
        const needsRefetch =
            last && (bar.time - last.time) >= stepSec * 2;

        if (DataCache.atLiveEdge) {
            if (needsRefetch) {
                console.log(
                    "[LIVE CLOSED BAR PENDING]",
                    "last=" + (last ? last.time : "none"),
                    "forming=" + bar.time
                );
            } else {
                candles.updateLive(bar);
            }
        }
    }

    // --- 2. Current flags ---
    try {
        const r = await fetch(
            `/api/flags_current?symbol=${symbol}&interval=${interval}&_=` + Date.now(),
            { cache: "no-store" }
        );
        if (r.ok) {
            const f = await r.json();
            flags.update(null, { flags_current: f });
        }
    } catch (e) { /* silent */ }
}

export function start() {
    if (timer) clearInterval(timer);
    timer = setInterval(tick, 1000);
    tick();
}

export function stop() {
    if (timer) { clearInterval(timer); timer = null; }
}
