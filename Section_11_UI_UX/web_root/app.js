// ============================================================
// APP — startup + controls + live polling.
//
// Historical navigation coordinator:
//   - DataCache owns historical block retrieval/storage.
//   - App watches chart navigation.
//   - Composer renders the combined active state packet.
//   - Navigation moves in 500-candle blocks.
//   - The visible TIME range is preserved across replacement.
// ============================================================

import * as symbolControl from "../controls/symbol/index.js";
import * as timeframeControl from "../controls/timeframe/index.js";
import * as reloadControl from "../controls/reload/index.js";
import * as livePoll from "./live_poll.js";

const WINDOW_BARS = 1000;
const BLOCK_BARS = 500;
const LEFT_TRIGGER_BARS = 250;
const RIGHT_TRIGGER_BARS = 250;

const status = () => document.getElementById("status");

let navigationBusy = false;
let suppressNavigation = false;


function rowTime(row) {
    if (!row || row.time == null) return null;

    const t = Number(row.time);
    return Number.isFinite(t) ? t : null;
}

function mergeRows(left, right, timeSelector) {
    const map = new Map();

    for (const row of left || []) {
        const t = timeSelector(row);
        if (t != null) map.set(t, row);
    }

    for (const row of right || []) {
        const t = timeSelector(row);
        if (t != null) map.set(t, row);
    }

    return Array.from(map.values()).sort(
        (a, b) => timeSelector(a) - timeSelector(b)
    );
}

function featureTime(row) {
    return rowTime(row);
}

function flagTime(row) {
    if (!row) return null;

    if (row.time != null) {
        const t = Number(row.time);
        return Number.isFinite(t) ? t : null;
    }

    if (row.bar_time != null) {
        const raw = Number(row.bar_time);

        if (!Number.isFinite(raw)) return null;

        // flags_history may carry bar_time in milliseconds.
        return raw >= 10_000_000_000
            ? Math.floor(raw / 1000)
            : raw;
    }

    return null;
}

function activeTimeBounds(klines) {
    if (!Array.isArray(klines) || !klines.length) {
        return null;
    }

    const first = rowTime(klines[0]);
    const last = rowTime(klines[klines.length - 1]);

    if (first == null || last == null) {
        return null;
    }

    return { first, last };
}

function filterRowsToActive(rows, first, last, selector) {
    return (rows || []).filter(row => {
        const t = selector(row);
        return t != null && t >= first && t <= last;
    });
}

function buildBlockFromRows(
    klines,
    features,
    flagsHistory
) {
    if (!Array.isArray(klines) || !klines.length) {
        return null;
    }

    const bounds = activeTimeBounds(klines);

    if (!bounds) {
        return null;
    }

    const first = bounds.first;
    const last = bounds.last;

    return {
        startMs: first * 1000,
        endMs: last * 1000 + DataCache._stepMs(),
        klines,
        features: filterRowsToActive(
            features,
            first,
            last,
            featureTime
        ),
        flags_history: filterRowsToActive(
            flagsHistory,
            first,
            last,
            flagTime
        ),
    };
}

function applyActivePacket(direction, block) {
    if (
        !block ||
        !Array.isArray(block.klines) ||
        !block.klines.length
    ) {
        return null;
    }

    const currentKlines = DataCache.klines || [];
    const currentFeatures = DataCache.features || [];
    const currentFlags = DataCache.flags_history || [];

    if (!currentKlines.length) {
        return null;
    }

    // Preserve the half that will fall out of the active
    // 1000-bar window. It becomes the instant reverse block.
    const displacedKlines =
        direction === "left"
            ? currentKlines.slice(-BLOCK_BARS)
            : currentKlines.slice(0, BLOCK_BARS);

    const displaced = buildBlockFromRows(
        displacedKlines,
        currentFeatures,
        currentFlags
    );

    const mergedKlines =
        direction === "left"
            ? mergeRows(
                block.klines,
                currentKlines,
                rowTime
            )
            : mergeRows(
                currentKlines,
                block.klines,
                rowTime
            );

    DataCache.klines =
        direction === "left"
            ? mergedKlines.slice(0, WINDOW_BARS)
            : mergedKlines.slice(-WINDOW_BARS);

    const bounds = activeTimeBounds(DataCache.klines);

    if (!bounds) {
        return null;
    }

    const mergedFeatures =
        direction === "left"
            ? mergeRows(
                block.features,
                currentFeatures,
                featureTime
            )
            : mergeRows(
                currentFeatures,
                block.features,
                featureTime
            );

    DataCache.features = filterRowsToActive(
        mergedFeatures,
        bounds.first,
        bounds.last,
        featureTime
    );

    const mergedFlags =
        direction === "left"
            ? mergeRows(
                block.flags_history,
                currentFlags,
                flagTime
            )
            : mergeRows(
                currentFlags,
                block.flags_history,
                flagTime
            );

    DataCache.flags_history = filterRowsToActive(
        mergedFlags,
        bounds.first,
        bounds.last,
        flagTime
    );

    const step = DataCache._stepMs();

    DataCache.startMs = bounds.first * 1000;
    DataCache.endMs = bounds.last * 1000 + step;

    // The ready block used for this shift has now been
    // consumed. It must not remain available while the next
    // directional block is being fetched.
    //
    // The 500 bars that fell off the opposite side become the
    // instant reverse-direction block.
    if (direction === "left") {
        DataCache.setReadyOlder(null);
        DataCache.setReadyNewer(displaced);

        // The moment the user leaves the latest region,
        // live polling must never reload the chart to "now".
        DataCache.atLiveEdge = false;
    } else {
        DataCache.setReadyNewer(null);
        DataCache.setReadyOlder(displaced);
    }

    return {
        bounds,
        displaced,
    };
}


// ============================================================
// FLOW TEST — temporary runtime instrumentation.
// Traces user/chart callback -> navigation -> render -> viewport
// compensation -> prefetch. Does not change navigation decisions.
// ============================================================

let flowCycleId = 0;
let flowCallbackId = 0;

function flowRange(range) {
    if (!range) return "null";

    return (
        Number(range.from).toFixed(2) +
        ".." +
        Number(range.to).toFixed(2)
    );
}

function flowBounds() {
    const rows = Array.isArray(DataCache.klines)
        ? DataCache.klines
        : [];

    if (!rows.length) {
        return "empty";
    }

    return (
        rows[0].time +
        ".." +
        rows[rows.length - 1].time
    );
}

async function navigate(chart, direction) {
    const cycleId = ++flowCycleId;

    console.log(
        `[FLOW C${cycleId} NAV ENTER]`,
        "direction=" + direction,
        "busy=" + navigationBusy,
        "suppressed=" + suppressNavigation,
        "visible=" +
            flowRange(
                chart.timeScale().getVisibleLogicalRange()
            ),
        "active=" + flowBounds(),
        "older=" +
            (
                DataCache.getReadyOlder()?.klines?.length || 0
            ),
        "newer=" +
            (
                DataCache.getReadyNewer()?.klines?.length || 0
            )
    );

    if (navigationBusy || suppressNavigation) {
        console.log(
            `[FLOW C${cycleId} NAV REJECTED]`,
            "busy/suppressed"
        );
        return;
    }

    const block =
        direction === "left"
            ? DataCache.getReadyOlder()
            : DataCache.getReadyNewer();

    if (
        !block ||
        !Array.isArray(block.klines) ||
        block.klines.length === 0
    ) {
        return;
    }

    navigationBusy = true;
    suppressNavigation = true;

    const visibleLogicalRange =
        chart.timeScale().getVisibleLogicalRange();

    try {
        const result = applyActivePacket(
            direction,
            block
        );

        if (!result) {
            console.log(
                `[FLOW C${cycleId} ROTATE FAILED]`
            );
            return;
        }

        console.log(
            `[FLOW C${cycleId} ROTATED]`,
            "active=" + flowBounds(),
            "klines=" + DataCache.klines.length,
            "features=" + DataCache.features.length,
            "flags=" + DataCache.flags_history.length,
            "visible-before-render=" +
                flowRange(
                    chart.timeScale().getVisibleLogicalRange()
                )
        );

        // IMPORTANT:
        // This is a direct coordinated render.
        // No DataCache.emit() is used for navigation.
        console.log(
            `[FLOW C${cycleId} RENDER START]`,
            "visible=" +
                flowRange(
                    chart.timeScale().getVisibleLogicalRange()
                )
        );

        Composer.updateAll(
            chart,
            DataCache,
            direction === "left"
                ? "shift-left"
                : "shift-right",
            { resetViewport: false }
        );

        console.log(
            `[FLOW C${cycleId} RENDER END]`,
            "visible=" +
                flowRange(
                    chart.timeScale().getVisibleLogicalRange()
                )
        );

        // The active dataset rolls by exactly one 500-bar block.
        // Preserve the same visible candles by compensating for that
        // logical index displacement exactly once.
        if (visibleLogicalRange) {
            const logicalShift =
                direction === "left"
                    ? BLOCK_BARS
                    : -BLOCK_BARS;

            console.log(
                `[FLOW C${cycleId} COMPENSATE REQUEST]`,
                "saved=" + flowRange(visibleLogicalRange),
                "shift=" + logicalShift,
                "target=" +
                    flowRange({
                        from:
                            visibleLogicalRange.from +
                            logicalShift,
                        to:
                            visibleLogicalRange.to +
                            logicalShift,
                    })
            );

            chart.timeScale().setVisibleLogicalRange({
                from:
                    visibleLogicalRange.from +
                    logicalShift,
                to:
                    visibleLogicalRange.to +
                    logicalShift,
            });

            console.log(
                `[FLOW C${cycleId} COMPENSATE DONE]`,
                "visible=" +
                    flowRange(
                        chart.timeScale().getVisibleLogicalRange()
                    )
            );
        }

        const bounds = result.bounds;

        if (bounds) {
            const newStartMs = bounds.first * 1000;
            const newEndMs =
                bounds.last * 1000 +
                DataCache._stepMs();

            // A -> B means B was already ready.
            // After entering B, prepare C only.
            if (direction === "left") {
                console.log(
                    `[FLOW C${cycleId} PREFETCH REQUEST]`,
                    "older",
                    "before=" + newStartMs
                );

                void DataCache.prefetchNextOlder(
                    newStartMs
                ).then(ok => {
                    console.log(
                        `[FLOW C${cycleId} PREFETCH RESULT]`,
                        "older",
                        "ok=" + ok,
                        "ready=" +
                            (
                                DataCache
                                    .getReadyOlder()
                                    ?.klines?.length || 0
                            )
                    );
                });
            } else {
                console.log(
                    `[FLOW C${cycleId} PREFETCH REQUEST]`,
                    "newer",
                    "after=" + newEndMs
                );

                void DataCache.prefetchNextNewer(
                    newEndMs
                ).then(ok => {
                    console.log(
                        `[FLOW C${cycleId} PREFETCH RESULT]`,
                        "newer",
                        "ok=" + ok,
                        "ready=" +
                            (
                                DataCache
                                    .getReadyNewer()
                                    ?.klines?.length || 0
                            )
                    );
                });
            }
        }

        console.log(
            direction === "left"
                ? "[UI02 NAV LEFT]"
                : "[UI02 NAV RIGHT]",
            "active=" + DataCache.klines.length,
            "first=" + DataCache.klines[0].time,
            "last=" +
                DataCache.klines[
                    DataCache.klines.length - 1
                ].time
        );

    } catch (e) {
        console.error(
            "[UI02 NAV] failed:",
            e
        );

    } finally {
        // setData() + setVisibleRange() can themselves produce
        // visible-range callbacks. Release suppression after
        // those callbacks have cleared.
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                suppressNavigation = false;
                navigationBusy = false;

                console.log(
                    `[FLOW C${cycleId} RELEASE]`,
                    "visible=" +
                        flowRange(
                            chart.timeScale()
                                .getVisibleLogicalRange()
                        ),
                    "active=" + flowBounds()
                );
            });
        });
    }
}

function installHistoricalNavigation(chart) {
    let lastLogicalCenter = null;

    chart
        .timeScale()
        .subscribeVisibleLogicalRangeChange(
            logicalRange => {
                if (!logicalRange) {
                    return;
                }

                const center =
                    (logicalRange.from + logicalRange.to) / 2;

                const previousCenter = lastLogicalCenter;
                lastLogicalCenter = center;

                const callbackId = ++flowCallbackId;

                console.log(
                    `[FLOW CB${callbackId}]`,
                    "range=" + flowRange(logicalRange),
                    "prevCenter=" +
                        (
                            previousCenter == null
                                ? "null"
                                : previousCenter.toFixed(2)
                        ),
                    "center=" + center.toFixed(2),
                    "busy=" + navigationBusy,
                    "suppressed=" + suppressNavigation,
                    "active=" + flowBounds(),
                    "older=" +
                        (
                            DataCache
                                .getReadyOlder()
                                ?.klines?.length || 0
                        ),
                    "newer=" +
                        (
                            DataCache
                                .getReadyNewer()
                                ?.klines?.length || 0
                        )
                );

                // setData() and our one logical-range compensation
                // produce callbacks too. They are maintenance, not
                // user navigation.
                if (
                    navigationBusy ||
                    suppressNavigation ||
                    previousCenter == null
                ) {
                    return;
                }

                const n =
                    Array.isArray(DataCache.klines)
                        ? DataCache.klines.length
                        : 0;

                if (!n) {
                    return;
                }

                const movedLeft =
                    center < previousCenter;

                const movedRight =
                    center > previousCenter;

                if (
                    movedLeft &&
                    logicalRange.from <= LEFT_TRIGGER_BARS
                ) {
                    const ready =
                        DataCache.getReadyOlder();

                    if (
                        ready &&
                        Array.isArray(ready.klines) &&
                        ready.klines.length
                    ) {
                        void navigate(chart, "left");
                    }

                    return;
                }

                if (
                    movedRight &&
                    logicalRange.to >=
                        n - RIGHT_TRIGGER_BARS
                ) {
                    const ready =
                        DataCache.getReadyNewer();

                    if (
                        ready &&
                        Array.isArray(ready.klines) &&
                        ready.klines.length
                    ) {
                        void navigate(chart, "right");
                    }
                }
            }
        );
}

async function loadAll() {
    const symbol = symbolControl.value();
    const timeframe = timeframeControl.value();

    Canvas.resetViewportOnNextReload = true;
    status().textContent =
        `Loading ${symbol} ${timeframe}...`;

    try {
        await symbolControl.applyPriceFormat(symbol);
        await DataCache.loadInitial(
            symbol,
            timeframe
        );

        status().textContent =
            `${symbol} ${timeframe} | ` +
            `${DataCache.klines.length} candles`;

    } catch (e) {
        status().textContent =
            "Error: " + e.message;

        console.error(
            "[app] load failed:",
            e
        );
    }
}

(async () => {
    const chartContainer =
        document.getElementById("chart");

    const chart =
        Canvas.init(chartContainer);

    await Composer.mountAll(chart);

    DataCache.subscribe(
        (cache, op, meta = {}) => {
            const resetViewport =
                !!Canvas.resetViewportOnNextReload;

            Canvas.resetViewportOnNextReload =
                false;

            Composer.updateAll(
                chart,
                cache,
                op || "reload",
                {
                    resetViewport,
                    ...meta,
                }
            );
        }
    );

    // Navigation ownership remains here in app.js.
    installHistoricalNavigation(chart);

    document
        .getElementById("symbol")
        .addEventListener(
            "change",
            loadAll
        );

    document
        .getElementById("interval")
        .addEventListener(
            "change",
            () => {
                timeframeControl.refreshButtons();
                loadAll();
            }
        );

    reloadControl.bind(loadAll);

    await loadAll();
    livePoll.start();
})();
