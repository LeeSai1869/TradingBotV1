export const TOOLS={line:2,rectangle:2,horizontal:1,retracement:2,extension:3};
export const RETRACEMENTS=[0,.236,.382,.5,.618,.786,1];
export const EXTENSIONS=[0,.618,1,1.272,1.618,2,2.618];
export function fibLevels(type,points){
    const [a,b,c]=points;
    return (type==='extension'?EXTENSIONS:RETRACEMENTS).map(ratio=>({ratio,
        price:type==='extension'?c.price+(b.price-a.price)*ratio:b.price+(a.price-b.price)*ratio}));
}
export function normalizeDrawings(value){
    return Array.isArray(value)?value.filter(d=>TOOLS[d?.type] && Array.isArray(d.anchors) && d.anchors.length===TOOLS[d.type] &&
        d.anchors.every(a=>a && Number.isFinite(a.time) && Number.isFinite(a.offset) && Math.abs(a.offset)<10000 && Number.isFinite(a.price)))
        .slice(-500).map(d=>({type:d.type,anchors:d.anchors.map(a=>({time:a.time,offset:a.offset,price:a.price}))})):[];
}
