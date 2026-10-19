// PANEL: decision state from the latest combined stored bar.
export const name = "flags";
function el(id) { return document.getElementById(id); }
function colorForSignal(sig) {
    if (!sig) return "#ddd";
    if (sig.indexOf("BUY") === 0) return "#4caf50";
    if (sig.indexOf("SELL") === 0) return "#f44336";
    return "#888";
}
export function mount() {}
export function update(chart, data) {
    const bar = data.latestBar;
    const f = bar?.adcn || {};
    const tfEl    = el("flags-tf");
    const sigEl   = el("flags-signal");
    const scoreEl = el("flags-score");
    const stateEl = el("flags-state");
    const memEl   = el("flags-memory");
    if (tfEl) tfEl.textContent = "tf: " + (bar?.interval || data.timeframe || "—");
    if (sigEl) {
        sigEl.textContent = "signal: " + (f.signal_type || "—");
        sigEl.style.color = colorForSignal(f.signal_type);
    }
    if (scoreEl) scoreEl.textContent =
        "score: " + ((f.final_score >= 0 ? "+" : "") + (f.final_score || 0).toFixed(2));
    if (stateEl) stateEl.textContent = "state: " + (f.decision_state || "—");
    if (memEl)   memEl.textContent   = "signal history: " + (bar?.adcn ? "stored bar " + new Date(bar.open_time).toISOString() : "no stored decision");
}
