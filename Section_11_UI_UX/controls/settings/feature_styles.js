// Each output owns its presentation. This catalog also drives the settings rows.
export const FEATURE_STYLES = {
    'Support / Resistance': { connected: true, outputs: [
        ['support_zones','Support zones','#26a69a','zone'],['resistance_zones','Resistance zones','#ef5350','zone'],
        ['inst_support_zones','Institutional support','#38bdf8','zone'],['inst_resistance_zones','Institutional resistance','#f59e0b','zone'],
    ] },
    FVG: { connected: true, outputs: [
        ['bull_fvg_zones','Bullish FVG','#26a69a','zone'],['bear_fvg_zones','Bearish FVG','#ef5350','zone'],
    ] },
    EMA: { connected: true, outputs: [
        ["ema7", "EMA 7", "#f5c542"], ["ema25", "EMA 25", "#e747ae"],
        ["ema50", "EMA 50", "#ad83f5"], ["ema100", "EMA 100", "#60ab64"],
        ["ema200", "EMA 200", "#4b7bff"], ["ema300", "EMA 300", "#f18a35"],
    ] },
    WMA: { connected: true, outputs: [["wma50", "WMA 50", "#38bdf8"]] },
    RSI: { connected: true, outputs: [["rsi", "RSI", "#ad83f5"]] },
    ADX: { connected: true, outputs: [
        ["adx", "ADX", "#f5c542"],
    ] },
    DI: { connected: true, outputs: [
        ["di_plus", "+DI", "#26a69a"],
        ["di_minus", "−DI", "#ef5350"], ["di_spread", "DI spread", "#4b7bff"],
        ["di_direction", "DI direction", "#ad83f5"],
        ["di_dominance", "DI dominance", "#f59e0b"],
    ] },
    ATR: { connected: true, outputs: [["atr", "ATR", "#f18a35"], ["atr_ma", "ATR average", "#4b7bff"]] },
    Volume: { connected: true, outputs: [["volume", "Volume", "#26a69a", "histogram"], ["volume_ma", "Volume average", "#f5c542"]] },
    VWAP: { connected: true, outputs: [
        ["vwap", "VWAP", "#f5c542"], ["vwap_upper1", "Upper band 1", "#26a69a"],
        ["vwap_upper2", "Upper band 2", "#60ab64"], ["vwap_lower1", "Lower band 1", "#ef5350"],
        ["vwap_lower2", "Lower band 2", "#e747ae"],
    ] },
};

export function normalizeStyles(value = {}) {
    const result = {};
    for (const feature of Object.values(FEATURE_STYLES)) {
        for (const [key, , color] of feature.outputs) {
            const input = value?.[key] || {};
            result[key] = {
                visible: typeof input.visible === "boolean" ? input.visible : key === "ema50",
                color: /^#[0-9a-f]{6}$/i.test(input.color) ? input.color : color,
                width: [1,2,3,4].includes(input.width) ? input.width : 2,
                style: [0,1,2].includes(input.style) ? input.style : 0,
            };
        }
    }
    return result;
}

export function migrateStyles(value) {
    if (value?.outputs) return normalizeStyles(value.outputs);
    const migrated = normalizeStyles();
    if (!value || !Array.isArray(value.periods)) return migrated;
    for (const [key] of FEATURE_STYLES.EMA.outputs) {
        migrated[key] = { visible: value.periods.includes(Number(key.slice(3))),
            color: value.color, width: value.width, style: value.style };
    }
    return normalizeStyles(migrated);
}
