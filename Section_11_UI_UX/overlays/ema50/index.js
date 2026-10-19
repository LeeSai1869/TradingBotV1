// VISUAL: EMA-50 from the same stored bars used by the candle series.
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

export function update(chart, data, options = {}) {
    if (!series) return;
    series.applyOptions({ visible: options.visible !== false });
    const bars = data.bars || [];
    const points = [];
    for (const bar of bars) {
        const value = bar.features?.ema50;
        if (value == null || !Number.isFinite(value)) continue;
        points.push({ time: bar.time, value });
    }
    series.setData(points);
}
