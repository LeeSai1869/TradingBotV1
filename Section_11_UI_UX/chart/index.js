// ============================================================
// CANVAS — the single Lightweight Charts instance.
// Created once. Visuals attach their series/lines to it.
// ============================================================

const Canvas = {
    chart: null,
    container: null,

    init(container) {
        if (this.chart) return this.chart;
        this.container = container;
        this.chart = LightweightCharts.createChart(container, {
            layout: {
                background: { type: "solid", color: "transparent" },
                textColor: "#CCCCCC",
            },
            grid: { vertLines: { color: "#222222" }, horzLines: { color: "#222222" } },
            rightPriceScale: { borderColor: "#444444" },
            timeScale: { borderColor: "#444444", timeVisible: true, secondsVisible: false },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            attributionLogo: true,
        });

        // Resize handling.
        const resize = () => {
            this.chart.resize(container.clientWidth, container.clientHeight);
        };
        this.resizeObserver = new ResizeObserver(resize);
        this.resizeObserver.observe(container);
        window.addEventListener("resize", resize);
        resize();

        return this.chart;
    },
};

window.Canvas = Canvas;
