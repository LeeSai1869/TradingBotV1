import {getSeries} from '../candles/index.js';

export const name = 'structure_tags';

const levels = [
    {side: 'high', direction: 1, protected: 'PH', confirmed: 'SH', candidate: 'CH'},
    {side: 'low', direction: -1, protected: 'PL', confirmed: 'SL', candidate: 'CL'},
];

export function structureTags(bars, styles) {
    if (!levels.some(({side}) => ['protected_' + side, 'latest_confirmed_pivot_' + side,
        'candidate_' + side + '_tag'].some(key => styles[key]?.visible))) return [];

    const tags = [];
    const visibleTimes = new Set(bars.filter(bar => !bar.provisional).map(bar => bar.time));
    const add = (key, label, side, time, price) => {
        if (!styles[key]?.visible || !visibleTimes.has(time) || !Number.isFinite(price)) return;
        tags.push({label, side, time, price, color: styles[key].color});
    };
    let previous = null;
    for (const bar of bars) {
        if (bar.provisional) continue;
        const f = bar.features ?? {};
        const prior = previous?.features;
        const contiguous = previous?.client?.close_time + 1 === bar.open_time;
        for (const level of levels) {
            const {side} = level;
            const protectedKey = 'protected_' + side;
            const origin = f[protectedKey + '_bar'];
            if (prior && (f[protectedKey] !== prior[protectedKey] || origin !== prior[protectedKey + '_bar'])) {
                // Mark when the engine published the protected level.
                add(protectedKey, level.protected, side, bar.time, f[protectedKey]);
            }
            const confirmedKey = 'latest_confirmed_pivot_' + side;
            if (f.structure_events == null && prior && f[confirmedKey] !== prior[confirmedKey]) {
                // Older stored rows have the confirmed price but no origin event.
                add(confirmedKey, level.confirmed, side, bar.time, f[confirmedKey]);
            }

        }

        // Confirmed events retain the pivot's original candle and recognition time.
        if (typeof f.structure_events === 'string' && f.structure_events !== '[]') {
            let events;
            try { events = JSON.parse(f.structure_events); } catch { events = null; }
            for (const event of Array.isArray(events) ? events : []) {
                const level = levels.find(({side}) => event?.type === 'PIVOT_' + side.toUpperCase());
                if (level && event.confirmation_time === bar.open_time && Number.isFinite(event.origin_time)) {
                    const originTime = Math.floor(event.origin_time / 1000);
                    add('latest_confirmed_pivot_' + level.side, level.confirmed, level.side, originTime, event.price);
                }
            }
        }
        previous = bar;
    }
    // The active candidate can predate its activation after a delayed pivot
    // confirmation. Read its current identity, not a one-candle discovery window.
    const last=bars.filter(bar=>!bar.provisional).at(-1),f=last?.features??{};
    const candidate=levels.find(level=>level.direction===f.candidate_pivot);
    if(candidate){
        const root='candidate_pivot_'+candidate.side,origin=f[root+'_time'];
        if(Number.isFinite(origin)&&origin<last.open_time)add('candidate_'+candidate.side+'_tag',candidate.candidate,candidate.side,Math.floor(origin/1000),f[root+'_price']);
    }
    return tags;
}


export function structureGeometry(bars,styles){
    const closed=bars.filter(bar=>!bar.provisional),last=closed.at(-1);
    const protectedLevels=[],trendLines=[];
    if(!last)return {protectedLevels,trendLines};
    for(const {side,protected:label} of levels){
        const key='protected_'+side,price=last.features?.[key];
        if(styles[key]?.visible&&Number.isFinite(price))protectedLevels.push({key,label,side,price,color:styles[key].color});
        const lineKey='structure_'+side+'_trendline';
        if(!styles[lineKey]?.visible)continue;
        const points=new Map();
        for(const bar of closed){
            const f=bar.features??{};
            if(typeof f.structure_events==='string'){
                let events;try{events=JSON.parse(f.structure_events);}catch{events=[];}
                for(const e of Array.isArray(events)?events:[])if(e.type==='PIVOT_'+side.toUpperCase()&&e.confirmation_time===bar.open_time&&e.origin_time<e.confirmation_time&&Number.isFinite(e.price)){
                    points.set(Math.floor(e.origin_time/1000),e.price);
                }
            }else{
                const origin=f['nearest_swing_'+side+'_time'],price=f['nearest_swing_'+side];
                if(Number.isFinite(origin)&&origin<bar.open_time&&Number.isFinite(price))points.set(Math.floor(origin/1000),price);
            }
        }
        trendLines.push({key:lineKey,color:styles[lineKey].color,width:styles[lineKey].width||2,style:styles[lineKey].style||0,
            points:[...points].sort((a,b)=>a[0]-b[0]).map(([time,price])=>({time,price}))});
    }
    return {protectedLevels,trendLines};
}

class StructureTags {
    attached({chart, series, requestUpdate}) {
        Object.assign(this, {chart, series, requestUpdate});
    }

    paneViews() { return [this]; }
    renderer() { return this; }
    zOrder() { return 'top'; }

    draw(target) {
        if (!this.series.options().visible) return;
        const scale = this.chart.timeScale();
        const range = scale.getVisibleRange();
        target.useMediaCoordinateSpace(({context, mediaSize}) => {
            const positions = new Map();
            // Overlay primitives do not expand the price scale or shrink candles.
            for(const line of this.geometry?.trendLines??[]){
                context.save();context.strokeStyle=line.color;context.lineWidth=line.width;
                context.setLineDash(line.style===1?[2,3]:line.style===2?[6,4]:[]);context.beginPath();let connected=false;
                for(const p of line.points){const x=scale.timeToCoordinate(p.time),y=this.series.priceToCoordinate(p.price);
                    if(x===null||y===null){connected=false;continue;}
                    if(connected)context.lineTo(x,y);else context.moveTo(x,y);connected=true;
                }context.stroke();context.restore();
            }
            const used=[];
            for(const level of this.geometry?.protectedLevels??[]){
                const priceY=this.series.priceToCoordinate(level.price);if(priceY===null)continue;
                const outside=priceY<12||priceY>mediaSize.height-12;
                let y=outside?(priceY<0?18:mediaSize.height-54):Math.max(12,Math.min(mediaSize.height-12,priceY));
                while(used.some(p=>Math.abs(p-y)<17))y=y>mediaSize.height/2?y-18:y+18;
                used.push(y);context.save();context.strokeStyle=level.color;context.fillStyle=level.color;context.font='bold 11px sans-serif';
                if(!outside){context.setLineDash([5,4]);context.beginPath();context.moveTo(0,priceY);context.lineTo(mediaSize.width,priceY);context.stroke();}
                const text=level.label+' '+Number(level.price.toPrecision(8))+(outside?(priceY<0?' ↑':' ↓'):'');
                const width=context.measureText(text).width+10;context.fillStyle='#101820';context.fillRect(mediaSize.width-width,y-8,width,16);
                context.fillStyle=level.color;context.textAlign='right';context.textBaseline='middle';context.fillText(text,mediaSize.width-5,y);context.restore();
            }
            context.save();
            context.font = 'bold 11px sans-serif';
            context.textAlign = 'center';
            context.textBaseline = 'middle';
            for (const tag of this.tags??[]) {
                if (range && (tag.time < range.from || tag.time > range.to)) continue;
                const x = scale.timeToCoordinate(tag.time);
                const priceY = this.series.priceToCoordinate(tag.price);
                if (x === null || priceY === null || priceY < 0 || priceY > mediaSize.height) continue;
                const position = tag.time + ':' + tag.side;
                const previousY = positions.get(position);
                const above = tag.side === 'high';
                const y = above ? Math.min(priceY - 10, (previousY ?? Infinity) - 14)
                    : Math.max(priceY + 10, (previousY ?? -Infinity) + 14);
                positions.set(position, y);
                const width = context.measureText(tag.label).width + 8;
                const labelX = Math.max(width / 2, Math.min(mediaSize.width - width / 2, x));
                context.fillStyle = '#101820';
                context.fillRect(labelX - width / 2, y - 7, width, 14);
                context.fillStyle = tag.color;
                context.fillText(tag.label, labelX, y);
            }
            context.restore();
        });
    }
}

let primitive;

export function mount() {
    primitive = new StructureTags();
    getSeries().attachPrimitive(primitive);
}

export function update(chart, data) {
    primitive.tags = structureTags(data.bars ?? [], window.Composer.config.featureStyles ?? {});
    primitive.geometry = structureGeometry(data.bars ?? [],window.Composer.config.featureStyles ?? {});
    primitive.requestUpdate?.();
}
