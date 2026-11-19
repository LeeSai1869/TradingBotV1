import { requireSignIn } from "./login.js";
import { logicalShift, readableRange } from "./window_state.js";
import * as symbolControl from "../controls/symbol/index.js";
import * as timeframeControl from "../controls/timeframe/index.js";
import * as reloadControl from "../controls/reload/index.js";
import * as latestControl from "../controls/latest/index.js";
import * as storedPoll from "./stored_poll.js";
import {zoneReadiness} from '../overlays/zones/readiness.js';
import {HTF,intervalMs} from "../overlays/zones/fvg.js";

const PREFETCH_BARS = 500;
const status = () => document.getElementById("status");
let loadId = 0;

async function loadAll() {
    const id = ++loadId;
    DataCache.alertReference=null;
    if(new URLSearchParams(location.search).has('at'))history.replaceState(null,'','/');
    const symbol = symbolControl.value();
    const timeframe = timeframeControl.value();
    status().textContent = `Loading ${symbol} ${timeframe}...`;
    try {
        if (await DataCache.loadInitial(symbol, timeframe, null, {pricesFirst: true}) && id === loadId) {
            await DataCache.prefetchOlder({limit: 1000});
        }
    } catch (error) {
        if (id === loadId) status().textContent = `Error: ${error.message}`;
    }
}

(async () => {
    await requireSignIn();
    const chart = Canvas.init(document.getElementById("chart"));
    await Composer.mountAll(chart);
    DataCache.liveEnabled = Composer.config.live_candle !== false;
    let renderedBars = [],renderedScope=null,needsRecovery=false,renderError=null;
    let rendering = false;
    let pending = null;
    let dragging = false;
    let boundaryFrame = 0;
    let renderGeneration = 0;

    function updateStatus() {
        const view=chart.timeScale().getVisibleLogicalRange();
        const visible=view?Math.max(0,Math.min(renderedBars.length-1,Math.floor(view.to))-Math.max(0,Math.ceil(view.from))+1):0;
        const bar=DataCache.latestBar, client=bar?.client;
        const duration=client ? client.close_time-bar.open_time+1 : 0;
        const behind=duration>0 && Date.now()-client.close_time>2*duration;
        const historyNotice=DataCache.historyPending ? ' | Earlier history pending' : behind ? ` | Historical data through ${new Date(client.close_time).toLocaleString()} — not current price` : '';
        const progress=DataCache.featureProgress;
        const stamp=t=>t==null?'not started':new Date(t).toLocaleString();
        const zonesPending=zoneReadiness(progress,DataCache.fvgFrames,Composer.config.featureStyles||{},DataCache.timeframe,DataCache.srFrames);
        const zoneNotice=zonesPending?` | ${zonesPending}`:'';
        const featureNotice=progress?progress.repair?` | Feature repair${progress.active===false?' paused':''}: ${progress.repair.columns} columns through ${stamp(progress.repair.through)}; target ${stamp(progress.repair.target)}`:
            progress.active===false?` | Features paused at ${stamp(progress.through)}`:progress.status==='features current'?' | Features current':` | Features through ${stamp(progress.through)} (${progress.status})`:'';
        const text = DataCache.error
            ? `History error: ${DataCache.error} — move the chart to retry`
            : `${DataCache.symbol} ${DataCache.timeframe} | ` +
              `${visible} candles in view | ` +
              `${DataCache.activeBars.length} active candles | ${DataCache.bars.length} cached` +
              (DataCache.liveEnabled ? ` | ${DataCache.liveQuote?.client?.close!=null?'Live price: '+DataCache.liveQuote.client.close+' | ':''}${DataCache.liveStatus}` : "") + historyNotice + featureNotice + zoneNotice;
        if (status().textContent !== text) status().textContent = text;
    }

    function checkBoundary() {
        if (rendering || pending || DataCache.loading) return;
        const range = chart.timeScale().getVisibleLogicalRange();
        DataCache.setVisibleWindow(range);
        latestControl.update(chart, DataCache);
        updateStatus();
        // The preceding page is already part of the render dataset before
        // it enters view. Arrival runs this check again and prepares the next.
        if (!dragging && range && range.from <= PREFETCH_BARS && DataCache.nextBefore !== null) {
            void DataCache.prefetchOlder();
        }
    }

    function render() {
        if (rendering || !pending || (dragging && !pending.reset && !pending.latest)) return;
        const { op, latest, span } = pending;
        const scope = `${DataCache.symbol}:${DataCache.timeframe}`;
        const reset = pending.reset || renderedScope !== scope;
        pending = null;
        if(op==='live'&&!reset&&!latest&&renderedScope===`${DataCache.symbol}:${DataCache.timeframe}`&&DataCache.formingBar&&renderedBars.at(-1)?.provisional&&renderedBars.at(-1).time===DataCache.formingBar.time){
            Composer.updateLive(chart,DataCache);
            renderedBars=DataCache.renderBars;
            updateStatus();return;
        }
        rendering = true;
        const generation = ++renderGeneration;
        try {
            const range = chart.timeScale().getVisibleLogicalRange();
            const bars = DataCache.renderBars;
            let target = null;
            if (latest && bars.length) {
                const last = bars.length - 1;
                target = { from: last - span, to: last };
                chart.priceScale("right").applyOptions({ autoScale: true });
            } else if (reset && bars.length) {
                target = readableRange(bars.length, chart.timeScale().width(), DataCache.timeframe);
                symbolControl.applyPriceFormat(DataCache.symbol, bars,
                    Composer.config.price_precision?.[DataCache.symbol]);
            } else if (range && renderedBars.length && bars.length) {
                const following = (op === "stored-refresh" || op === "live") && DataCache.atLiveEdge &&
                    range.to >= renderedBars.length - 2;
                const shift = following ? bars.length - renderedBars.length
                    : logicalShift(renderedBars, bars);
                if (shift) target = { from: range.from + shift, to: range.to + shift };
            }
            // All consumers receive the same canonical bars. No visual fetches
            // its own candles/features/decisions, and no visible history is evicted.
            Composer.updateAll(chart, { ...DataCache, formingBar: DataCache.formingBar, bars }, op, { resetViewport: reset });
            renderedBars = bars;renderedScope=bars.length ? scope : null;needsRecovery=false;
            if (op === "prices") status().textContent = `${DataCache.symbol} ${DataCache.timeframe} | Loading indicators…`;
            if(DataCache.error===renderError)DataCache.error=null;
            renderError=null;
            if (target) chart.timeScale().setVisibleLogicalRange(target);
        } catch(error) {
            // A format/viewport error must not leave old-market candles frozen
            // behind a new market's independent quote label.
            console.error('[chart render]',error);
            const empty={...DataCache,bars:[],renderBars:[],formingBar:null,liveQuote:null,fvgFrames:{},srSnapshot:null,srFrames:{}};
            for(const visual of [...Composer.visuals,...Composer.panels])try{if(visual.clear)visual.clear(chart);else visual.update?.(chart,empty,{op:'loading',resetViewport:true});}catch{}
            renderedBars=[];renderedScope=null;needsRecovery=true;Composer._seriesKey=null;
            renderError=`Chart render failed: ${error.message}. Reload or change settings to retry.`;
            DataCache.error=renderError;status().textContent=renderError;
        } finally {
            requestAnimationFrame(() => requestAnimationFrame(() => {
                if (generation !== renderGeneration) return;
                rendering = false;
                if (pending) render();
                else checkBoundary();
            }));
        }
    }

    DataCache.subscribe((cache, op) => {
        if (op === "loading") latestControl.update(chart, cache);
        if (op === "error") { updateStatus(); return; }
        if (op === "liquidity" && !dragging && !pending && !rendering) { Composer.updateLiquidity(chart, cache); return; }
        if(op==='quote'){Composer.visuals.find(v=>v.name==='candles')?.updateQuote?.(chart,cache.liveQuote||cache.latestBar);updateStatus();return;}
        if (op === "live" && !dragging && !rendering && !pending && renderedScope===`${cache.symbol}:${cache.timeframe}` && cache.formingBar &&
            renderedBars.at(-1)?.provisional &&
            renderedBars.at(-1).time === cache.formingBar.time) {
            Composer.updateLive(chart, cache);
            renderedBars = cache.renderBars;
            updateStatus();
            return;
        }
        const reset=needsRecovery || op === "reload" || op === "loading" || op === "prices";
        pending = { op:pending?.op==='settings'&&!reset?'settings':op==='live'&&pending?pending.op:op, reset: reset || !!pending?.reset,
            latest: reset ? false : pending?.latest, span: reset ? undefined : pending?.span };
        render();
    });
    chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
        if (!boundaryFrame) boundaryFrame = requestAnimationFrame(() => {
            boundaryFrame = 0;
            checkBoundary();
        });
    });
    document.getElementById("chart").addEventListener("pointerdown", event => {
        if (event.isPrimary && event.button === 0) dragging = true;
    }, {capture: true, passive: true});
    function finishDrag() {
        if (!dragging) return;
        dragging = false;
        if (pending) render();
        checkBoundary();
    }
    for (const event of ["pointerup", "pointercancel", "blur"]) window.addEventListener(event, finishDrag);
    window.addEventListener("chart-settings-change", () => {
        pending = { op: "settings", reset: !!pending?.reset,
            latest: pending?.latest, span: pending?.span };
        render();
        const outputs=Composer.config.featureStyles||{};
        const needProfile=!DataCache.volumeProfile&&Object.entries(outputs).some(([k,v])=>k.startsWith('vp_')&&v.visible);
        const needCurrent=!DataCache.fvgFrames.current&&['bull_fvg_zones','bear_fvg_zones',`bull_fvg_${DataCache.timeframe}_zones`,`bear_fvg_${DataCache.timeframe}_zones`].some(k=>outputs[k]?.visible);
        const needHigher=Object.entries(HTF).some(([tf,duration])=>duration>intervalMs(DataCache.timeframe)&&!DataCache.fvgFrames[tf]&&['bull','bear'].some(side=>outputs[`${side}_fvg_${tf}_zones`]?.visible));
        const needSR=!DataCache.srSnapshot&&Object.entries(outputs).some(([key,value])=>(['support_zones','resistance_zones','inst_support_zones','inst_resistance_zones'].includes(key)||/_(ob|breaker)_zones$/.test(key))&&value?.visible);
        const needLiquidity=!DataCache.liquidity&&['liquidity_bids','liquidity_asks','liquidity_heatmap'].some(k=>outputs[k]?.visible);
        const needInstitutional=Object.entries(outputs).some(([k,v])=>['inst_support_zones','inst_resistance_zones'].includes(k)&&v.visible&&v.higher!==false);
        if(needProfile||needCurrent||needHigher||needSR||needLiquidity||needInstitutional||Object.entries(outputs).some(([key,v])=>key.startsWith('opportunity_')&&v.visible)){
            const full=Object.entries(outputs).some(([key,v])=>key.startsWith('opportunity_')&&v.visible);
            void DataCache.refreshStored({full}).catch(error=>{status().textContent=error.message;});
        }
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
        if(DataCache.alertReference!=null){void loadAll();return;}
        const range = chart.timeScale().getVisibleLogicalRange();
        DataCache.atLiveEdge = true;
        pending = { op: "latest", reset: false, latest: true,
            span: range ? range.to - range.from : 999 };
        render();
        void DataCache.refreshStored().catch(error => {
            status().textContent = `Latest candle refresh failed: ${error.message}`;
        });
    });
    let navigation=0;
    window.openAlertChart=async event=>{
        const sequence=++navigation,symbol=String(event.symbol||''),tf=String(event.interval||''),at=Number(event.bar_time);
        const symbolSelect=document.getElementById('symbol'),tfSelect=document.getElementById('interval');
        if(!/^[A-Z0-9]{2,30}$/.test(symbol)||![...tfSelect.options].some(option=>option.value===tf)||!Number.isSafeInteger(at)||at<0||at>Date.now())throw new Error('Invalid notification chart link');
        if(![...symbolSelect.options].some(option=>option.value===symbol)){const option=new Option(symbol+' (alert history)',symbol);symbolSelect.add(option);}
        ++loadId;
        for(const dialog of document.querySelectorAll('dialog[open]'))dialog.close();
        symbolSelect.value=symbol;symbolControl.syncSelection();tfSelect.value=tf;timeframeControl.refreshButtons();
        const before=Math.min(Date.now(),at+100*intervalMs(tf));
        const loaded=await DataCache.loadInitial(symbol,tf,before);
        if(!loaded||sequence!==navigation||DataCache.symbol!==symbol||DataCache.timeframe!==tf)return;
        await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
        const index=DataCache.renderBars.findIndex(bar=>bar.open_time===at);
        if(index<0){status().textContent='The notification candle is no longer stored.';return;}
        DataCache.alertReference=at;DataCache.atLiveEdge=false;chart.timeScale().setVisibleLogicalRange({from:Math.max(0,index-45),to:index+45});
        history.replaceState(null,'','/?'+new URLSearchParams({symbol,interval:tf,at:String(at)}));
        document.getElementById('chart').focus();
    };
    const target=new URLSearchParams(location.search);
    if(target.has('at')){
        try{await window.openAlertChart({symbol:target.get('symbol'),interval:target.get('interval'),bar_time:Number(target.get('at'))});}
        catch(error){status().textContent=error.message;}
    }else await loadAll();
    const interval = Composer.config.stored_refresh_ms ?? 5000;
    storedPoll.start(interval, DataCache.liveEnabled);
})();
