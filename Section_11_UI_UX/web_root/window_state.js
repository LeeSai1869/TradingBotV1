// Preserve the same candle positions when a bounded window changes.
export function readableRange(length,width){
    // Fresh datasets reset to 200 candles; narrow plots keep thicker bodies.
    const count=Number.isFinite(width)&&width>0?Math.max(30,Math.min(200,Math.floor(width/6))):200;
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
