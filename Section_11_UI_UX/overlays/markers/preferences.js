export const SOUNDS=['none','chime','bell','alarm'];
export function normalizeMomentum(value={}) {
    const result={};
    for(const side of ['buy','sell'])result[side]=SOUNDS.includes(value?.[side])?value[side]:'none';
    const volume=Number(value?.volume??0.35);
    result.volume=Number.isFinite(volume)?Math.min(1,Math.max(0,volume)):0.35;
    return result;
}
export function closedSignals(bars,styles={},visible=true) {
    if(!visible)return [];
    return bars.flatMap(bar=>{
        if(bar.provisional)return [];
        const row=bar.momentum??(bar.adcn?.trigger==='DI_TURNING_POINT_V3'?bar.adcn:null);
        const side=row?.signal_type?.toLowerCase();
        if(!['buy','sell'].includes(side)||styles[`momentum_${side}`]?.visible===false)return [];
        return [{bar,side}];
    });
}
// Arm on entry into a symbol/timeframe; never replay history or changed settings.
export class SignalCursor {
    reset(data,now=Date.now()) {
        this.key=`${data.symbol}|${data.timeframe}`;
        this.started=now;this.seen=new Set();
    }
    observe(data,signals,now=Date.now()) {
        const key=`${data.symbol}|${data.timeframe}`;
        if(key!==this.key)this.reset(data,now);
        const fresh=[];
        for(const {bar,side} of signals) {
            const id=`${bar.open_time}|${side}`;
            if(this.seen.has(id))continue;
            this.seen.add(id);
            const closed=bar.client?.close_time;
            if(Number.isFinite(closed)&&closed>=this.started&&closed<now)fresh.push(side);
        }
        return fresh;
    }
}
