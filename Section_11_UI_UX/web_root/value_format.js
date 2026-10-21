// Display rounding only. Stored values and alert comparisons keep full precision.
const RAW_PRICES = new Set([
    'client.open', 'client.high', 'client.low', 'client.close',
    ...['c','o','h','l','c1','o1','h1','l1','current_price','prev_close'].map(key=>`features.${key}`),
]);

export const featurePriceFormat = Object.freeze({type:'price',precision:2,minMove:.01});

export function formatValue(value, field='') {
    if(value==null || (typeof value==='number' && !Number.isFinite(value)))return '—';
    if(typeof value!=='number')return String(value);
    return RAW_PRICES.has(field)?String(value):value.toFixed(2);
}
