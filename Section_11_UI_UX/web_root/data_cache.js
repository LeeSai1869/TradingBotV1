// One stored-bar stream. A bar owns client OHLCV, permanent features and ADCN.
// Retain visited history for smooth reversal; only fetch the next older page.
const WINDOW_BARS = 1000;
const BLOCK_BARS = 500;

const DataCache = {
    symbol: null,
    timeframe: null,
    bars: [],
    activeBars: [],
    latestBar: null,
    nextBefore: null,
    loading: false,
    atLiveEdge: true,
    error: null,
    _reloadGeneration: 0,
    _olderPromise: null,
    _refreshPromise: null,
    _latestSignature: null,
    listeners: [],

    subscribe(fn) { this.listeners.push(fn); },
    emit(op, meta = {}) {
        for (const fn of this.listeners) fn(this, op, meta);
    },

    async _fetchPage(symbol, timeframe, limit, before = null) {
        const qs = new URLSearchParams({ symbol, interval: timeframe, limit });
        if (before !== null) qs.set("before", before);
        const response = await fetch(`/api/bars?${qs}`, { cache: "no-store" });
        if (!response.ok) throw new Error(`Stored bars: HTTP ${response.status}`);
        const packet = await response.json();
        if (!Array.isArray(packet.bars)) throw new Error("Invalid stored-bar packet");
        return packet;
    },

    _merge(rows) {
        const byTime = new Map(this.bars.map(bar => [bar.open_time, bar]));
        for (const bar of rows) byTime.set(bar.open_time, bar);
        this.bars = [...byTime.values()].sort((a, b) => a.open_time - b.open_time);
    },

    setVisibleWindow(range) {
        if (!range || !this.bars.length) {
            this.activeBars = this.bars.slice(-WINDOW_BARS);
            return;
        }
        const start = Math.max(0, Math.min(this.bars.length - WINDOW_BARS,
            Math.floor((range.from + range.to) / 2) - WINDOW_BARS / 2));
        this.activeBars = this.bars.slice(start, start + WINDOW_BARS);
        this.atLiveEdge = range.to >= this.bars.length - 2;
    },

    async loadInitial(symbol, timeframe) {
        const generation = ++this._reloadGeneration;
        Object.assign(this, { symbol, timeframe, bars: [], activeBars: [], latestBar: null,
            nextBefore: null, loading: true, atLiveEdge: true, error: null,
            _olderPromise: null, _refreshPromise: null, _latestSignature: null });
        this.emit("loading");
        try {
            const packet = await this._fetchPage(symbol, timeframe, WINDOW_BARS);
            if (generation !== this._reloadGeneration) return false;
            this.bars = packet.bars;
            this.activeBars = this.bars;
            this.latestBar = this.bars.at(-1) || null;
            this.nextBefore = packet.next_before;
            this._latestSignature = JSON.stringify(packet.bars);
            this.loading = false;
            this.emit("reload");
            return true;
        } finally {
            if (generation === this._reloadGeneration) this.loading = false;
        }
    },

    prefetchOlder() {
        if (this.loading || this.nextBefore === null) return Promise.resolve(false);
        if (this._olderPromise) return this._olderPromise;
        const generation = this._reloadGeneration;
        const cursor = this.nextBefore;
        const request = this._fetchPage(this.symbol, this.timeframe, BLOCK_BARS, cursor);
        const work = request.then(packet => {
            if (generation !== this._reloadGeneration || cursor !== this.nextBefore) return false;
            this._merge(packet.bars);
            this.nextBefore = packet.next_before;
            this.error = null;
            // Readiness is an event: navigation re-evaluates even if the
            // user stopped moving while this block was in flight.
            this.emit("history");
            return packet.bars.length > 0;
        }).catch(error => {
            if (generation === this._reloadGeneration) {
                this.error = error.message;
                this.emit("error");
            }
            return false;
        }).finally(() => {
            if (this._olderPromise === work) this._olderPromise = null;
        });
        this._olderPromise = work;
        return work;
    },

    refreshStored() {
        if (this.loading || !this.atLiveEdge) return Promise.resolve(false);
        if (this._refreshPromise) return this._refreshPromise;
        const generation = this._reloadGeneration;
        const request = this._fetchPage(this.symbol, this.timeframe, WINDOW_BARS);
        const work = request.then(packet => {
            if (generation !== this._reloadGeneration || this.loading || !this.atLiveEdge) return false;
            const signature = JSON.stringify(packet.bars);
            if (signature === this._latestSignature) return false;
            this._latestSignature = signature;
            this._merge(packet.bars);
            this.latestBar = packet.bars.at(-1) || null;
            this.emit("stored-refresh");
            return true;
        }).finally(() => {
            if (this._refreshPromise === work) this._refreshPromise = null;
        });
        this._refreshPromise = work;
        return work;
    },
};
window.DataCache = DataCache;
