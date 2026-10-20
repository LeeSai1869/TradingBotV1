export const INTERVALS = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h','1d','3d','1w','1M'];
export const POSITIONS = ['top-left','top-right','bottom-left','bottom-right'];
export const FONTS = {system:'System', monospace:'Monospace', serif:'Serif'};
export const DEFAULT_STYLE = {fontSize:11,fontFamily:'system',textColor:'#e3e9f2',bold:false,
    borderColor:'#73849a',borderWidth:1,borderStyle:'solid',padding:6,showDates:false};
export const DEFAULT_HUD = {visible: true, position: 'top-left', symbol: '', style:DEFAULT_STYLE, size:{width:null,height:null}, intervals: ['5m','15m','1h','4h'],
    fields: ['client.close','features.rsi','features.adx','features.di_plus','features.di_minus','features.ema50']};
export function normalizeHud(value = {}) {
    const unique = (list, fallback, allowed, max) => {
        const items = Array.isArray(list) ? [...new Set(list.filter(allowed))].slice(0,max) : [];
        return items.length ? items : [...fallback];
    };
    const number = (v,fallback,min,max) => typeof v==='number' && Number.isFinite(v) ? Math.max(min,Math.min(max,v)) : fallback;
    const color = (v,fallback) => typeof v==='string' && /^#[0-9a-f]{6}$/i.test(v) ? v : fallback;
    const style=value?.style || {}, size=value?.size || {};
    return {style:{fontSize:number(style.fontSize,11,9,24),fontFamily:Object.hasOwn(FONTS,style.fontFamily)?style.fontFamily:'system',
            textColor:color(style.textColor,DEFAULT_STYLE.textColor),bold:style.bold===true,
            borderColor:color(style.borderColor,DEFAULT_STYLE.borderColor),borderWidth:number(style.borderWidth,1,0,4),
            borderStyle:['solid','dashed','dotted'].includes(style.borderStyle)?style.borderStyle:'solid',
            padding:number(style.padding,6,2,16),showDates:style.showDates===true},
        size:{width:number(size.width,null,180,2000),height:number(size.height,null,100,1400)},
        visible: typeof value?.visible === 'boolean' ? value.visible : true,
        position: POSITIONS.includes(value?.position) ? value.position : 'top-left',
        symbol: value?.symbol === 'BTCUSDT' ? 'BTCUSDT' : '',
        intervals: unique(value?.intervals,DEFAULT_HUD.intervals,x=>INTERVALS.includes(x),8),
        fields: unique(value?.fields,DEFAULT_HUD.fields,x=>typeof x==='string' && /^(client|features|adcn)\.[a-z0-9_]+$/.test(x),20)};
}
