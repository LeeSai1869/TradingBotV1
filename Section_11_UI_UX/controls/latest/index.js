// CONTROL: return to the newest candle without clearing visited history.
export const name = "latest";
let button = null;
let onClick = null;

export function mount() {
    if (button) return;
    button = document.createElement("button");
    button.id = "latest-candle-button";
    button.type = "button";
    button.title = "Go to latest candle";
    button.setAttribute("aria-label", "Go to latest candle");
    button.hidden = true;
    button.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m6 6 6 6-6 6m7-12 6 6-6 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    button.addEventListener("click", () => onClick?.());
    document.getElementById("chart").appendChild(button);
}

export function bind(fn) { onClick = fn; }

export function update(chart, cache) {
    if (!button) return;
    const range = chart.timeScale().getVisibleLogicalRange();
    const last = cache.renderBars.length - 1;
    const latestVisible = range && range.from <= last && range.to >= last - 0.5;
    button.hidden = cache.loading || last < 0 || !!latestVisible;
    button.style.right = `${chart.priceScale("right").width() + 12}px`;
}
