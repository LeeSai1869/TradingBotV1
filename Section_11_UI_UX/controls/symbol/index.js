// CONTROL: symbol dropdown + per-symbol price format.
import { setPriceFormat } from "../../overlays/candles/index.js";
export const name = "symbol";
const el = () => document.getElementById("symbol");

export async function mount() {
    try {
        const r = await fetch("/api/symbols", { cache: "no-store" });
        const data = await r.json();
        const syms = Array.isArray(data.symbols) ? data.symbols : [];
        const sel = el();
        sel.innerHTML = "";
        for (const s of (syms.length ? syms : ["BTCUSDT"])) {
            const opt = document.createElement("option");
            opt.value = s; opt.textContent = s;
            sel.appendChild(opt);
        }
        if (syms.includes("BTCUSDT")) sel.value = "BTCUSDT";
    } catch (e) {
        console.error("[symbol] populate failed:", e);
        el().innerHTML = '<option value="BTCUSDT">BTCUSDT</option>';
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
