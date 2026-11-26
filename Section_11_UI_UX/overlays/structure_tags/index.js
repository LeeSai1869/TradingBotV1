import {getSeries} from '../candles/index.js';

export const name = 'structure_tags';

const levels = [
    {side: 'high', direction: 1, protected: 'PH', confirmed: 'CSH', candidate: 'CPH'},
    {side: 'low', direction: -1, protected: 'PL', confirmed: 'CSL', candidate: 'CPL'},
];

export function structureTags(bars, styles) {
    if (!levels.some(({side}) => ['protected_' + side, 'latest_confirmed_pivot_' + side,
        'candidate_' + side + '_tag'].some(key => styles[key]?.visible))) return [];

    const tags = [];
    const candidates = new Map();
    const visibleTimes = new Set(bars.filter(bar => !bar.provisional).map(bar => bar.time));
    const add = (key, label, side, time, price) => {
        if (!styles[key]?.visible || !visibleTimes.has(time) || !Number.isFinite(price)) return;
        const tag = {label, side, time, price, color: styles[key].color};
        if (key.startsWith('candidate_')) candidates.set(side + ':' + time, tag);
        else tags.push(tag);
    };
    let previous = null;
    for (const bar of bars) {
        if (bar.provisional) continue;
        const f = bar.features ?? {};
        const prior = previous?.features;
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
            const candidate = 'candidate_pivot_' + side;
            if (previous && previous.client?.close_time + 1 === bar.open_time &&
                f.candidate_pivot === level.direction && prior?.candidate_pivot === level.direction &&
                f[candidate + '_time'] === previous.open_time && prior[candidate + '_time'] === previous.open_time) {
                add('candidate_' + side + '_tag', level.candidate, side, previous.time, f[candidate + '_price']);
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
                    candidates.delete(level.side + ':' + originTime);
                    add('latest_confirmed_pivot_' + level.side, level.confirmed, level.side, originTime, event.price);
                }
            }
        }
        previous = bar;
    }
    return [...tags, ...candidates.values()];
}

class StructureTags {
    attached({chart, series, requestUpdate}) {
        Object.assign(this, {chart, series, requestUpdate});
    }

    paneViews() { return [this]; }
    renderer() { return this; }
    zOrder() { return 'top'; }

    draw(target) {
        if (!this.tags?.length || !this.series.options().visible) return;
        const scale = this.chart.timeScale();
        const range = scale.getVisibleRange();
        target.useMediaCoordinateSpace(({context, mediaSize}) => {
            const positions = new Map();
            context.save();
            context.font = 'bold 11px sans-serif';
            context.textAlign = 'center';
            context.textBaseline = 'middle';
            for (const tag of this.tags) {
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
    primitive.requestUpdate?.();
}
