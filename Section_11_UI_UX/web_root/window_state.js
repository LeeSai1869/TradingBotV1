// Preserve the same candle positions when a bounded window changes.
export function readableRange(length,width,timeframe){
    const maximum = timeframe === '5m' ? 120 : 200;
    const count = Number.isFinite(width) && width > 0
        ? Math.max(30, Math.min(maximum, Math.floor(width / 6))) : maximum;
    return {from:Math.max(0,length-count),to:length+7};
}

export function logicalShift(previous, next) {
    const indices = new Map(next.map((row, index) => [row.time, index]));
    for (let index = 0; index < previous.length; index++) {
        const nextIndex = indices.get(previous[index].time);
        if (nextIndex !== undefined) return nextIndex - index;
    }
    return 0;
}
