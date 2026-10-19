// VISUAL: ema50 — EMA-50 line from features packet.
export const name = "ema50";
let series = null;

export function mount(chart) {
    series = chart.addSeries(LightweightCharts.LineSeries, {
        color: "#f5c542",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
    });
}

export function update(chart, data) {
    if (!series) return;
    const features = data.features || [];
    const points = [];
    for (const row of features) {
        if (row.ema50 == null) continue;
        points.push({ time: row.time, value: row.ema50 });
    }
    series.setData(points);
}
