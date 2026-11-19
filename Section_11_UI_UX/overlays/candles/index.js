// VISUAL: price candles from the unified stored-bar stream.

export const name = "candles";

let series = null;
let currentPriceLine = null;
let currentPriceRay = null;
let renderedBars = [];

// A native price line spans the entire pane. Draw the live-price ray ourselves
// so it begins at the newest candle, with a dotted reference in history.
class CurrentPriceRay {
    attached({ chart, series, requestUpdate }) {
        this.chart = chart;
        this.series = series;
        this.requestUpdate = requestUpdate;
    }

    detached() {
        this.chart = this.series = this.requestUpdate = null;
    }

    setBar(bar) {
        this.bar = bar;
        this.requestUpdate?.();
    }

    paneViews() { return [this]; }
    renderer() { return this; }
    zOrder() { return "normal"; }

    draw(target) {
        if (!this.bar || !this.series?.options().visible) return;
        const y = this.series.priceToCoordinate(this.bar.client.close);
        const x = this.chart.timeScale().timeToCoordinate(this.bar.time);
        if (y === null || x === null) return;
        target.useMediaCoordinateSpace(({ context, mediaSize }) => {
            const visible = x >= 0 && x <= mediaSize.width;
            context.save();
            context.strokeStyle = this.bar.client.close >= this.bar.client.open
                ? this.series.options().upColor : this.series.options().downColor;
            context.lineWidth = 1;
            context.setLineDash(visible ? [] : [2, 3]);
            context.beginPath();
            context.moveTo(visible ? x : 0, y);
            context.lineTo(mediaSize.width, y);
            context.stroke();
            context.restore();
        });
    }
}

let priceFormat = {
    type: "price",
    precision: 2,
    minMove: 0.01,
};

export function mount(chart) {
    renderedBars = [];
    currentPriceLine = null;
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
    currentPriceRay = new CurrentPriceRay();
    series.attachPrimitive(currentPriceRay);
}

function point(bar) {
    const { open, high, low, close } = bar.client;
    return { time: bar.time, open, high, low, close };
}

function sameCandle(a, b) {
    return a === b || (a.time === b.time &&
        a.client.open === b.client.open && a.client.high === b.client.high &&
        a.client.low === b.client.low && a.client.close === b.client.close);
}

function updateData(bars, reset) {
    let firstChange = 0;
    while (firstChange < Math.min(renderedBars.length, bars.length) &&
        sameCandle(renderedBars[firstChange], bars[firstChange])) firstChange++;

    if (reset || bars.length < renderedBars.length || firstChange < renderedBars.length - 1 ||
        (firstChange < renderedBars.length && renderedBars[firstChange].time !== bars[firstChange].time)) {
        series.setData(bars.map(point));
    } else {
        for (let i = firstChange; i < bars.length; i++) series.update(point(bars[i]));
    }
    renderedBars = bars;
}

function updateCurrentPrice(bar) {
    currentPriceRay.setBar(bar);
    if (!bar) {
        if (currentPriceLine) series.removePriceLine(currentPriceLine);
        currentPriceLine = null;
        return;
    }
    const options = {
        price: bar.client.close,
        color: bar.client.close >= bar.client.open ? series.options().upColor : series.options().downColor,
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        lineVisible: false,
        axisLabelVisible: true,
    };
    if (currentPriceLine) currentPriceLine.applyOptions(options);
    else currentPriceLine = series.createPriceLine(options);
}

// Replace the series on reload or when history changes beyond its right edge.
export function update(chart, data, options = {}) {
    if (!series) return;

    series.applyOptions({ ...window.Composer?.config.candleStyle, visible: options.visible !== false });
    updateData(data.bars || [], options.op === "reload");
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
    series.update(point(bar));
    renderedBars = [...renderedBars.slice(0, -1), bar];
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
