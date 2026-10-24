// Each output owns its presentation. This catalog also drives the settings rows.
export const FEATURE_STYLES = {
    'Momentum Indicator': {connected:true,outputs:[
        ['momentum_buy','BUY','#26a69a','marker'],['momentum_sell','SELL','#ef5350','marker'],
    ]},
    'Support / Resistance': { connected: true, outputs: [
        ['support_zones','Support zones','#26a69a','zone'],['resistance_zones','Resistance zones','#ef5350','zone'],
        ['inst_support_zones','Institutional support','#38bdf8','zone'],['inst_resistance_zones','Institutional resistance','#f59e0b','zone'],
    ] },
    FVG: { connected: true, outputs: [
        ['bull_fvg_zones','Bullish FVG','#26a69a','zone'],['bear_fvg_zones','Bearish FVG','#ef5350','zone'],
        ...['4h','1d','1w'].flatMap(tf=>[[`bull_fvg_${tf}_zones`,`${tf.toUpperCase()} bullish FVG`,'#26a69a','zone'],[`bear_fvg_${tf}_zones`,`${tf.toUpperCase()} bearish FVG`,'#ef5350','zone']]),
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
    'Volume Profile': { connected: true, outputs: [
        ['vp_poc','Point of control (POC)','#f5c542'],
        ['vp_va_high','Value area high (VAH)','#38bdf8'],['vp_va_low','Value area low (VAL)','#38bdf8'],
        ['vp_histogram','Volume by price','#748298','profile'],
        ['vp_hvn_nodes','High-volume nodes','#26a69a','profile'],
        ['vp_lvn_nodes','Low-volume nodes','#ef5350','profile'],
    ] },
    VWAP: { connected: true, outputs: [
        ["vwap", "VWAP", "#f5c542"], ["vwap_upper1", "Upper band 1", "#26a69a"],
        ["vwap_upper2", "Upper band 2", "#60ab64"], ["vwap_lower1", "Lower band 1", "#ef5350"],
        ["vwap_lower2", "Lower band 2", "#e747ae"],
    ] },
};

export function normalizeStyles(value = {}) {
    const result = {};
    for (const feature of Object.values(FEATURE_STYLES)) {
        for (const [key, , color, presentation] of feature.outputs) {
            const legacy=key==='vp_hvn_nodes'?(value?.vp_hvn_high?.visible?value.vp_hvn_high:value?.vp_hvn_low||value?.vp_hvn_high):key==='vp_lvn_nodes'?(value?.vp_lvn_high?.visible?value.vp_lvn_high:value?.vp_lvn_low||value?.vp_lvn_high):null;
            const input = value?.[key] || legacy || {};
            result[key] = {
                visible: typeof input.visible === "boolean" ? input.visible : ["ema50","momentum_buy","momentum_sell"].includes(key),
                color: /^#[0-9a-f]{6}$/i.test(input.color) ? input.color : color,
                width: [1,2,3,4].includes(input.width) ? input.width : 2,
                style: (presentation==='zone'?[0,1,2,3]:[0,1,2]).includes(input.style) ? input.style : 0,
            };
            if(['zone','profile'].includes(presentation))result[key].opacity=Number.isFinite(input.opacity)?Math.max(0,Math.min(100,input.opacity)):(presentation==='profile'?65:20);
            if(key==='vp_histogram'){
                result[key].lengthPercent=Number.isFinite(input.lengthPercent)?Math.max(10,Math.min(80,input.lengthPercent)):45;
            }
            if(key.startsWith('momentum_')) {
                result[key].shape=['arrowUp','arrowDown','circle','square'].includes(input.shape)?input.shape:(key==='momentum_buy'?'arrowUp':'arrowDown');
                result[key].label=typeof input.label==='boolean'?input.label:true;
            }
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
