// VISUAL: price candles from the unified stored-bar stream.

export const name = "candles";

let series = null;
let currentPriceLine = null;

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
            lastValueVisible: false,
        }
    );
}

function _toPoints(bars) {
    return (bars || []).map(bar => ({
        ...bar.client,
        time: bar.time,
    }));
}

function updateCurrentPrice(bar) {
    if (!bar) {
        if (currentPriceLine) series.removePriceLine(currentPriceLine);
        currentPriceLine = null;
        return;
    }
    const options = {
        price: bar.client.close,
        color: bar.client.close >= bar.client.open ? "#26a69a" : "#ef5350",
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
    };
    if (currentPriceLine) currentPriceLine.applyOptions(options);
    else currentPriceLine = series.createPriceLine(options);
}

// Full historical packet replacement.
// Used for initial load, symbol change, timeframe change and explicit reload.
export function update(chart, data, options = {}) {
    if (!series) return;

    series.applyOptions({ visible: options.visible !== false });
    series.setData(_toPoints(data.bars));
    updateCurrentPrice(data.bars?.at(-1));

    // Only an explicit reload establishes autoscale. Prefetch preserves
    // the user's vertical scale; the "A" control can reset it manually.
    if (
        options.resetViewport &&
        chart &&
        chart.priceScale
    ) {
        chart
            .priceScale("right")
            .applyOptions({ autoScale: true });
    }
}

// A forming-price tick updates one point, without rebuilding history/EMA/markers.
export function updateLive(chart, bar) {
    if (!series || !bar) return;
    series.update({ ...bar.client, time: bar.time });
    updateCurrentPrice(bar);
}

export function setPriceFormat(fmt) {
    if (!series) return;

    priceFormat = fmt;
    series.applyOptions({ priceFormat });
}

export function getSeries() {
    return series;
}
