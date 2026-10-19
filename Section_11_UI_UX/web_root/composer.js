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

const VISUALS = [candles, markers, ema50];
const PANELS = [flagsPanel];

const Composer = {
    mounted: false,

    visuals: VISUALS,
    panels: PANELS,

    controls: {
        symbol: symbolControl,
        timeframe: timeframeControl,
        reload: reloadControl,
        autoscale: autoscaleControl,
    },

    async mountAll(chart) {
        if (this.mounted) return;

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

    updateAll(chart, data, op = "reload", options = {}) {
        for (const v of this.visuals) {
            try {
                if (v.update) {
                    v.update(chart, data, options);
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
