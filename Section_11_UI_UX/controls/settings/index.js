// Chart preferences are browser-local. Runner policies remain owned by Core.
import { FEATURE_STYLES, migrateStyles } from "./feature_styles.js";
import {normalizeHud} from "../workspace/preferences.js";
import {renderHudSettings} from "../workspace/settings.js";
import * as admin from "./admin_controls.js";
import {normalizeMomentum,SOUNDS} from '../../overlays/markers/preferences.js';
import {enableSignalSound,playSignalSound} from '../alerts/index.js';
import {normalizeCandleStyle} from './candle_style.js';
export const name = "settings";
const STORAGE = "tradingbot.chart-settings.v1";
const PERIODS = [7, 25, 50, 100, 200, 300];
const defaults = { candles: true, markers: true, ema: true };
let saved = { ...defaults }, draft, dialog, content, sidebar, tabs;
let featureTab = "Style";
let section = "general", item = "Chart", registry = null, registryError = "";
const selectedCoins = new Set();
const sections = {
    general: ["Chart", "Account"], inputs: ["Overview"],
    features: ["EMA", "WMA", "RSI", "ADX", "DI", "ATR", "Volume", "Volume Profile", "VWAP", "Support / Resistance", "FVG", "Momentum Indicator"],
    hud: ["Comparison"], candles: ["Display"], timeframes: ["Downloads"],
    coins: ["Approved", "Inactive", "Disapproved", "Ineligible", "Pending", "Staged"],
};
const titles = { general: "General", inputs: "Inputs", features: "Features",
    hud: "HUD", candles: "Candles", timeframes: "Timeframes", coins: "Coins" };

function validated(value) {
    const result = { ...defaults };
    if (!value || typeof value !== "object") value = {};
    for (const key of ["candles", "markers", "ema"]) {
        if (typeof value[key] === "boolean") result[key] = value[key];
    }
    result.outputs = migrateStyles(value);
    result.candleStyle=normalizeCandleStyle(value.candleStyle);
    result.hud = normalizeHud(value.hud);
    result.momentumSounds=normalizeMomentum(value.momentumSounds);
    const lower=Number(value.rsiLevels?.lower??30), upper=Number(value.rsiLevels?.upper??70);
    result.rsiLevels = Number.isFinite(lower) && Number.isFinite(upper) && lower>=0 && upper<=100 && lower<upper?{lower,upper}:{lower:30,upper:70};
    return result;
}

function apply() {
    const config = window.Composer.config;
    config.hud = saved.hud;
    config.momentumSounds=saved.momentumSounds;
    config.rsiLevels = saved.rsiLevels;
    config.display = { ...config.display, candles: saved.candles, markers: saved.markers, ema50: saved.ema };
    config.featureStyles = saved.outputs;
    config.candleStyle=saved.candleStyle;
    config.ema = { periods: PERIODS.filter(p => saved.outputs[`ema${p}`].visible) };
}

function el(tag, text, parent, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    if (parent) parent.append(node);
    return node;
}
function note(text) { el("p", text, content, "settings-note"); }
function toggle(label, key, parent = content) {
    const row = el("label", "", parent, "settings-row");
    el("span", label, row);
    const input = el("input", "", row);
    input.type = "checkbox"; input.role = "switch"; input.checked = draft[key];
    input.addEventListener("change", () => { draft[key] = input.checked; });
}
function reserved(label, explanation) {
    const row = el("div", "", content, "settings-row");
    el("span", label, row);
    const control = el("button", "Not connected yet", row);
    control.disabled = true;
    note(explanation);
}
function renderFeature() {
    const feature = FEATURE_STYLES[item];
    const subnav = el("nav", "", content, "settings-subtabs");
    subnav.setAttribute("aria-label", `${item} options`);
    for (const title of ["Display", "Style"]) {
        const button = el("button", title, subnav);
        button.setAttribute("aria-pressed", String(featureTab === title));
        button.onclick = () => {
            featureTab = title; render();
            content.querySelector(`[aria-pressed="true"]`).focus();
        };
    }
    if(item==='Momentum Indicator') {
        toggle('Show Momentum Indicator','markers');
        note('Section 8 BUY/SELL signals use closed candles with complete formula-v3 features. Current signals wait for feature replay; historical markers never play sounds.');
        for(const side of ['buy','sell']) {
            const row=el('label',`${side.toUpperCase()} sound `,content,'settings-row'), select=el('select','',row);
            select.setAttribute('aria-label',`${side.toUpperCase()} sound`);
            for(const value of SOUNDS){const o=el('option',value,select);o.value=value;}
            select.value=draft.momentumSounds[side];select.onchange=()=>{draft.momentumSounds[side]=select.value;};
            const test=el('button',`Test ${side.toUpperCase()} sound`,content);
            test.onclick=async()=>{try{await enableSignalSound();playSignalSound(draft.momentumSounds[side],draft.momentumSounds.volume);}catch(error){note(error.message);}};
        }
        const row=el('label','Signal volume ',content,'settings-row'), volume=el('input','',row);
        volume.type='range';volume.min=0;volume.max=1;volume.step=.05;volume.value=draft.momentumSounds.volume;
        volume.setAttribute('aria-label','Signal volume');volume.oninput=()=>{draft.momentumSounds.volume=Number(volume.value);};
        const enable=el('button','Enable signal sounds',content);
        enable.onclick=async()=>{try{await enableSignalSound();note('Signal sounds enabled for this session and the open symbol/timeframe.');}catch(error){note(error.message);}};
    }
    if (item === "EMA") toggle("Show EMA", "ema");
    else note(`${item} reads the same combined stored bars as the chart. Missing values remain blank until calculated.`);
    if(item==='Volume Profile')note('POC, VAH and VAL plot each candle’s calculated values, like VWAP. Filled node bars stay on the side, span their full price ranges, and have separate opacity controls.');
    const selection=el('div','',content,'settings-selection');
    for(const [label,visible] of [['Select all',true],['Deselect all',false]]) {
        const button=el('button',label,selection);
        button.onclick=()=>{
            for(const [key] of feature.outputs)draft.outputs[key].visible=visible;
            if(item==='EMA' && visible)draft.ema=true;
            if(item==='Momentum Indicator'&&visible)draft.markers=true;
            render();
        };
    }
    if(item==='RSI') {
        const row=el('div','',content,'settings-row');
        for(const key of ['lower','upper']) {
            const label=el('label',`${key==='lower'?'Lower':'Upper'} reference level `,row), input=el('input','',label);
            input.type='number';input.min=0;input.max=100;input.value=draft.rsiLevels[key];
            input.setAttribute('aria-label',`RSI ${key} reference level`);input.onchange=()=>{draft.rsiLevels[key]=Number(input.value);};
        }
    }
    if (featureTab === "Display") {
        for (const [key, label,,presentation] of feature.outputs) {
            if(item==='Volume Profile'&&(key==='vp_poc'||key==='vp_histogram'))el('h4',presentation==='profile'?'Histogram bars':'Per-candle lines',content);
            const row = el("label", "", content, "settings-row");
            el("span", label, row);
            const check = el("input", "", row); check.type = "checkbox";
            check.checked = draft.outputs[key].visible;
            check.disabled = !feature.connected;
            check.onchange = () => { draft.outputs[key].visible = check.checked; };
        }
        note("Display choices use existing stored values; calculation periods and inputs stay unchanged.");
        return;
    }
    if(item==='Volume Profile'){
        for(const [key,label,min,max] of [['lengthPercent','Profile bar length (% of chart)',10,80]]){
            const row=el('label',label+' ',content,'settings-row'),input=el('input','',row);
            input.type='number';input.min=min;input.max=max;input.step=1;input.value=draft.outputs.vp_histogram[key];input.setAttribute('aria-label',label);
            input.onchange=()=>{draft.outputs.vp_histogram[key]=Math.max(min,Math.min(max,Number(input.value)||min));};
        }
    }
    const table = el("div", "", content, "settings-style-table");
    const heading = el("div", "", table, "settings-style-row settings-style-heading");
    for (const title of ["Output", "Color", item==='Momentum Indicator'?"Size":"Width", item==='Momentum Indicator'?"Shape":"Line style"]) el("span", title, heading);
    for (const [key, label, , presentation = "line"] of feature.outputs) {
        const state = draft.outputs[key];
        const row = el("div", "", table, "settings-style-row");
        const name = el("label", "", row, "settings-output-name");
        const check = el("input", "", name); check.type = "checkbox";
        check.checked = state.visible; check.disabled = !feature.connected;
        check.onchange = () => { state.visible = check.checked; };
        el("span", label, name);
        const color = el("input", "", row); color.type = "color";
        color.value = state.color; color.setAttribute("aria-label", `${label} color`);
        color.oninput = () => { state.color = color.value; };
        if(presentation==='marker') {
            const size=el('select','',row);size.setAttribute('aria-label',`${label} size`);
            for(const n of [1,2,3,4]){const o=el('option',String(n),size);o.value=n;}
            size.value=state.width;size.onchange=()=>{state.width=Number(size.value);};
            const shape=el('select','',row);shape.setAttribute('aria-label',`${label} shape`);
            for(const value of ['arrowUp','arrowDown','circle','square']){const o=el('option',value,shape);o.value=value;}
            shape.value=state.shape;shape.onchange=()=>{state.shape=shape.value;};
            const labelToggle=el('label','Show label ',content,'settings-row'), input=el('input','',labelToggle);
            input.type='checkbox';input.checked=state.label;input.setAttribute('aria-label',`${label} label`);input.onchange=()=>{state.label=input.checked;};
            continue;
        }
        if(presentation==='profile'){
            el('span','Profile layout',row);el('span','—',row);continue;
        }
        for (const [field, title, options] of [
            ["width", "width", [[1,"1 px"],[2,"2 px"],[3,"3 px"],[4,"4 px"]]],
            ["style", "line style", [[0,"Solid"],[1,"Dotted"],[2,"Dashed"]]],
        ]) {
            const select = el("select", "", row);
            select.setAttribute("aria-label", `${label} ${title}`);
            for (const [value, text] of options) { const option = el("option", text, select); option.value = value; }
            select.value = state[field];
            select.onchange = () => { state[field] = Number(select.value); };
            if (presentation === "histogram") {
                select.disabled = true;
                select.title = "Bars use color and opacity. Profile length applies to all bins; each bar spans its full price range.";
            }
        }
    }
    for(const [key,label,,presentation] of feature.outputs)if(['zone','profile'].includes(presentation)) {
        const caption=presentation==='profile'?`${label} bar opacity`:`${label} fill opacity`;
        const row=el('label',`${caption} (%) `,content,'settings-row');
        const input=el('input','',row);input.type='number';input.min=0;input.max=100;input.step=1;
        input.value=draft.outputs[key].opacity;input.setAttribute('aria-label',caption);
        input.onchange=()=>{draft.outputs[key].opacity=Math.max(0,Math.min(100,Number(input.value)||0));};
    }
    note("Each output keeps its own style. Unchecking an output preserves its color, width and line style.");
}

function render() {
    for (const tab of tabs.children) {
        tab.hidden = ["timeframes", "coins"].includes(tab.dataset.section) && !admin.isAdmin();
    }
    if (["timeframes", "coins"].includes(section) && !admin.isAdmin()) {
        section = "general"; item = "Account";
    }
    document.getElementById("settings-body").setAttribute("aria-labelledby", `settings-tab-${section}`);
    for (const tab of tabs.children) {
        const active = tab.dataset.section === section;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
    }
    sidebar.replaceChildren();
    for (const label of sections[section]) {
        const button = el("button", label, sidebar);
        button.classList.toggle("selected", item === label);
        button.setAttribute("aria-current", item === label ? "page" : "false");
        button.onclick = () => { item = label; render(); };
    }
    content.replaceChildren();
    el("div", `${titles[section]} / ${item}`, content, "settings-breadcrumb");
    el("h3", item === "Chart" ? "Chart preferences" : item, content);
    if (section === "general" && item === "Account") {
        admin.account(content, render);
    } else if (section === "general") {
        toggle("Show BUY / SELL markers", "markers");
        note("Chart preferences apply when you choose Apply and are saved in this browser.");
    } else if (section === "candles") {
        const nav=el('nav','',content,'settings-subtabs');
        for(const title of ['Display','Style']){const b=el('button',title,nav);b.setAttribute('aria-pressed',String(featureTab===title));b.onclick=()=>{featureTab=title;render();};}
        if(featureTab==='Display')toggle("Show candles and current-price line", "candles");
        else for(const [key,label] of Object.entries({upColor:'Bullish body',downColor:'Bearish body',wickUpColor:'Bullish wick',wickDownColor:'Bearish wick',borderUpColor:'Bullish border',borderDownColor:'Bearish border',wickVisible:'Show wicks',borderVisible:'Show borders'})){
            const row=el('label','',content,'settings-row');el('span',label,row);const input=el('input','',row);
            const check=typeof draft.candleStyle[key]==='boolean';input.type=check?'checkbox':'color';input.setAttribute('aria-label',label);
            if(check)input.checked=draft.candleStyle[key];else input.value=draft.candleStyle[key];
            input.onchange=()=>{draft.candleStyle[key]=check?input.checked:input.value;};
        }
        note("Candles and features come from the combined bar stream.");
    } else if (section === "features") {
        renderFeature();
    } else if (section === "hud") {
        void renderHudSettings(content, draft);
    } else if (section === "timeframes") {
        admin.renderTimeframes(content, render);
    } else if (section === "coins") {
        note("Registry entries are permanent. Category changes and data deletion apply immediately and preserve these entries.");
        if (item === "Approved") note("Approved coins currently in the top 50.");
        if (item === "Inactive") note("Still approved, but manually paused, outside the eligible top 50, or beyond the active cap. Downloads and processing are paused.");
        if (item === "Ineligible") note("Rule-based exclusions from the existing registry, including memes and stablecoins.");
        if (registryError) {
            note(registryError);
            const retry = el("button", "Retry loading registry", content); retry.onclick = loadRegistry;
        } else if (!registry) note("Loading coin registry…");
        else {
            const rows = registry[item.toLowerCase()] || [];
            el("p", `${rows.length} coins`, content, "settings-note");
            const count = el("p", `${selectedCoins.size} selected`, content, "settings-note");
            const selection = el("button", rows.length && rows.every(coin => selectedCoins.has(coin.symbol)) ? "Deselect all" : "Select all", content);
            selection.disabled = !rows.length;
            selection.onclick = () => {
                const all = rows.every(coin => selectedCoins.has(coin.symbol));
                for (const coin of rows) {
                    if (all) selectedCoins.delete(coin.symbol); else selectedCoins.add(coin.symbol);
                }
                render();
            };
            if (!rows.length) note("No coins in this category.");
            for (const coin of rows) {
                const row = el("label", "", content, "settings-coin");
                const check = el("input", "", row); check.type = "checkbox";
                check.setAttribute("aria-label", `Select ${coin.symbol}`);
                check.checked = selectedCoins.has(coin.symbol);
                check.onchange = () => {
                    if (check.checked) selectedCoins.add(coin.symbol);
                    else selectedCoins.delete(coin.symbol);
                    render();
                };
                el("strong", coin.symbol, row);
                el("span", coin.reason || coin.note || (coin.rank ? `Rank ${coin.rank}` : ""), row);
            }
        }
        admin.coinActions(content, selectedCoins, loadRegistry);
    } else {
        reserved("Input parameters", "Calculation inputs will be connected to the existing input configuration, one group at a time.");
    }
}
async function loadRegistry() {
    if (!admin.isAdmin()) return;
    registryError = ""; registry = null; if (section === "coins") render();
    try {
        const response = await fetch("/api/settings/coins", { cache: "no-store" });
        if (!response.ok) throw new Error("Cannot load coin registry. Make sure the updated UI server is running.");
        registry = await response.json();
    } catch (error) { registryError = error.message; }
    if (dialog.open && section === "coins") render();
}

export async function mount() {
    await admin.load();
    try {
        const raw = localStorage.getItem(STORAGE);
        // Preserve server display defaults until the user saves preferences.
        saved = raw ? validated(JSON.parse(raw)) : validated({
            outputs: migrateStyles(), candles: window.Composer.config.display?.candles !== false,
            markers: window.Composer.config.display?.markers !== false,
            ema: window.Composer.config.display?.ema50 !== false,
        });
    } catch { saved = validated(defaults); }
    apply();
    const gear = el("button", "", document.getElementById("toolbar"));
    const accountButton = el("button", `${window.AppSession.username} · ${window.AppSession.role === "admin" ? "Administrator" : "Normal user"}`, document.getElementById("toolbar"));
    accountButton.id = "account-button";
    gear.before(accountButton);
    accountButton.onclick = () => { section = "general"; item = "Account"; gear.click(); };
    gear.id = "settings-button"; gear.title = "Settings";
    gear.setAttribute("aria-label", "Open settings");
    gear.innerHTML = '<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M9.5 3h5l.6 2.4 2 1.2 2.4-.7 2.5 4.2-1.8 1.8v2.3l1.8 1.7-2.5 4.2-2.4-.7-2 1.2-.6 2.4h-5l-.6-2.4-2-1.2-2.4.7L2 15.9l1.8-1.7v-2.3L2 10.1l2.5-4.2 2.4.7 2-1.2Z"/><circle cx="12" cy="13" r="3"/></svg>';
    dialog = el("dialog", "", document.body); dialog.id = "settings-dialog";
    dialog.setAttribute("aria-labelledby", "settings-title");
    const header = el("header", "", dialog);
    el("h2", "Settings", header).id = "settings-title";
    const close = el("button", "×", header); close.setAttribute("aria-label", "Close settings"); close.onclick = () => dialog.close();
    tabs = el("nav", "", dialog, "settings-tabs"); tabs.setAttribute("role", "tablist"); tabs.setAttribute("aria-label", "Settings sections");
    for (const key of Object.keys(sections)) {
        const tab = el("button", titles[key], tabs); tab.dataset.section = key; tab.id = `settings-tab-${key}`;
        tab.setAttribute("role", "tab"); tab.setAttribute("aria-controls", "settings-body");
        tab.onclick = () => {
            section = key; item = sections[key][0]; render();
            if (key === "coins" && admin.isAdmin() && !registry) void loadRegistry();
        };
    }
    tabs.onkeydown = event => {
        const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
        if (!keys.includes(event.key)) return;
        event.preventDefault();
        const buttons = [...tabs.children].filter(button => !button.hidden), current = buttons.indexOf(document.activeElement);
        const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1
            : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
        buttons[next].focus(); buttons[next].click();
    };
    const body = el("div", "", dialog, "settings-body"); body.id = "settings-body"; body.setAttribute("role", "tabpanel");
    sidebar = el("nav", "", body, "settings-sidebar"); sidebar.setAttribute("aria-label", "Settings categories");
    content = el("section", "", body, "settings-content"); content.setAttribute("aria-live", "polite");
    const footer = el("footer", "", dialog);
    const message = el("span", "", footer); message.setAttribute("role", "status");
    const cancel = el("button", "Cancel", footer); cancel.onclick = () => dialog.close();
    const save = el("button", "Apply", footer, "settings-apply");
    save.onclick = async () => {
        if (!(draft.rsiLevels.lower>=0 && draft.rsiLevels.upper<=100 && draft.rsiLevels.lower<draft.rsiLevels.upper)) {
            message.textContent='RSI levels must be between 0 and 100, with lower below upper.';return;
        }
        const next = validated(draft);
        if(next.momentumSounds.buy!=='none'||next.momentumSounds.sell!=='none') {
            try{await enableSignalSound();}catch(error){message.textContent=error.message;return;}
        }
        try { localStorage.setItem(STORAGE, JSON.stringify(next)); }
        catch { message.textContent = "Could not save preferences in this browser."; return; }
        saved = next; apply(); window.dispatchEvent(new Event("chart-settings-change")); dialog.close();
    };
    gear.onclick = () => {
        draft = structuredClone(saved); selectedCoins.clear(); message.textContent = ""; render(); dialog.showModal();
        tabs.querySelector('[aria-selected="true"]').focus();
        if (section === "coins" && admin.isAdmin()) void loadRegistry();
        void admin.load().then(() => {
            if (dialog.open && (section === "coins" || section === "timeframes" || item === "Account")) render();
        }).catch(() => {});
    };
    window.addEventListener('open-feature-settings', event=>{
        if(!FEATURE_STYLES[event.detail])return;
        section='features';item=event.detail;featureTab='Style';gear.click();
    });
    window.addEventListener('feature-visibility-change',event=>{
        const feature=FEATURE_STYLES[event.detail.feature];if(!feature)return;
        for(const [key] of feature.outputs)saved.outputs[key].visible=event.detail.visible===true;
        try{localStorage.setItem(STORAGE,JSON.stringify(saved));}catch{}
        apply();window.dispatchEvent(new Event('chart-settings-change'));
    });
    window.addEventListener("hud-size-change", event => {
        saved.hud = normalizeHud({...saved.hud,size:event.detail});
        try {localStorage.setItem(STORAGE,JSON.stringify(saved));} catch {}
        apply();
    });
    window.addEventListener("hud-visibility-change", event => {
        saved.hud.visible = event.detail === true;
        try {localStorage.setItem(STORAGE, JSON.stringify(saved));} catch {}
        apply(); window.dispatchEvent(new Event("chart-settings-change"));
    });
    window.addEventListener("open-hud-settings", () => {section="hud";item="Comparison";gear.click();});
    dialog.addEventListener("close", () => gear.focus());
}
