export const CANDLE_DEFAULTS={upColor:'#26a69a',downColor:'#ef5350',wickUpColor:'#26a69a',wickDownColor:'#ef5350',borderUpColor:'#26a69a',borderDownColor:'#ef5350',wickVisible:true,borderVisible:false};
export function normalizeCandleStyle(value={}){
    const result={...CANDLE_DEFAULTS};
    for(const key of Object.keys(result))if(typeof result[key]==='boolean'){
        if(typeof value?.[key]==='boolean')result[key]=value[key];
    }else if(/^#[a-f0-9]{6}$/i.test(value?.[key]))result[key]=value[key];
    return result;
}
