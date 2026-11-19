const amount = new Intl.NumberFormat(undefined, {maximumFractionDigits: 2});

export function isUSDT(bar) {
    return (bar?.symbol ?? bar?.client?.symbol)?.endsWith('USDT') === true;
}

export function turnover(bar) {
    const candle = bar?.client;
    if (!candle) return null;
    if (Number.isFinite(candle.quote_volume)) return {value: candle.quote_volume, estimated: false};
    // Older rows retained only base volume. The OHLC average is a price estimate.
    const {open, high, low, close, volume} = candle;
    if (![open, high, low, close, volume].every(Number.isFinite)) return null;
    return {value: volume * (open + high + low + close) / 4, estimated: true};
}

export function formatTurnover(point) {
    return point ? `${point.estimated ? '≈' : ''}${amount.format(point.value)} USDT` : '—';
}

export const turnoverPriceFormat = {type: 'custom', minMove: .01, formatter: value => `${amount.format(value)} USDT`};
export const TURNOVER_AVERAGE_BARS = 20;
