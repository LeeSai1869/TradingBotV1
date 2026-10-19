// One stored-bar stream. A bar owns client OHLCV, permanent features and ADCN.
// Retain visited history for smooth reversal; only fetch the next older page.
const WINDOW_BARS = 1000;
const BLOCK_BARS = 500;

const DataCache = {
    symbol: null,
    timeframe: null,
    bars: [],
    liveEnabled: true,
    formingBar: null,
    liveStatus: "loading",
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

    get renderBars() {
        return this.formingBar ? [...this.bars, this.formingBar] : this.bars;
    },

    _applyLive(live) {
        const previous = JSON.stringify([this.formingBar, this.liveStatus]);
        const latest = this.bars.at(-1);
        if (!this.liveEnabled || !latest || this.formingBar?.open_time <= latest.open_time) {
            this.formingBar = null;
        }
        if (live && this.liveEnabled) {
            this.liveStatus = live.status;
            const candidate = live.bar;
            if (candidate && latest) {
                // Do not jump over missing audited history. At rollover keep
                // the prior provisional bar until the store replaces it.
                if (candidate.open_time === latest.client.close_time + 1) {
                    this.formingBar = candidate;
                } else if (candidate.open_time > latest.open_time) {
                    this.liveStatus = "waiting for stored bar";
                }
            }
        }
        return previous !== JSON.stringify([this.formingBar, this.liveStatus]);
    },

    subscribe(fn) { this.listeners.push(fn); },
    emit(op, meta = {}) {
        for (const fn of this.listeners) fn(this, op, meta);
    },

    async _fetchPage(symbol, timeframe, limit, before = null) {
        const qs = new URLSearchParams({ symbol, interval: timeframe, limit });
        if (before !== null) qs.set("before", before);
        else if (this.liveEnabled) qs.set("live", "1");
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
            _olderPromise: null, _refreshPromise: null, _latestSignature: null,
            formingBar: null, liveStatus: this.liveEnabled ? "loading" : "disabled" });
        this.emit("loading");
        try {
            const packet = await this._fetchPage(symbol, timeframe, WINDOW_BARS);
            if (generation !== this._reloadGeneration) return false;
            this.bars = packet.bars;
            this.activeBars = this.bars;
            this.latestBar = this.bars.at(-1) || null;
            this.nextBefore = packet.next_before;
            this._latestSignature = JSON.stringify(packet.bars);
            this._applyLive(packet.live);
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
            const changed = signature !== this._latestSignature;
            if (changed) {
                this._latestSignature = signature;
                this._merge(packet.bars);
                this.latestBar = packet.bars.at(-1) || null;
            }
            const liveChanged = this._applyLive(packet.live);
            if (changed) this.emit("stored-refresh");
            else if (liveChanged) this.emit("live");
            return changed || liveChanged;
        }).finally(() => {
            if (this._refreshPromise === work) this._refreshPromise = null;
        });
        this._refreshPromise = work;
        return work;
    },
};
window.DataCache = DataCache;
