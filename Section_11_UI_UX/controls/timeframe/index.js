// CONTROL: timeframe dropdown + favorite buttons.
export const name = "timeframe";
const intervalEl = () => document.getElementById("interval");
const buttonsEl  = () => document.getElementById("tf-buttons");
let uiConfig = {
    timeframes: {
        all: ["1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"],
        favorites: ["1m","5m","15m","1h","4h","1d"],
    }
};

async function loadConfig() {
    try {
        const r = await fetch("/api/ui_config", { cache: "no-store" });
        if (r.ok) {
            const d = await r.json();
            if (d && d.timeframes) uiConfig = d;
        }
    } catch (e) { console.warn("[tf] config load failed:", e); }
}

async function saveConfig() {
    try {
        await fetch("/api/ui_config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ timeframes: uiConfig.timeframes }),
        });
    } catch (e) { console.error("[tf] save failed:", e); }
}

function renderButtons() {
    const wrap = buttonsEl();
    wrap.innerHTML = "";
    const current = intervalEl().value;
    for (const tf of uiConfig.timeframes.favorites) {
        const btn = document.createElement("button");
        btn.textContent = tf;
        if (tf === current) btn.classList.add("active");
        btn.addEventListener("click", () => {
            intervalEl().value = tf;
            intervalEl().dispatchEvent(new Event("change"));
        });
        btn.addEventListener("contextmenu", (ev) => {
            ev.preventDefault();
            toggleFavorite(tf);
        });
        wrap.appendChild(btn);
    }
}

async function toggleFavorite(tf) {
    if (!tf) return;
    const favs = uiConfig.timeframes.favorites;
    const i = favs.indexOf(tf);
    if (i === -1) favs.push(tf); else favs.splice(i, 1);
    await saveConfig();
    renderButtons();
}

export async function mount() {
    await loadConfig();
    const sel = intervalEl();
    sel.innerHTML = "";
    for (const tf of uiConfig.timeframes.all) {
        const opt = document.createElement("option");
        opt.value = tf; opt.textContent = tf;
        sel.appendChild(opt);
    }
    if (uiConfig.timeframes.all.includes("15m")) sel.value = "15m";
    sel.addEventListener("contextmenu", (ev) => {
        ev.preventDefault();
        toggleFavorite(sel.value);
    });
    renderButtons();
}

export function value() { return intervalEl().value; }
export function refreshButtons() { renderButtons(); }
