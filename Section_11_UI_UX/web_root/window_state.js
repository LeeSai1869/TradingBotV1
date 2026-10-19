// Preserve the same candle positions when a bounded window changes.
export function logicalShift(previous, next) {
    const indices = new Map(next.map((row, index) => [row.time, index]));
    for (let index = 0; index < previous.length; index++) {
        const nextIndex = indices.get(previous[index].time);
        if (nextIndex !== undefined) return nextIndex - index;
    }
    return 0;
}
