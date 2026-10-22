// VISUAL: BUY/SELL markers from each canonical bar's stored ADCN state.
import { getSeries } from "../candles/index.js";
export const name = "markers";
let markersPrimitive = null;

export function mount() {}

export function update(chart, data, options = {}) {
    const series = getSeries();
    if (!series) return;
    const markers = [];
    for (const bar of options.visible === false ? [] : (data.bars || [])) {
        const row = bar.adcn;
        const sig = String(row?.signal_type || "").toUpperCase();
        if (sig !== "BUY" && sig !== "SELL") continue;
        const isBuy = sig === "BUY";
        markers.push({
            time: bar.time,
            position: isBuy ? "belowBar" : "aboveBar",
            color: isBuy ? "#4caf50" : "#f44336",
            shape: "circle",
            text: `${isBuy ? "B" : "S"}${Number.isFinite(row.final_score) ? ` | ${Math.round(row.final_score)}` : ""}`,
            size: 1.7,
        });
    }
    markers.sort((a, b) => a.time - b.time);
    if (typeof LightweightCharts.createSeriesMarkers === "function") {
        if (!markersPrimitive) {
            markersPrimitive = LightweightCharts.createSeriesMarkers(series, markers);
        } else {
            markersPrimitive.setMarkers(markers);
        }
    }
}
