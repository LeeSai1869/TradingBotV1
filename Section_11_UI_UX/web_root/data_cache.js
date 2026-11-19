// One stored-bar stream. A bar owns client OHLCV, permanent features and ADCN.
// Retain visited history for smooth reversal; only fetch the next older page.
const WINDOW_BARS = 1000;
const BLOCK_BARS = 500;
const LIVE_TAIL_BARS = 4;

const DataCache = {
    symbol: null,
    timeframe: null,
    bars: [],
    liveEnabled: true,
    historyPending: false,
    liveBars: [],
    featureProgress: null,
    volumeProfile: null,
    liquidity:null,
    fvgFrames: {},
    srSnapshot:null,
    srFrames:{},
    liveStatus: "loading",
    liveError: null,
    _liveAsOf: null,
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
    _refreshCount: 0,
    _fullRefreshVersion: 0,
    _appliedFullRefreshVersion: 0,
    _storageEpoch: "0:0",
    listeners: [],

    get formingBar() {
        return this.liveBars.at(-1) ?? null;
    },

    get renderBars() {
        return this.liveBars.length ? [...this.bars, ...this.liveBars] : this.bars;
    },

    _applyLive(live) {
        if (live?.as_of != null) {
            if (this._liveAsOf != null && live.as_of < this._liveAsOf) live = null;
            else this._liveAsOf = live.as_of;
        }
        const previous = JSON.stringify([this.liveBars, this.liveStatus, this.liveError]);
        const latest = this.bars.at(-1);
        if (!this.liveEnabled || live?.status === "inactive") {
            this.liveBars = [];
        } else {
            // Stored bars replace overlapping previews. A bounded tail keeps
            // rollover visible even when the storage runner is behind.
            if (latest) this.liveBars = this.liveBars.filter(bar => bar.open_time > latest.open_time);
            const candidate = live?.bar;
            if (candidate && (!latest || candidate.open_time > latest.open_time)) {
                const last = this.formingBar;
                if (!last || candidate.open_time > last.open_time) {
                    this.liveBars = [...this.liveBars, candidate].slice(-LIVE_TAIL_BARS);
                } else if (candidate.open_time === last.open_time) {
                    this.liveBars[this.liveBars.length - 1] = candidate;
                }
            }
        }
        if (live && this.liveEnabled) {
            this.liveStatus = live.status;
            this.liveError = live.status === "unavailable" ? (live.error || "No current quote from Binance") : null;
        }
        return previous !== JSON.stringify([this.liveBars, this.liveStatus, this.liveError]);
    },

    async refreshLive() {
        if (!this.liveEnabled || this.loading || !this.atLiveEdge || !this.symbol) return false;
        const generation = this._reloadGeneration;
        const query = new URLSearchParams({symbol: this.symbol, interval: this.timeframe});
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        let live;
        try {
            const response = await fetch(`/api/live_snapshot?${query}`, {cache: "no-store", signal: controller.signal});
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            live = await response.json();
        } catch (error) {
            live = {status: "unavailable", error: error.name === "AbortError" ? "Live quote request timed out" : error.message};
        } finally {
            clearTimeout(timeout);
        }
        if (generation !== this._reloadGeneration || this.loading || !this.atLiveEdge || !this._applyLive(live)) return false;
        this.emit("live");
        return true;
    },

    subscribe(fn) { this.listeners.push(fn); },
    emit(op, meta = {}) {
        for (const fn of this.listeners) fn(this, op, meta);
    },

    async _fetchPage(symbol, timeframe, limit, before = null, { includeLive = true } = {}) {
        const qs = new URLSearchParams({ symbol, interval: timeframe, limit });
        if(before===null){
            const reference=this.symbol===symbol&&this.timeframe===timeframe?[...this.bars].reverse().find(b=>b.signal_context)?.signal_context:null;
            if(Number.isFinite(reference?.open_time))qs.set('analysis_reference',String(reference.open_time));
            if(Object.entries(window.Composer?.config.featureStyles||{}).some(([key,value])=>(['support_zones','resistance_zones','inst_support_zones','inst_resistance_zones'].includes(key)||/_(ob|breaker)_zones$/.test(key))&&value?.visible))qs.set('sr_zones','1');
            const srOptions=window.Composer?.config.featureStyles||{};
            if(['support','resistance'].some(side=>srOptions[`inst_${side}_zones`]?.visible&&srOptions[`inst_${side}_zones`]?.higher!==false)){
                const all=['1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h','1d','3d','1w','1M'];
                qs.set('sr_frames',all.slice(all.indexOf(timeframe)+1).join(','));
            }
            const match=/^(\d+)([mhdwM])$/.exec(timeframe),units={m:60000,h:3600000,d:86400000,w:604800000,M:2678400000};
            const duration=match?Number(match[1])*units[match[2]]:Infinity;
            const frames=['4h','1d','1w'].filter(tf=>({ '4h':14400000,'1d':86400000,'1w':604800000 }[tf]>duration)&&['bull','bear'].some(side=>window.Composer?.config.featureStyles?.[`${side}_fvg_${tf}_zones`]?.visible));
            if(frames.length)qs.set('fvg_frames',frames.join(','));
            if(['bull_fvg_zones','bear_fvg_zones',`bull_fvg_${timeframe}_zones`,`bear_fvg_${timeframe}_zones`].some(k=>window.Composer?.config.featureStyles?.[k]?.visible))qs.set('fvg_current','1');
            qs.set('fvg_versions',JSON.stringify(Object.fromEntries(Object.entries(this.fvgFrames).map(([tf,frame])=>[tf,frame.version]))));
        }
        const costs=window.Composer?.config.featureStyles?.opportunity_buy_1;
        if(costs){qs.set('fee_bps',String(costs.feeBps??4));qs.set('slippage_bps',String(costs.slippageBps??2));}
        if(before===null&&['liquidity_bids','liquidity_asks','liquidity_heatmap'].some(k=>window.Composer?.config.featureStyles?.[k]?.visible))qs.set('liquidity','1');
        if(before===null && Object.entries(window.Composer?.config.featureStyles||{}).some(([k,v])=>k.startsWith('vp_')&&v.visible))qs.set('volume_profile','1');
        if (before !== null) qs.set("before", before);
        else if (this.liveEnabled && includeLive) qs.set("live", "1");
        for (let attempt = 0; attempt < 3; attempt++) {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 12000);
            try {
                const response = await fetch(`/api/bars?${qs}`, { cache: "no-store", signal: controller.signal });
                const packet = await response.json();
                if (response.status === 503 && attempt < 2) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                    continue;
                }
                if (!response.ok) throw new Error(packet.error || `Stored bars: HTTP ${response.status}`);
                if (!Array.isArray(packet.bars)) throw new Error("Invalid stored-bar packet");
                return packet;
            } catch (error) {
                if (error.name === "AbortError") throw new Error("Chart server timed out. Use Reload to retry.");
                if (error instanceof TypeError) throw new Error("Cannot reach the chart server. Run python3 restart_ui.py, then Reload.");
                throw error;
            } finally { clearTimeout(timer); }
        }
    },

    _applyFVG(packet){
        let changed=false;
        for(const [tf,frame] of Object.entries(packet.fvg_frames||{}))if(!frame.unchanged){
            if(this.fvgFrames[tf]?.version!==frame.version)changed=true;
            this.fvgFrames[tf]=frame;
        }
        return changed;
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

    async loadInitial(symbol, timeframe, before=null, { preserveViewport = false } = {}) {
        const generation = ++this._reloadGeneration;
        const initialState = { symbol, timeframe, bars: [], activeBars: [], latestBar: null,
            nextBefore: null, atLiveEdge: true, error: null,
            _olderPromise: null, _refreshPromise: null, _latestSignature: null, _refreshCount: 0,
            _fullRefreshVersion: 0, _appliedFullRefreshVersion: 0,
            historyPending: false, liveBars: preserveViewport ? this.liveBars : [],
            _liveAsOf: preserveViewport ? this._liveAsOf : null, liveError: preserveViewport ? this.liveError : null,
            volumeProfile:null, liquidity:null, featureProgress:null, fvgFrames:{}, srSnapshot:null, srFrames:{},
            liveStatus: preserveViewport ? this.liveStatus : (this.liveEnabled ? "loading" : "disabled") };
        this.loading = true;
        if (!preserveViewport) Object.assign(this, initialState);
        this.emit("loading");
        try {
            const packet = await this._fetchPage(symbol, timeframe, WINDOW_BARS, before);
            if (generation !== this._reloadGeneration) return false;
            if (preserveViewport) Object.assign(this, initialState);
            this.featureProgress=packet.feature_progress??null;
            this.srSnapshot=packet.sr_snapshot??null;
            this.srFrames=packet.sr_frames??{};
            this._applyFVG(packet);
            this.volumeProfile=packet.volume_profile??null;
            this.liquidity=packet.liquidity??null;
            this.historyPending=!!packet.history_pending;
            this._storageEpoch = packet.storage_epoch ?? "0:0";
            this.bars = packet.bars;
            this.activeBars = this.bars;
            this.latestBar = this.bars.at(-1) || null;
            this.nextBefore = packet.next_before;
            this._latestSignature = JSON.stringify(packet.bars);
            this._applyLive(packet.live);
            if(before!==null)this.atLiveEdge=false;
            this.loading = false;
            this.emit(preserveViewport ? "stored-refresh" : "reload");
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
            if ((packet.storage_epoch ?? "0:0") !== this._storageEpoch) {
                return this.loadInitial(this.symbol, this.timeframe);
            }
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

    refreshStored({full=false, includeLive=true}={}) {
        if(full)++this._fullRefreshVersion;
        if (this.loading || !this.atLiveEdge) return Promise.resolve(false);
        if (this._refreshPromise) return this._refreshPromise;
        const generation = this._reloadGeneration;
        // Healthy live charts need only the edge. A full 1,000-row response can
        // exceed 30 MB; refresh history only during replay or on explicit demand.
        const fullVersion=this._fullRefreshVersion;
        const replaying=this.historyPending||this.featureProgress?.status!=='features current';
        const limit=fullVersion>this._appliedFullRefreshVersion||(++this._refreshCount%12===0&&replaying)?WINDOW_BARS:2;
        const request = this._fetchPage(this.symbol, this.timeframe, limit, null, { includeLive });
        const work = request.then(packet => {
            if (generation !== this._reloadGeneration || this.loading || !this.atLiveEdge) return false;
            if(limit===WINDOW_BARS)this._appliedFullRefreshVersion=fullVersion;
            if ((packet.storage_epoch ?? "0:0") !== this._storageEpoch) {
                return this.loadInitial(this.symbol, this.timeframe);
            }
            const wasHistoryPending=this.historyPending;
            const historyChanged=this.historyPending!==!!packet.history_pending;
            if (wasHistoryPending && !packet.history_pending) {
                return this.loadInitial(this.symbol, this.timeframe, null, { preserveViewport: true });
            }
            const prior=this.latestBar;
            if(prior?.client?.close_time && packet.bars.length && packet.bars[0].open_time>prior.client.close_time+1){
                return this.loadInitial(this.symbol,this.timeframe, null, { preserveViewport: true });
            }
            this.historyPending=!!packet.history_pending;
            const progressChanged=JSON.stringify(this.featureProgress)!==JSON.stringify(packet.feature_progress??null);
            if(limit<WINDOW_BARS&&this.featureProgress&&this.featureProgress.status!=='features current'&&packet.feature_progress?.status==='features current')++this._fullRefreshVersion;
            this.featureProgress=packet.feature_progress??null;
            const srChanged=JSON.stringify([this.srSnapshot,this.srFrames])!==JSON.stringify([packet.sr_snapshot??null,packet.sr_frames??{}]);
            this.srSnapshot=packet.sr_snapshot??null;
            this.srFrames=packet.sr_frames??{};
            const fvgChanged=this._applyFVG(packet);
            const liquidityChanged=JSON.stringify(this.liquidity)!==JSON.stringify(packet.liquidity??null);
            this.liquidity=packet.liquidity??null;
            const profileChanged=JSON.stringify(this.volumeProfile)!==JSON.stringify(packet.volume_profile??null);
            this.volumeProfile=packet.volume_profile??null;
            const signature = JSON.stringify(packet.bars);
            const rowsChanged = signature !== this._latestSignature;
            const chartChanged = rowsChanged || historyChanged || profileChanged || fvgChanged || progressChanged || srChanged;
            if (rowsChanged) {
                this._latestSignature = signature;
                this._merge(packet.bars);
                this.latestBar = this.bars.at(-1) || null;
            }
            const liveChanged = this._applyLive(packet.live);
            if (chartChanged || (liquidityChanged && liveChanged)) this.emit("stored-refresh");
            else if (liveChanged) this.emit("live");
            else if (liquidityChanged) this.emit("liquidity");
            return chartChanged || liveChanged || liquidityChanged;
        }).finally(() => {
            if (this._refreshPromise === work) this._refreshPromise = null;
        });
        this._refreshPromise = work;
        return work;
    },
};
window.DataCache = DataCache;
