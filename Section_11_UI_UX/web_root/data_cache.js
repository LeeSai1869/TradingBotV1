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
    loading: false,

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

        const firstMs = this._rowTimeMs(this.klines[0]);
        const lastMs = this._rowTimeMs(
            this.klines[this.klines.length - 1]
        );

        if (firstMs == null || lastMs == null) {
            return null;
        }

        return {
            startMs: firstMs,
            endMs: this._shiftMs(lastMs, 1),
        };
    },

    async loadInitial(symbol, timeframe) {
        this.symbol = symbol;
        this.timeframe = timeframe;
        this.atLiveEdge = true;
        this.loading = true;
        const generation = ++this._reloadGeneration;
        ++this._olderRequestId;
        ++this._newerRequestId;
        this.readyOlder = null;
        this.readyNewer = null;
        this.klines = [];
        this.features = [];
        this.flags_history = [];
        this.flags_current = null;
        this.emit("loading", { resetViewport: false });

        const end = Date.now();
        const start = this._shiftMs(end, -WINDOW_BARS);
        try {
            const [packet, flags] = await Promise.all([
                this._fetchWindow(start, end),
                this._readFlagsCurrent(symbol, timeframe),
            ]);
            if (generation !== this._reloadGeneration) return false;
            Object.assign(this, packet, {
                startMs: start, endMs: end, flags_current: flags,
            });
            this.loading = false;
            this.emit("reload", { resetViewport: true });
            void this._prefetchInitialOlder(generation);
            return true;
        } finally {
            if (generation === this._reloadGeneration) this.loading = false;
        }
    },

    // Calendar months are not fixed 30-day intervals. Boundaries are
    // calculated from the canonical candle open time in UTC.
    _shiftMs(time, bars) {
        if (this.timeframe === "1M") {
            const date = new Date(time);
            return Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + bars, 1);
        }
        return time + bars * this._stepMs();
    },

    async refreshLive() {
        if (this.loading || !this.atLiveEdge) return false;
        const generation = this._reloadGeneration;
        const first = this.klines[0];
        const start = first ? first.time * 1000 : this._shiftMs(Date.now(), -WINDOW_BARS);
        const end = Date.now();
        const packet = await this._fetchWindow(start, end);
        // Panning while this request was pending must not return the user to now.
        if (generation !== this._reloadGeneration || !this.atLiveEdge || this.loading) {
            return false;
        }
        const previous = this.klines;
        packet.klines = packet.klines.slice(-WINDOW_BARS);
        const times = new Set(packet.klines.map(row => row.time));
        packet.features = packet.features.filter(row => times.has(row.time));
        packet.flags_history = packet.flags_history.filter(row =>
            times.has(Math.floor(row.bar_time / 1000)));
        Object.assign(this, packet, { startMs: start, endMs: end });
        // A reserve based on the old active boundary is no longer adjacent.
        if (previous[0]?.time !== this.klines[0]?.time) {
            this.readyOlder = null;
            void this._prefetchInitialOlder(generation);
        }
        this.emit("live-refresh", { previousKlines: previous, resetViewport: false });
        return true;
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
        if (generation !== this._reloadGeneration) return false;
        const bounds = this._activeBounds();
        if (!bounds) return false;
        return this.prefetchNextOlder(bounds.startMs);
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
        ++this._olderRequestId;
        this.readyOlder = block || null;
    },

    setReadyNewer(block) {
        ++this._newerRequestId;
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

        const startMs = this._shiftMs(newActiveStartMs, -BLOCK_BARS);
        const endMs = newActiveStartMs;

        try {
            const block = await this._fetchBlock(
                startMs,
                endMs
            );

            if (
                reloadGeneration !== this._reloadGeneration ||
                requestId !== this._olderRequestId ||
                this._activeBounds()?.startMs !== newActiveStartMs
            ) {
                return false;
            }

            this.readyOlder =
                block.klines.length ? block : null;

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

        const startMs = newActiveEndMs;
        const endMs = this._shiftMs(newActiveEndMs, BLOCK_BARS);

        try {
            const block = await this._fetchBlock(
                startMs,
                endMs
            );

            if (
                reloadGeneration !== this._reloadGeneration ||
                requestId !== this._newerRequestId ||
                this._activeBounds()?.endMs !== newActiveEndMs
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

    async _readFlagsCurrent(symbol, timeframe) {
        try {
            const r = await fetch(
                `/api/flags_current?symbol=${encodeURIComponent(symbol)}` +
                `&interval=${encodeURIComponent(timeframe)}`,
                { cache: "no-store" }
            );
            return r.ok ? await r.json() : null;
        } catch {
            return null;
        }
    },
};

window.DataCache = DataCache;
