import { logicalShift } from "./window_state.js";
import * as symbolControl from "../controls/symbol/index.js";
import * as timeframeControl from "../controls/timeframe/index.js";
import * as reloadControl from "../controls/reload/index.js";
import * as latestControl from "../controls/latest/index.js";
import * as storedPoll from "./stored_poll.js";

const PREFETCH_BARS = 500;
const status = () => document.getElementById("status");
let loadId = 0;

async function loadAll() {
    const id = ++loadId;
    const symbol = symbolControl.value();
    const timeframe = timeframeControl.value();
    status().textContent = `Loading ${symbol} ${timeframe}...`;
    try {
        await DataCache.loadInitial(symbol, timeframe);
        // Keep an older buffer ready even though the readable initial view
        // now contains fewer candles than the cached active window.
        for (let page = 0; page < 2 && id === loadId && DataCache.nextBefore !== null; page++) {
            await DataCache.prefetchOlder();
        }
    } catch (error) {
        if (id === loadId) status().textContent = `Error: ${error.message}`;
    }
}

(async () => {
    const chart = Canvas.init(document.getElementById("chart"));
    await Composer.mountAll(chart);
    DataCache.liveEnabled = Composer.config.live_candle !== false;
    let renderedBars = [];
    let rendering = false;
    let pending = null;
    let renderGeneration = 0;

    function updateStatus() {
        status().textContent = DataCache.error
            ? `History error: ${DataCache.error} — move the chart to retry`
            : `${DataCache.symbol} ${DataCache.timeframe} | ` +
              `${DataCache.activeBars.length} active candles | ${DataCache.bars.length} cached` +
              (DataCache.liveEnabled ? ` | ${DataCache.liveStatus}` : "");
    }

    function checkBoundary() {
        if (rendering || pending || DataCache.loading) return;
        const range = chart.timeScale().getVisibleLogicalRange();
        DataCache.setVisibleWindow(range);
        latestControl.update(chart, DataCache);
        updateStatus();
        // The preceding page is already part of the render dataset before
        // it enters view. Arrival runs this check again and prepares the next.
        if (range && range.from <= PREFETCH_BARS && DataCache.nextBefore !== null) {
            void DataCache.prefetchOlder();
        }
    }

    function render() {
        if (rendering || !pending) return;
        const { op, reset, latest, span } = pending;
        pending = null;
        rendering = true;
        const generation = ++renderGeneration;
        const range = chart.timeScale().getVisibleLogicalRange();
        const bars = DataCache.renderBars;
        let target = null;
        if (latest && bars.length) {
            const last = bars.length - 1;
            target = { from: last - span, to: last };
            chart.priceScale("right").applyOptions({ autoScale: true });
        } else if (reset && bars.length) {
            target = { from: Math.max(0, bars.length - 200), to: bars.length + 7 };
            symbolControl.applyPriceFormat(DataCache.symbol, bars,
                Composer.config.price_precision?.[DataCache.symbol]);
        } else if (range && renderedBars.length && bars.length) {
            const following = (op === "stored-refresh" || op === "live") && DataCache.atLiveEdge &&
                range.to >= renderedBars.length - 2;
            const shift = following ? bars.length - renderedBars.length
                : logicalShift(renderedBars, bars);
            target = { from: range.from + shift, to: range.to + shift };
        }
        // All consumers receive the same canonical bars. No visual fetches
        // its own candles/features/decisions, and no visible history is evicted.
        Composer.updateAll(chart, { ...DataCache, bars }, op, { resetViewport: reset });
        renderedBars = bars;
        if (target) chart.timeScale().setVisibleLogicalRange(target);
        requestAnimationFrame(() => requestAnimationFrame(() => {
            if (generation !== renderGeneration) return;
            rendering = false;
            if (pending) render();
            else checkBoundary();
        }));
    }

    DataCache.subscribe((cache, op) => {
        if (op === "loading") latestControl.update(chart, cache);
        if (op === "error") { updateStatus(); return; }
        if (op === "live" && !rendering && !pending && cache.formingBar &&
            renderedBars.at(-1)?.provisional &&
            renderedBars.at(-1).time === cache.formingBar.time) {
            Composer.updateLive(chart, cache);
            renderedBars[renderedBars.length - 1] = cache.formingBar;
            updateStatus();
            return;
        }
        pending = { op, reset: op === "reload" || !!pending?.reset,
            latest: pending?.latest, span: pending?.span };
        render();
    });
    chart.timeScale().subscribeVisibleLogicalRangeChange(checkBoundary);
    window.addEventListener("chart-settings-change", () => {
        pending = { op: "settings", reset: !!pending?.reset,
            latest: pending?.latest, span: pending?.span };
        render();
    });
    document.getElementById("symbol").addEventListener("change", loadAll);
    document.getElementById("interval").addEventListener("change", () => {
        timeframeControl.refreshButtons();
        void loadAll();
    });
    window.addEventListener("data-policy-change", event => {
        void symbolControl.refresh();
        const scope = event.detail?.deleted;
        if (scope && (scope.interval === DataCache.timeframe || scope.symbol === DataCache.symbol)) void loadAll();
    });
    reloadControl.bind(loadAll);
    latestControl.bind(() => {
        if (DataCache.loading || !DataCache.renderBars.length) return;
        const range = chart.timeScale().getVisibleLogicalRange();
        DataCache.atLiveEdge = true;
        pending = { op: "latest", reset: false, latest: true,
            span: range ? range.to - range.from : 999 };
        render();
        void DataCache.refreshStored().catch(error => {
            status().textContent = `Latest candle refresh failed: ${error.message}`;
        });
    });
    await loadAll();
    const interval = Composer.config.stored_refresh_ms ?? 5000;
    storedPoll.start(DataCache.liveEnabled && interval > 0 ? Math.min(interval, 1000) : interval);
})();
