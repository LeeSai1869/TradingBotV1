// ============================================================
// CONTROL: autoscale button ("A").
//
// Self-contained: creates its own DOM, applies its own styles,
// wires its own behavior. The composer is the only file that
// knows this control exists.
//
// Placement (TradingView-style):
//   - sits inside the price-axis column, above the time axis
//   - hidden by default
//   - fades in when the mouse is near the right edge of the chart
//
// Behavior:
//   - Click -> force the right price scale back to autoscale.
//   - Highlighted when autoscale is currently on.
// ============================================================

export const name = "autoscale";

const BTN_ID = "autoscale-button";
let _btn = null;
let _poll = null;

export function mount() {
    if (_btn) return;

    const host = document.getElementById("chart");
    if (!host) {
        console.warn("[autoscale] #chart not found");
        return;
    }

    if (getComputedStyle(host).position === "static") {
        host.style.position = "relative";
    }

    _btn = document.createElement("button");
    _btn.id = BTN_ID;
    _btn.type = "button";
    _btn.title = "Auto (fits data to screen)";
    _btn.textContent = "A";

    Object.assign(_btn.style, {
        position: "absolute",
        right: "8px",
        bottom: "34px",
        width: "28px",
        height: "28px",
        padding: "0",
        background: "rgba(40, 40, 40, 0.85)",
        color: "#ccc",
        border: "1px solid #333",
        borderRadius: "4px",
        fontSize: "13px",
        fontWeight: "600",
        lineHeight: "1",
        cursor: "pointer",
        zIndex: "20",
        fontFamily: "-apple-system, sans-serif",
        opacity: "0",
        transition: "opacity 0.15s ease",
        pointerEvents: "none",
    });

    _btn.addEventListener("mouseenter", () => {
        _btn.style.background = "rgba(60, 60, 60, 0.95)";
        _btn.style.color = "#fff";
    });
    _btn.addEventListener("mouseleave", () => {
        _applyActiveStyle();
    });

    _btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        _forceAutoscale();
    });

    host.appendChild(_btn);

    // Fade the button in when the mouse is near the right edge of the chart.
    host.addEventListener("mousemove", (ev) => {
        const rect = host.getBoundingClientRect();
        const fromRight = rect.right - ev.clientX;
        _setVisible(fromRight < 80);
    });
    host.addEventListener("mouseleave", () => _setVisible(false));

    _applyActiveStyle();

    if (_poll) clearInterval(_poll);
    _poll = setInterval(_applyActiveStyle, 250);
}

function _setVisible(on) {
    if (!_btn) return;
    if (on) {
        _btn.style.opacity = "1";
        _btn.style.pointerEvents = "auto";
    } else {
        _btn.style.opacity = "0";
        _btn.style.pointerEvents = "none";
    }
}

function _forceAutoscale() {
    const chart = window.Canvas && Canvas.chart;
    if (!chart || !chart.priceScale) return;
    try {
        chart.priceScale("right").applyOptions({ autoScale: true });
    } catch (e) { /* ignore */ }
    _applyActiveStyle();
}

function _applyActiveStyle() {
    if (!_btn) return;
    const chart = window.Canvas && Canvas.chart;
    if (!chart || !chart.priceScale) return;

    let auto = false;
    try {
        const opts = chart.priceScale("right").options();
        auto = !!(opts && opts.autoScale);
    } catch (e) { /* ignore */ }

    if (auto) {
        _btn.style.background = "#2a3b55";
        _btn.style.color = "#fff";
        _btn.style.borderColor = "#4a6a99";
    } else {
        _btn.style.background = "rgba(40, 40, 40, 0.85)";
        _btn.style.color = "#ccc";
        _btn.style.borderColor = "#333";
    }
}
