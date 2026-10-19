// VISUAL: candles — draws price candles from klines packet.

export const name = "candles";

let series = null;

let priceFormat = {
    type: "price",
    precision: 2,
    minMove: 0.01,
};

export function mount(chart) {
    series = chart.addSeries(
        LightweightCharts.CandlestickSeries,
        {
            upColor: "#26a69a",
            downColor: "#ef5350",
            borderVisible: false,
            wickUpColor: "#26a69a",
            wickDownColor: "#ef5350",
            priceFormat,
            priceLineVisible: false,
        }
    );
}

function _toPoints(klines) {
    return (klines || []).map(k => ({
        time: k.time,
        open: k.open,
        high: k.high,
        low: k.low,
        close: k.close,
    }));
}

// Full historical packet replacement.
// Used for initial load, symbol change, timeframe change and explicit reload.
export function update(chart, data, options = {}) {
    if (!series) return;

    series.setData(_toPoints(data.klines));

    // Historical 500-bar window rotation must not continually
    // reset the user's vertical scale. Full/reset loads may
    // establish autoscale; the dedicated "A" control remains
    // responsible for explicit user-requested autoscaling.
    if (
        options.resetViewport &&
        chart &&
        chart.priceScale
    ) {
        chart
            .priceScale("right")
            .applyOptions({ autoScale: true });
    }

    if (
        options.resetViewport &&
        chart &&
        chart.timeScale
    ) {
        const n = (data.klines || []).length;

        if (n > 0) {
            const barsToShow = Math.min(300, n);

            chart.timeScale().setVisibleLogicalRange({
                from: Math.floor(n - barsToShow),
                to: Math.floor(n),
            });
        }
    }
}

// Forming Binance candle only.
export function updateLive(bar) {
    if (!series || !bar || bar.time == null) return;

    try {
        series.update({
            time: bar.time,
            open: bar.open,
            high: bar.high,
            low: bar.low,
            close: bar.close,
        });
    } catch (e) {
        // A historical reload can transiently race a live update.
    }
}

export function setPriceFormat(fmt) {
    if (!series) return;

    priceFormat = fmt;
    series.applyOptions({ priceFormat });
}

export function getSeries() {
    return series;
}
