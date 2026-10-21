import {featurePriceFormat} from '../../web_root/value_format.js';
// EMA overlays read the same combined stored bars as candles.
// Keep the legacy name so existing display.ema50 configuration stays valid.
export const name = "ema50";
const PERIODS = [7, 25, 50, 100, 200, 300];
const series = new Map();

export function mount(chart) {
    for (const period of PERIODS) {
        series.set(period, chart.addSeries(LightweightCharts.LineSeries, {
            color: "#f5c542", lineWidth: 2,
            visible: period === 50,
            priceLineVisible: false, lastValueVisible: true,
            crosshairMarkerVisible: false,
        }));
    }
}

export function update(chart, data, options = {}) {
    const config = window.Composer?.config.ema || {};
    const periods = config.periods || [50];
    for (const [period, line] of series) {
        const style = window.Composer?.config.featureStyles?.[`ema${period}`];
        const visible = options.visible !== false && (style ? style.visible : periods.includes(period));
        line.applyOptions({ priceFormat:featurePriceFormat, visible, lastValueVisible: visible, color: style?.color || config.color || "#f5c542",
            lineWidth: style?.width || config.lineWidth || 2, lineStyle: style?.style ?? config.lineStyle ?? 0 });
        if (!visible) continue;
        const points = [];
        for (const bar of data.bars || []) {
            const value = bar.features?.[`ema${period}`];
            if (value == null || !Number.isFinite(value)) continue;
            points.push({ time: bar.time, value });
        }
        line.setData(points);
    }
}

// Update the existing point on each tick; never append another copy of the candle.
export function updateLive(chart, bar) {
    if (!bar) return;
    for (const [period, line] of series) {
        const value = bar.features?.[`ema${period}`];
        line.update(Number.isFinite(value) ? {time: bar.time, value} : {time: bar.time});
    }
}
