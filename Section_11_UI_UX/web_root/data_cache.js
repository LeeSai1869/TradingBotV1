// ============================================================
// DATA CACHE
//
// Historical source:
//   Central Core -> /api/chart_window -> DataCache
//
// CACHE CONTRACT
//
// Active chart packet:
//   1000 candles
//
// Historical navigation blocks:
//   500 candles each
//
// Cache layout:
//
//   [readyOlder 500][ ACTIVE 1000 ][readyNewer 500]
//
// Only the next block in the direction of travel is prefetched.
// The 500 bars displaced from the active window become the
// ready block for an immediate direction reversal.
//
// DataCache ONLY retrieves and stores these blocks.
// It does NOT move the chart, reset the viewport, or emit a
// navigation event.
//
// The candles component will later decide when a cached block
// becomes visible.
// ============================================================

const WINDOW_BARS = 1000;
const BLOCK_BARS = 500;

const DataCache = {
    symbol: null,
    timeframe: null,

    startMs: null,
    endMs: null,

    atLiveEdge: true,

    _intervalMs: {
        "1m": 60_000,
        "3m": 180_000,
        "5m": 300_000,
        "15m": 900_000,
        "30m": 1_800_000,
        "1h": 3_600_000,
        "2h": 7_200_000,
        "4h": 14_400_000,
        "6h": 21_600_000,
        "8h": 28_800_000,
        "12h": 43_200_000,
        "1d": 86_400_000,
        "3d": 259_200_000,
        "1w": 604_800_000,
        "1M": 2_592_000_000,
    },

    // Active 1000-candle packet.
    klines: [],
    features: [],
    flags_history: [],
    flags_current: null,

    // One ready 500-candle block on each side at most.
    // At the live edge, readyNewer is normally null.
    readyOlder: null,
    readyNewer: null,

    // Reload generation invalidates every request belonging to
    // an older symbol/timeframe/load cycle.
    _reloadGeneration: 0,

    // Directional request ownership is independent.
    // Older navigation must never cancel newer navigation,
    // and newer navigation must never cancel older navigation.
    _olderRequestId: 0,
    _newerRequestId: 0,

    listeners: [],

    subscribe(fn) {
        this.listeners.push(fn);
    },

    emit(op, meta = {}) {
        for (const fn of this.listeners) {
            try {
                fn(this, op, meta);
            } catch (e) {
                console.error("[cache] listener error:", e);
            }
        }
    },

    _stepMs() {
        return this._intervalMs[this.timeframe] || 60_000;
    },

    _rowTimeMs(row) {
        if (!row || row.time == null) return null;

        const t = Number(row.time);

        if (!Number.isFinite(t)) {
            return null;
        }

        return t < 10_000_000_000 ? t * 1000 : t;
    },

    _emptyBlock(startMs, endMs) {
        return {
            startMs,
            endMs,
            klines: [],
            features: [],
            flags_history: [],
        };
    },

    _makeBlock(startMs, endMs, packet) {
        return {
            startMs,
            endMs,
            klines: Array.isArray(packet.klines)
                ? packet.klines
                : [],
            features: Array.isArray(packet.features)
                ? packet.features
                : [],
            flags_history: Array.isArray(packet.flags_history)
                ? packet.flags_history
                : [],
        };
    },

    _activeBounds() {
        if (!Array.isArray(this.klines) || !this.klines.length) {
            return null;
        }

        const step = this._stepMs();

        const firstMs = this._rowTimeMs(this.klines[0]);
        const lastMs = this._rowTimeMs(
            this.klines[this.klines.length - 1]
        );

        if (firstMs == null || lastMs == null) {
            return null;
        }

        return {
            startMs: firstMs,
            endMs: lastMs + step,
        };
    },

    async loadInitial(symbol, timeframe) {
        this.symbol = symbol;
        this.timeframe = timeframe;
        this.atLiveEdge = true;

        // A full load invalidates every request from the previous
        // symbol/timeframe/load cycle.
        const generation = ++this._reloadGeneration;

        ++this._olderRequestId;
        ++this._newerRequestId;

        this.readyOlder = null;
        this.readyNewer = null;

        const step = this._stepMs();
        const end = Date.now();

        const start =
            Math.floor(
                (end - WINDOW_BARS * step) / step
            ) * step;

        const packet = await this._fetchWindow(start, end);

        this.startMs = start;
        this.endMs = end;

        this.klines = packet.klines;
        this.features = packet.features;
        this.flags_history = packet.flags_history;

        console.log(
            "[REG01 assign]",
            "DataCache.klines=" + this.klines.length,
            "DataCache.features=" + this.features.length
        );

        const debugStatus =
            document.getElementById("status");

        if (debugStatus) {
            debugStatus.textContent =
                "ASSIGN | cache=" + this.klines.length +
                " | features=" + this.features.length;
        }

        await this._fetchFlagsCurrent();

        // Existing initial-render event only.
        this.emit("reload");

        // Initial historical reserve:
        // A is active/current. B must already be available.
        // Do not request future blocks at the live edge.
        void this._prefetchInitialOlder(generation);
    },

    async _fetchBlock(startMs, endMs) {
        const packet = await this._fetchWindow(
            startMs,
            endMs
        );

        return this._makeBlock(
            startMs,
            endMs,
            packet
        );
    },

    async _prefetchInitialOlder(
        generation = this._reloadGeneration
    ) {
        const bounds = this._activeBounds();

        if (!bounds) {
            return false;
        }

        const span = BLOCK_BARS * this._stepMs();
        const startMs = bounds.startMs - span;
        const endMs = bounds.startMs;

        try {
            const block = await this._fetchBlock(
                startMs,
                endMs
            );

            if (generation !== this._reloadGeneration) {
                return false;
            }

            this.readyOlder =
                block.klines.length ? block : null;

            console.log(
                "[CACHE INITIAL READY]",
                "older=" + block.klines.length,
                "active=" + this.klines.length
            );

            return true;

        } catch (e) {
            console.error(
                "[CACHE INITIAL READY] failed:",
                e
            );
            return false;
        }
    },

    // --------------------------------------------------------
    // READY BLOCK ACCESS
    // --------------------------------------------------------

    getReadyOlder() {
        return this.readyOlder;
    },

    getReadyNewer() {
        return this.readyNewer;
    },

    setReadyOlder(block) {
        this.readyOlder = block || null;
    },

    setReadyNewer(block) {
        this.readyNewer = block || null;
    },

    // --------------------------------------------------------
    // PREFETCH NEXT DIRECTIONAL BLOCK
    //
    // The block being entered is already available.
    // Entering it causes ONLY the following block in that
    // direction to be prepared.
    // --------------------------------------------------------

    async prefetchNextOlder(newActiveStartMs) {
        const reloadGeneration = this._reloadGeneration;
        const requestId = ++this._olderRequestId;
        const span = BLOCK_BARS * this._stepMs();

        const startMs = newActiveStartMs - span;
        const endMs = newActiveStartMs;

        try {
            const block = await this._fetchBlock(
                startMs,
                endMs
            );

            if (
                reloadGeneration !== this._reloadGeneration ||
                requestId !== this._olderRequestId
            ) {
                return false;
            }

            this.readyOlder =
                block.klines.length ? block : null;

            this.atLiveEdge = false;

            console.log(
                "[CACHE NEXT OLDER READY]",
                "rows=" + block.klines.length,
                "range=" + startMs + ".." + endMs
            );

            return block.klines.length > 0;

        } catch (e) {
            console.error(
                "[CACHE NEXT OLDER] failed:",
                e
            );
            return false;
        }
    },

    async prefetchNextNewer(newActiveEndMs) {
        const reloadGeneration = this._reloadGeneration;
        const requestId = ++this._newerRequestId;
        const span = BLOCK_BARS * this._stepMs();

        const startMs = newActiveEndMs;
        const endMs = newActiveEndMs + span;

        try {
            const block = await this._fetchBlock(
                startMs,
                endMs
            );

            if (
                reloadGeneration !== this._reloadGeneration ||
                requestId !== this._newerRequestId
            ) {
                return false;
            }

            this.readyNewer =
                block.klines.length ? block : null;

            this.atLiveEdge =
                block.klines.length === 0;

            console.log(
                "[CACHE NEXT NEWER READY]",
                "rows=" + block.klines.length,
                "range=" + startMs + ".." + endMs
            );

            return block.klines.length > 0;

        } catch (e) {
            console.error(
                "[CACHE NEXT NEWER] failed:",
                e
            );
            return false;
        }
    },

    async _fetchWindow(start, end) {
        const s = this.symbol;
        const tf = this.timeframe;

        const qs =
            `symbol=${encodeURIComponent(s)}` +
            `&interval=${encodeURIComponent(tf)}` +
            `&start=${start}` +
            `&end=${end}`;

        const response = await fetch(
            `/api/chart_window?${qs}`,
            { cache: "no-store" }
        );

        if (!response.ok) {
            throw new Error(
                `chart_window request failed: HTTP ${response.status}`
            );
        }

        const packet = await response.json();

        console.log(
            "[REG01 fetch]",
            "HTTP=" + response.status,
            "packet.klines=" +
                (
                    Array.isArray(packet.klines)
                        ? packet.klines.length
                        : "NOT_ARRAY"
                ),
            "packet.features=" +
                (
                    Array.isArray(packet.features)
                        ? packet.features.length
                        : "NOT_ARRAY"
                )
        );

        return {
            klines: Array.isArray(packet.klines)
                ? packet.klines
                : [],

            features: Array.isArray(packet.features)
                ? packet.features
                : [],

            flags_history: Array.isArray(packet.flags_history)
                ? packet.flags_history
                : [],
        };
    },

    async _fetchFlagsCurrent() {
        const s = this.symbol;
        const tf = this.timeframe;

        try {
            const r = await fetch(
                `/api/flags_current?symbol=${encodeURIComponent(s)}` +
                `&interval=${encodeURIComponent(tf)}` +
                `&_=${Date.now()}`,
                { cache: "no-store" }
            );

            this.flags_current =
                r.ok ? await r.json() : null;

        } catch (e) {
            this.flags_current = null;
        }
    },
};

window.DataCache = DataCache;
