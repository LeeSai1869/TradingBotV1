import { logicalShift } from "./window_state.js";
import * as symbolControl from "../controls/symbol/index.js";
import * as timeframeControl from "../controls/timeframe/index.js";
import * as reloadControl from "../controls/reload/index.js";
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
    } catch (error) {
        if (id === loadId) status().textContent = `Error: ${error.message}`;
    }
}

(async () => {
    const chart = Canvas.init(document.getElementById("chart"));
    await Composer.mountAll(chart);
    let renderedBars = [];
    let rendering = false;
    let pending = null;
    let renderGeneration = 0;

    function updateStatus() {
        status().textContent = DataCache.error
            ? `History error: ${DataCache.error} — move the chart to retry`
            : `${DataCache.symbol} ${DataCache.timeframe} | ` +
              `${DataCache.activeBars.length} active candles | ${DataCache.bars.length} cached`;
    }

    function checkBoundary() {
        if (rendering || pending || DataCache.loading) return;
        const range = chart.timeScale().getVisibleLogicalRange();
        DataCache.setVisibleWindow(range);
        updateStatus();
        // The preceding page is already part of the render dataset before
        // it enters view. Arrival runs this check again and prepares the next.
        if (range && range.from <= PREFETCH_BARS && DataCache.nextBefore !== null) {
            void DataCache.prefetchOlder();
        }
    }

    function render() {
        if (rendering || !pending) return;
        const { op, reset } = pending;
        pending = null;
        rendering = true;
        const generation = ++renderGeneration;
        const range = chart.timeScale().getVisibleLogicalRange();
        const bars = DataCache.bars;
        let target = null;
        if (reset && bars.length) {
            target = { from: Math.max(0, bars.length - 1000), to: bars.length - 1 };
            symbolControl.applyPriceFormat(DataCache.symbol, bars,
                Composer.config.price_precision?.[DataCache.symbol]);
        } else if (range && renderedBars.length && bars.length) {
            const following = op === "stored-refresh" && DataCache.atLiveEdge &&
                range.to >= renderedBars.length - 2;
            const shift = following ? bars.length - renderedBars.length
                : logicalShift(renderedBars, bars);
            target = { from: range.from + shift, to: range.to + shift };
        }
        // All consumers receive the same canonical bars. No visual fetches
        // its own candles/features/decisions, and no visible history is evicted.
        Composer.updateAll(chart, DataCache, op, { resetViewport: reset });
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
        if (op === "error") { updateStatus(); return; }
        pending = { op, reset: op === "reload" || !!pending?.reset };
        render();
    });
    chart.timeScale().subscribeVisibleLogicalRangeChange(checkBoundary);
    document.getElementById("symbol").addEventListener("change", loadAll);
    document.getElementById("interval").addEventListener("change", () => {
        timeframeControl.refreshButtons();
        void loadAll();
    });
    reloadControl.bind(loadAll);
    await loadAll();
    storedPoll.start(Composer.config.stored_refresh_ms ?? 5000);
})();
