// Chart preferences are browser-local. Runner policies remain owned by Core.
import { FEATURE_STYLES, migrateStyles } from "./feature_styles.js";
import * as admin from "./admin_controls.js";
export const name = "settings";
const STORAGE = "tradingbot.chart-settings.v1";
const PERIODS = [7, 25, 50, 100, 200, 300];
const defaults = { candles: true, markers: true, flags: true, ema: true };
let saved = { ...defaults }, draft, dialog, content, sidebar, tabs;
let featureTab = "Style";
let section = "general", item = "Chart", registry = null, registryError = "";
const selectedCoins = new Set();
const sections = {
    general: ["Chart", "Account"], inputs: ["Overview"],
    features: ["EMA", "RSI", "ADX", "ATR", "Volume", "VWAP"],
    candles: ["Display"], timeframes: ["Downloads"],
    coins: ["Approved", "Inactive", "Disapproved", "Ineligible", "Pending", "Staged"],
};
const titles = { general: "General", inputs: "Inputs", features: "Features",
    candles: "Candles", timeframes: "Timeframes", coins: "Coins" };

function validated(value) {
    const result = { ...defaults };
    if (!value || typeof value !== "object") value = {};
    for (const key of ["candles", "markers", "flags", "ema"]) {
        if (typeof value[key] === "boolean") result[key] = value[key];
    }
    result.outputs = migrateStyles(value);
    return result;
}

function apply() {
    const config = window.Composer.config;
    config.display = { ...config.display, candles: saved.candles, markers: saved.markers, ema50: saved.ema };
    config.featureStyles = saved.outputs;
    config.ema = { periods: PERIODS.filter(p => saved.outputs[`ema${p}`].visible) };
    document.getElementById("flags-panel").hidden = !saved.flags;
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
    if (item === "EMA") toggle("Show EMA", "ema");
    else note("Style preferences can be saved now. This feature’s chart renderer is not connected yet.");
    if (featureTab === "Display") {
        for (const [key, label] of feature.outputs) {
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
    const table = el("div", "", content, "settings-style-table");
    const heading = el("div", "", table, "settings-style-row settings-style-heading");
    for (const title of ["Output", "Color", "Width", "Line style"]) el("span", title, heading);
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
        for (const [field, title, options] of [
            ["width", "width", [[1,"1 px"],[2,"2 px"],[3,"3 px"],[4,"4 px"]]],
            ["style", "line style", [[0,"Solid"],[1,"Dotted"],[2,"Dashed"]]],
        ]) {
            const select = el("select", "", row);
            select.setAttribute("aria-label", `${label} ${title}`);
            for (const [value, text] of options) { const option = el("option", text, select); option.value = value; }
            select.value = state[field];
            select.onchange = () => { state[field] = Number(select.value); };
            if (presentation !== "line") {
                select.disabled = true;
                select.title = "Histogram output uses bar color; line controls do not apply.";
            }
        }
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
        toggle("Show stored signal panel", "flags");
        toggle("Show BUY / SELL markers", "markers");
        note("Chart preferences apply when you choose Apply and are saved in this browser.");
    } else if (section === "candles") {
        toggle("Show candles and current-price line", "candles");
        note("Candles and features come from the combined bar stream.");
    } else if (section === "features") {
        renderFeature();
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
    save.onclick = () => {
        const next = validated(draft);
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
    dialog.addEventListener("close", () => gear.focus());
}
