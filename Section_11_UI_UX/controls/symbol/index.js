// CONTROL: symbol dropdown + per-symbol price format.
import { setPriceFormat } from "../../overlays/candles/index.js";
export const name = "symbol";
const el = () => document.getElementById("symbol");
let populateId = 0;

async function populate(preserve = false) {
    const id = ++populateId;
    try {
        const r = await fetch("/api/symbols", { cache: "no-store" });
        if (!r.ok) throw new Error(`Symbols: HTTP ${r.status}`);
        const data = await r.json();
        if (id !== populateId) return;
        const syms = Array.isArray(data.symbols) ? data.symbols : [];
        const sel = el();
        const current = preserve ? sel.value : null;
        sel.innerHTML = "";
        for (const s of (syms.length ? syms : ["BTCUSDT"])) {
            const opt = document.createElement("option");
            opt.value = s; opt.textContent = s;
            sel.appendChild(opt);
        }
        if (current && ![...sel.options].some(option => option.value === current)) {
            const option = document.createElement("option");
            option.value = current; option.textContent = `${current} (inactive)`;
            sel.append(option);
        }
        if (current) sel.value = current;
        else if (syms.includes("BTCUSDT")) sel.value = "BTCUSDT";
    } catch (e) {
        console.error("[symbol] populate failed:", e);
        if (id === populateId && !preserve) el().innerHTML = '<option value="BTCUSDT">BTCUSDT</option>';
    }
}

export function applyPriceFormat(symbol, bars, configuredPrecision) {
    if (el().value !== symbol) return;
    let precision = Number.isInteger(configuredPrecision)
        ? Math.max(0, Math.min(8, configuredPrecision)) : null;
    if (precision === null) {
        precision = 0;
        for (const bar of bars.slice(-1000)) {
            for (const key of ["open", "high", "low", "close"]) {
                const value = bar.client[key];
                if (!Number.isFinite(value)) continue;
                const [base, exponent = "0"] = String(value).toLowerCase().split("e");
                const decimals = (base.split(".")[1] || "").length - Number(exponent);
                precision = Math.max(precision, Math.min(8, decimals));
            }
        }
    }
    setPriceFormat({ type: "price", precision, minMove: Math.pow(10, -precision) });
}

export function value() { return el().value; }

export async function mount() { await populate(); }
export async function refresh() { await populate(true); }
