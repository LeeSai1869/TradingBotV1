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

export async function applyPriceFormat(symbol) {
    try {
        const r = await fetch(`/api/symbol_meta?symbol=${encodeURIComponent(symbol)}`,
                              { cache: "no-store" });
        if (!r.ok) return;
        const meta = await r.json();
        const prec = meta.precision ?? 2;
        setPriceFormat({ type: "price", precision: prec, minMove: Math.pow(10, -prec) });
    } catch (e) {
        console.warn("[symbol] price format failed:", e);
    }
}

export function value() { return el().value; }
