export const INTERVALS = ['1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h','1d','3d','1w','1M'];
export const POSITIONS = ['top-left','top-right','bottom-left','bottom-right'];
export const DEFAULT_HUD = {visible: true, position: 'top-left', symbol: '', intervals: ['5m','15m','1h','4h'],
    fields: ['client.close','features.rsi','features.adx','features.di_plus','features.di_minus','features.ema50']};
export function normalizeHud(value = {}) {
    const unique = (list, fallback, allowed, max) => {
        const items = Array.isArray(list) ? [...new Set(list.filter(allowed))].slice(0,max) : [];
        return items.length ? items : [...fallback];
    };
    return {visible: typeof value?.visible === 'boolean' ? value.visible : true,
        position: POSITIONS.includes(value?.position) ? value.position : 'top-left',
        symbol: typeof value?.symbol === 'string' && /^[A-Z0-9]{2,30}$/.test(value.symbol) ? value.symbol : '',
        intervals: unique(value?.intervals,DEFAULT_HUD.intervals,x=>INTERVALS.includes(x),8),
        fields: unique(value?.fields,DEFAULT_HUD.fields,x=>typeof x==='string' && /^(client|features|adcn)\.[a-z0-9_]+$/.test(x),20)};
}
