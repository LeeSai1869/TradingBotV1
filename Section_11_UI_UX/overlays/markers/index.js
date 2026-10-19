// VISUAL: markers — draws BUY/SELL markers from flags_history.
import { getSeries } from "../candles/index.js";
export const name = "markers";
let markersPrimitive = null;

export function mount() {}

export function update(chart, data) {
    const series = getSeries();
    if (!series) return;
    if (markersPrimitive) {
        try { series.detachPrimitive(markersPrimitive); } catch (e) {}
        markersPrimitive = null;
    }
    const history = data.flags_history || [];
    const markers = [];
    for (const row of history) {
        const sig = String(row.signal_type || "").toUpperCase();
        if (sig !== "BUY" && sig !== "SELL") continue;
        const t = Math.floor((row.bar_time || 0) / 1000);
        if (!t) continue;
        const isBuy = sig === "BUY";
        markers.push({
            time: t,
            position: isBuy ? "belowBar" : "aboveBar",
            color: isBuy ? "#4caf50" : "#f44336",
            shape: "circle",
            text: `${isBuy ? "B" : "S"} | ${Math.round(row.final_score || 0)}`,
            size: 1.7,
        });
    }
    markers.sort((a, b) => a.time - b.time);
    if (typeof LightweightCharts.createSeriesMarkers === "function") {
        markersPrimitive = LightweightCharts.createSeriesMarkers(series, markers);
    }
}
