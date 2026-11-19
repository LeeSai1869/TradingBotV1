// One stored-bar stream. A bar owns client OHLCV, permanent features and ADCN.
// Retain visited history for smooth reversal; only fetch the next older page.
const WINDOW_BARS = 1000;
const BLOCK_BARS = 500;

const DataCache = {
    symbol: null,
    timeframe: null,
    bars: [],
    liveEnabled: true,
    historyPending: false,
    formingBar: null,
    featureProgress: null,
    volumeProfile: null,
    liquidity:null,
    fvgFrames: {},
    srSnapshot:null,
    srFrames:{},
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
    _refreshCount: 0,
    _fullRefreshVersion: 0,
    _appliedFullRefreshVersion: 0,
    _storageEpoch: "0:0",
    _requests: new Set(),
    listeners: [],

    get renderBars() {
        return this.formingBar ? [...this.bars, this.formingBar] : this.bars;
    },

    _applyLive(live) {
        if(live)this.liveQuote=this.liveEnabled?(live.bar??null):null;
        const previous = JSON.stringify([this.formingBar, this.liveStatus]);
        const latest = this.bars.at(-1);
        if (!this.liveEnabled || !latest || this.formingBar?.open_time <= latest.open_time) {
            this.formingBar = null;
        }
        if (live && this.liveEnabled) {
            this.liveStatus = live.status;
            if (live.status === "inactive") this.formingBar = null;
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
        const changed=previous !== JSON.stringify([this.formingBar, this.liveStatus]);
        if(changed)this._liveVersion=(this._liveVersion||0)+1;
        return changed;
    },

    subscribe(fn) { this.listeners.push(fn); },
    emit(op, meta = {}) {
        for (const fn of this.listeners) fn(this, op, meta);
    },

    async _fetchPage(symbol, timeframe, limit, before = null, includeLive = true) {
        const generation=this._reloadGeneration;
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
            if(generation!==this._reloadGeneration)throw Object.assign(new Error('Superseded chart request'),{name:'AbortError'});
            const controller = new AbortController();
            this._requests.add(controller);
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
                if(generation!==this._reloadGeneration)throw error;
                if (error.name === "AbortError") throw new Error("Chart server timed out. Use Reload to retry.");
                if (error instanceof TypeError) throw new Error("Cannot reach the chart server. Run python3 restart_ui.py, then Reload.");
                throw error;
            } finally { clearTimeout(timer);this._requests.delete(controller); }
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
        this._barsVersion=(this._barsVersion||0)+1;
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

    async loadInitial(symbol, timeframe, before=null) {
        const generation = ++this._reloadGeneration;
        for(const controller of this._requests)controller.abort();
        this._requests.clear();
        Object.assign(this, { symbol, timeframe, bars: [], activeBars: [], latestBar: null,
            nextBefore: null, loading: true, atLiveEdge: true, error: null,
            _olderPromise: null, _refreshPromise: null, _livePromise: null, _latestSignature: null, _refreshCount: 0,
            _fullRefreshVersion: 0, _appliedFullRefreshVersion: 0,
            historyPending: false, formingBar: null, liveQuote:null, volumeProfile:null, liquidity:null, featureProgress:null, fvgFrames:{}, srSnapshot:null, srFrames:{}, liveStatus: this.liveEnabled ? "loading" : "disabled" });
        this.emit("loading");
        try {
            const packet = await this._fetchPage(symbol, timeframe, WINDOW_BARS, before);
            if (generation !== this._reloadGeneration) return false;
            this.featureProgress=packet.feature_progress??null;
            this.srSnapshot=packet.sr_snapshot??null;
            this.srFrames=packet.sr_frames??{};
            this._applyFVG(packet);
            this.volumeProfile=packet.volume_profile??null;
            this.liquidity=packet.liquidity??null;
            this.historyPending=!!packet.history_pending;
            this._storageEpoch = packet.storage_epoch ?? "0:0";
            this.bars = packet.bars;
            this._barsVersion=(this._barsVersion||0)+1;
            this.activeBars = this.bars;
            this.latestBar = this.bars.at(-1) || null;
            this.nextBefore = packet.next_before;
            this._latestSignature = JSON.stringify(packet.bars);
            this._applyLive(packet.live);
            if(before!==null)this.atLiveEdge=false;
            this.loading = false;
            this.emit("reload");
            return true;
        } catch(error) {
            if(generation!==this._reloadGeneration)return false;
            throw error;
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

    refreshLive() {
        if (!this.liveEnabled || !this.symbol || !this.timeframe) return Promise.resolve(false);
        if (this._livePromise) return this._livePromise;
        const generation=this._reloadGeneration;
        const controller=new AbortController();this._requests.add(controller);
        const timer=setTimeout(()=>controller.abort(),4000);
        const qs=new URLSearchParams({symbol:this.symbol,interval:this.timeframe});
        const work=fetch(`/api/chart_live?${qs}`,{cache:'no-store',signal:controller.signal})
            .then(async response=>{
                const packet=await response.json();
                if(!response.ok)throw new Error(packet.error||'Live snapshot unavailable');
                if(generation!==this._reloadGeneration)return false;
                const priorQuote=JSON.stringify(this.liveQuote?.client??null),priorStatus=this.liveStatus;
                let changed=false;
                if(!this.loading&&this.atLiveEdge)changed=this._applyLive(packet.live);
                else {this.liveQuote=packet.live?.bar??null;this.liveStatus=packet.live?.status??'unavailable';}
                if(changed)this.emit('live');
                if(priorQuote!==JSON.stringify(this.liveQuote?.client??null)||priorStatus!==this.liveStatus)this.emit('quote');
                return changed;
            }).finally(()=>{
                clearTimeout(timer);this._requests.delete(controller);
                if(this._livePromise===work)this._livePromise=null;
            });
        this._livePromise=work;return work;
    },

    refreshStored({full=false}={}) {
        if(full)++this._fullRefreshVersion;
        if (this.loading || !this.atLiveEdge) return Promise.resolve(false);
        if (this._refreshPromise) return this._refreshPromise;
        const generation = this._reloadGeneration;
        // Healthy live charts need only the edge. A full 1,000-row response can
        // exceed 30 MB; refresh history only during replay or on explicit demand.
        const fullVersion=this._fullRefreshVersion;
        const replaying=this.historyPending||this.featureProgress?.status!=='features current';
        const limit=fullVersion>this._appliedFullRefreshVersion||(++this._refreshCount%12===0&&replaying)?WINDOW_BARS:2;
        const request = this._fetchPage(this.symbol, this.timeframe, limit, null, false);
        const work = request.then(packet => {
            if (generation !== this._reloadGeneration || this.loading || !this.atLiveEdge) return false;
            if(limit===WINDOW_BARS)this._appliedFullRefreshVersion=fullVersion;
            if ((packet.storage_epoch ?? "0:0") !== this._storageEpoch) {
                return this.loadInitial(this.symbol, this.timeframe);
            }
            const wasHistoryPending=this.historyPending;
            const historyChanged=this.historyPending!==!!packet.history_pending;
            this.historyPending=!!packet.history_pending;
            if(wasHistoryPending&&!this.historyPending)return this.loadInitial(this.symbol,this.timeframe);
            const prior=this.latestBar;
            if(prior?.client?.close_time && packet.bars.length && packet.bars[0].open_time>prior.client.close_time+1){
                return this.loadInitial(this.symbol,this.timeframe);
            }
            const progressChanged=JSON.stringify(this.featureProgress)!==JSON.stringify(packet.feature_progress??null);
            if(limit<WINDOW_BARS&&this.featureProgress&&this.featureProgress.status!=='features current'&&packet.feature_progress?.status==='features current')++this._fullRefreshVersion;
            this.featureProgress=packet.feature_progress??null;
            const srChanged=JSON.stringify([this.srSnapshot,this.srFrames])!==JSON.stringify([packet.sr_snapshot??null,packet.sr_frames??{}]);
            if(srChanged){this.srSnapshot=packet.sr_snapshot??null;this.srFrames=packet.sr_frames??{};}
            const fvgChanged=this._applyFVG(packet);
            const liquidityChanged=JSON.stringify(this.liquidity)!==JSON.stringify(packet.liquidity??null);
            this.liquidity=packet.liquidity??null;
            const profileChanged=JSON.stringify(this.volumeProfile)!==JSON.stringify(packet.volume_profile??null);
            this.volumeProfile=packet.volume_profile??null;
            // Compare matching rows, not the initial 1,000-row packet against
            // a two-row edge poll. An unchanged edge must not rebuild the chart.
            const existing=new Map(this.bars.map(bar=>[bar.open_time,bar]));
            const signature = JSON.stringify(packet.bars);
            const changedRows=packet.bars.filter(bar=>JSON.stringify(existing.get(bar.open_time))!==JSON.stringify(bar));
            const barsChanged=changedRows.length>0;
            const changed = barsChanged || historyChanged || profileChanged || fvgChanged || progressChanged || srChanged || liquidityChanged;
            if (changed) {
                this._latestSignature = signature;
                if(barsChanged)this._merge(changedRows);
                this.latestBar = this.bars.at(-1) || null;
            }
            const liveChanged = this._applyLive(packet.live);
            if (changed) this.emit("stored-refresh");
            else if (liveChanged) this.emit("live");
            return changed || liveChanged;
        }).catch(error=>{
            if(generation!==this._reloadGeneration)return false;
            throw error;
        }).finally(() => {
            if (this._refreshPromise === work) this._refreshPromise = null;
        });
        this._refreshPromise = work;
        return work;
    },
};
window.DataCache = DataCache;
