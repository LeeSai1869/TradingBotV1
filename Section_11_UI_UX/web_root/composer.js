// ============================================================
// COMPOSER — registers every visual, panel, and control.
// Adding a feature = one import + one list entry.
// ============================================================

import * as candles from "../overlays/candles/index.js";
import * as markers from "../overlays/markers/index.js";
import * as ema50 from "../overlays/ema50/index.js";

import * as flagsPanel from "../panels/flags/index.js";

import * as symbolControl from "../controls/symbol/index.js";
import * as timeframeControl from "../controls/timeframe/index.js";
import * as reloadControl from "../controls/reload/index.js";
import * as autoscaleControl from "../controls/autoscale/index.js";
import * as latestControl from "../controls/latest/index.js";
import * as alertsControl from "../controls/alerts/index.js";
import * as settingsControl from "../controls/settings/index.js";

const VISUALS = [candles, markers, ema50];
const PANELS = [flagsPanel];

const Composer = {
    mounted: false,
    config: { display: {}, stored_refresh_ms: 5000, price_precision: {} },

    visuals: VISUALS,
    panels: PANELS,

    controls: {
        symbol: symbolControl,
        timeframe: timeframeControl,
        reload: reloadControl,
        autoscale: autoscaleControl,
        latest: latestControl,
        settings: settingsControl,
        alerts: alertsControl,
    },

    async mountAll(chart) {
        if (this.mounted) return;
        const response = await fetch("/api/ui_config", { cache: "no-store" });
        if (response.ok) this.config = { ...this.config, ...await response.json() };

        for (const v of this.visuals) {
            try {
                if (v.mount) await v.mount(chart);
            } catch (e) {
                console.error(
                    `[composer] ${v.name} mount failed:`,
                    e
                );
            }
        }

        for (const p of this.panels) {
            try {
                if (p.mount) await p.mount(chart);
            } catch (e) {
                console.error(
                    `[composer] ${p.name} mount failed:`,
                    e
                );
            }
        }

        for (const c of Object.values(this.controls)) {
            try {
                if (c.mount) await c.mount(chart);
            } catch (e) {
                console.error(
                    "[composer] control mount failed:",
                    e
                );
            }
        }

        this.mounted = true;
    },

    updateLive(chart, data) {
        for (const v of this.visuals) {
            if (v.updateLive && this.config.display?.[v.name] !== false) {
                v.updateLive(chart, data.formingBar);
            }
        }
    },

    updateAll(chart, data, op = "reload", options = {}) {
        for (const v of this.visuals) {
            try {
                if (v.update) {
                    v.update(chart, data, { ...options, visible: this.config.display?.[v.name] !== false });
                }
            } catch (e) {
                console.error(
                    `[composer] ${v.name} update failed:`,
                    e
                );
            }
        }

        for (const p of this.panels) {
            try {
                if (p.update) {
                    p.update(chart, data);
                }
            } catch (e) {
                console.error(
                    `[composer] ${p.name} update failed:`,
                    e
                );
            }
        }
    },
};

window.Composer = Composer;
