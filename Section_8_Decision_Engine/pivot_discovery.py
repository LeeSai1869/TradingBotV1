"""Retrospective native-pivot labels versus context-matched candle controls."""
from bisect import bisect_right, bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timezone
import math

import numpy as np

from .strategy_analyzer import FRAMES, number

FEATURES = '''di_plus di_minus di_absolute_spread adx rsi rsi_change natr_pct
efficiency_ratio relative_volume volume_ratio atr_ma_ratio atr_change candle_range_atr
displacement_atr body_percent close_location ema50_slope_atr ema200_slope_atr
bb_width_percentile bb_width_change_fraction positive_return_fraction negative_return_fraction
lower_wick_fraction upper_wick_fraction close_position close_to_ema50_pct close_to_ema200_pct
return_1_bar_pct return_3_bar_pct return_12_bar_pct spread_peak_drop'''.split()


def context(row, source=None):
    result = []
    for engine, names in [('REGIME', ('primary', 'direction')), ('TREND', ('direction',))]:
        p = row.get('context', {}).get(engine, {})
        if not p and source is not None:
            p = source.get('engine_history', {}).get(source['timeframe'] + ':' + engine, {}).get('results', {}).get(str(row['open_time']), {})
        c = p.get('classification') or {}
        result.extend(c.get(name, 'UNKNOWN') if p.get('data_quality') in ('VALID', 'PARTIAL') else 'UNKNOWN' for name in names)
    return tuple(result)


class Dataset:
    def __init__(self, source):
        from .pivot_candle_source import unpack
        source = unpack(source)
        self.source, self.rows = source, source['candles']
        self.step = FRAMES[source['timeframe']] or (self.rows[-1]['close_time']+1-self.rows[-1]['open_time'])
        self.times = [r['open_time'] for r in self.rows]
        self.positions = {t: i for i, t in enumerate(self.times)}
        self.contexts = [context(r, source) for r in self.rows]
        self.years = [datetime.fromtimestamp(t / 1000, timezone.utc).year for t in self.times]
        gap = [i > 0 and self.rows[i-1]['close_time'] + 1 != r['open_time'] for i, r in enumerate(self.rows)]
        self.gaps = np.cumsum(gap)
        raw = source.get('native_pivots')
        if raw is None:
            raw = [c['pivot'] for c in source.get('pivots', [])]
        self.events, self.invalid_labels = [], 0
        for p in sorted(raw, key=lambda p: (p['origin_time'], p['known_time'], p['id'])):
            i = self.positions.get(p['origin_time'])
            name = 'low' if p.get('type') == 'PIVOT_LOW' else 'high' if p.get('type') == 'PIVOT_HIGH' else None
            if (i is None or not name or not number(p.get('price')) or p['price'] <= 0
                    or p['known_time'] > source['observed_as_of'] or p['known_time'] <= self.rows[i]['close_time']
                    or not math.isclose(self.rows[i][name], p['price'], rel_tol=1e-10, abs_tol=1e-10)):
                self.invalid_labels += 1
                continue
            self.events.append(p)
        by_side = {s: [p for p in self.events if p['type'] == s] for s in ('PIVOT_LOW', 'PIVOT_HIGH')}
        times = {s: [p['origin_time'] for p in ps] for s, ps in by_side.items()}
        self.cases = []
        for p in self.events:
            opposite = 'PIVOT_HIGH' if p['type'] == 'PIVOT_LOW' else 'PIVOT_LOW'
            at = bisect_right(times[opposite], p['origin_time'])
            q = by_side[opposite][at] if at < len(by_side[opposite]) else None
            i = self.positions[p['origin_time']]
            j = self.positions[q['origin_time']] if q else None
            complete = j is not None and self.gaps[i] == self.gaps[j]
            move = (q['price'] / p['price'] - 1) * (100 if p['type'] == 'PIVOT_LOW' else -100) if complete else None
            self.cases.append(dict(id=p['id'], pivot=p, index=i, side='BUY' if p['type'] == 'PIVOT_LOW' else 'SELL',
                                   next_opposite=q, move_pct=move, status='GE_1' if move is not None and move >= 1 else 'LT_1' if move is not None else 'CENSORED'))
        self.native_indices = {c['index'] for c in self.cases}
        self.arrays = {}
        self.valid = np.array([bool(r.get('feature_valid')) and not r.get('features', {}).get('measurement_gap') for r in self.rows])

    def values(self, name):
        if name in self.arrays:
            return self.arrays[name]
        if hasattr(self.rows, 'column_index') and name in self.rows.column_index:
            v = np.array([float(v) if number(v) else np.nan for v in self.rows.feature(name)])
            v[~self.valid] = np.nan
            self.arrays[name] = v
            return v
        values = []
        for i, r in enumerate(self.rows):
            f, v = r.get('features', {}), None
            if not r.get('feature_valid') or f.get('measurement_gap'):
                values.append(np.nan)
                continue
            span = r['high'] - r['low']
            if name == 'di_absolute_spread':
                if all(number(f.get(k)) for k in ('di_plus', 'di_minus')):
                    v = abs(f['di_plus'] - f['di_minus'])
            elif name in ('lower_wick_fraction', 'upper_wick_fraction', 'close_position'):
                if span > 0:
                    v = ((min(r['open'], r['close']) - r['low']) if name == 'lower_wick_fraction' else
                         (r['high'] - max(r['open'], r['close'])) if name == 'upper_wick_fraction' else
                         (r['close'] - r['low'])) / span
            elif name in ('close_to_ema50_pct', 'close_to_ema200_pct'):
                ema = f.get(name.split('_')[2])
                if number(ema) and ema > 0:
                    v = 100 * (r['close'] / ema - 1)
            elif name.startswith('return_'):
                lag = int(name.split('_')[1])
                if i >= lag and self.gaps[i] == self.gaps[i-lag]:
                    v = 100 * (r['close'] / self.rows[i-lag]['close'] - 1)
            elif name == 'spread_peak_drop':
                if i >= 2 and self.gaps[i] == self.gaps[i-2]:
                    fs = [row['features'] for row in self.rows[i-2:i+1] if row.get('feature_valid') and not row['features'].get('measurement_gap')]
                    if len(fs) == 3 and all(number(g.get(k)) for g in fs for k in ('di_plus', 'di_minus')):
                        a, b, c = [abs(g['di_plus'] - g['di_minus']) for g in fs]
                        v = float(a < b > c)
            else:
                v = f.get(name)
            values.append(float(v) if number(v) else np.nan)
        out = self.arrays[name] = np.array(values, dtype=float)
        return out

    def included(self, i, regime, trend):
        primary, direction, td = self.contexts[i]
        return ((regime == 'ALL' or regime == 'BEARISH' and direction == 'BEARISH'
                 or regime == primary + '_' + direction)
                and (trend == 'ALL' or td == trend))

    def compare(self, *, side='BUY', control='ordinary', regime='ALL', trend='ALL', offset=0, page=0, since=None, until=None):
        if side not in ('BUY', 'SELL') or control not in ('ordinary', 'failed_pivots') or offset not in (-1, 0, 1):
            raise ValueError('Choose BUY/SELL, ordinary/failed_pivots and an offset of -1, 0 or 1')
        if regime not in ('ALL', 'BEARISH', 'TRENDING_BEARISH', 'TRANSITIONAL_BEARISH', 'TRENDING_BULLISH', 'TRANSITIONAL_BULLISH', 'RANGING_NEUTRAL') or trend not in ('ALL', 'BEARISH', 'BULLISH', 'NEUTRAL'):
            raise ValueError('Unsupported Trend/Regime filter')
        if any(v is not None and type(v) is not int for v in (since, until)) or since is not None and until is not None and since >= until:
            raise ValueError('Choose chronological integer millisecond period boundaries')
        in_window = lambda i: (since is None or self.times[i] >= since) and (until is None or self.times[i] < until)

        def observation(c):
            i, j = c['index'], c['index'] + offset
            return j if (0 <= j < len(self.rows) and self.gaps[j] == self.gaps[i]
                         and in_window(j) and self.included(j, regime, trend)) else None

        selected = [(c, observation(c)) for c in self.cases if c['side'] == side]
        selected = [(c, i) for c, i in selected if i is not None]
        target = sorted({i for c, i in selected if c['status'] == 'GE_1'})
        target_set = set(target)
        if control == 'ordinary':
            controls = [i for i in range(len(self.rows)) if i not in self.native_indices and i not in target_set and in_window(i) and self.included(i, regime, trend)]
        else:
            controls = sorted({i for c, i in selected if c['status'] == 'LT_1' and i not in target_set})
        # Equal numbers within each UTC year + exact Regime/Trend combination.
        # This avoids a pooled bull-year control overwhelming bear pivots.
        key = lambda i: (self.years[i], *self.contexts[i])
        targets_by, controls_by = defaultdict(list), defaultdict(list)
        for i in target:
            targets_by[key(i)].append(i)
        for i in controls:
            controls_by[key(i)].append(i)
        matched_t, matched_c = [], []
        for group, ts in sorted(targets_by.items()):
            cs = controls_by.get(group, [])
            n = min(len(ts), len(cs))
            if n:
                matched_t.extend(ts[int(k)] for k in np.linspace(0, len(ts)-1, n))
                matched_c.extend(cs[int(k)] for k in np.linspace(0, len(cs)-1, n))
        a, b = np.array(matched_t, dtype=int), np.array(matched_c, dtype=int)

        def stats(v):
            v = v[np.isfinite(v)]
            return dict(n=len(v), mean=float(np.mean(v)), p10=float(np.percentile(v, 10)), median=float(np.median(v)),
                        p90=float(np.percentile(v, 90)), sd=float(np.std(v))) if len(v) else dict(n=0, mean=None, p10=None, median=None, p90=None, sd=None)

        features = []
        for name in FEATURES:
            v = self.values(name)
            x, y = stats(v[a]), stats(v[b])
            sd = math.sqrt((x['sd']**2 + y['sd']**2) / 2) if min(x['n'], y['n']) else 0
            effect = (x['mean'] - y['mean']) / sd if sd > 0 and min(x['n'], y['n']) >= 30 else None
            features.append(dict(feature=name, pivot=x, control=y, standardized_difference=effect))
        features.sort(key=lambda f: abs(f['standardized_difference']) if f['standardized_difference'] is not None else -1, reverse=True)
        conditions = [('di_minus', '>=', 40), ('di_minus', '>=', 45), ('di_minus', '>=', 50),
                      ('di_absolute_spread', '>=', 40), ('spread_peak_drop', '>=', 1), ('rsi', '<=', 20),
                      ('lower_wick_fraction', '>=', .4), ('relative_volume', '>=', 1.5),
                      ('candle_range_atr', '>=', 1.5), ('return_3_bar_pct', '<=', -1),
                      ('close_to_ema50_pct', '<=', -1), ('natr_pct', '>=', .5)]
        overlap = []
        for name, op, threshold in conditions:
            v = self.values(name)
            def coverage(indices):
                vs = v[indices];vs = vs[np.isfinite(vs)]
                count = int(np.sum(vs >= threshold if op == '>=' else vs <= threshold))
                return dict(available=len(vs), count=count, pct=100 * count / len(vs) if len(vs) else None)
            overlap.append(dict(feature=name, op=op, threshold=threshold, pivot=coverage(a), control=coverage(b)))
        strata = Counter((c['status'], *self.contexts[i]) for c, i in selected)
        cases = [dict(c, observation_time=self.times[i], context=self.contexts[i]) for c, i in selected]
        cases.reverse()
        return dict(symbol=self.source['symbol'], timeframe=self.source['timeframe'], observed_as_of=self.source['observed_as_of'],
                    native_pivots=len(self.cases), invalid_labels=self.invalid_labels, since=since, until=until,
                    labels=dict(Counter(c['status'] for c, _ in selected)), total_candles=len(self.rows),
                    candidates=len(target), available_controls=len(controls), matched_pairs=len(a), unmatched_targets=len(target)-len(a),
                    features=features, overlap=overlap, strata=[dict(status=k[0], regime=k[1], regime_direction=k[2], trend=k[3], n=n) for k, n in sorted(strata.items())],
                    cases=cases[max(0, page)*25:max(0, page)*25+25], case_count=len(cases),
                    matching='1:1 deterministic evenly spaced samples within UTC year + exact same-timeframe Regime primary/direction + Trend direction. Unknown remains its own stratum.',
                    label='Native pivot origin to first strictly later opposite native pivot; endpoint move >=1%, contiguous candles only. Confirmed later pivots are historical reference labels.',
                    timing=f'Features at pivot offset {offset}; positive offsets describe later confirmation evidence, not the pivot candle itself.')

    def chart(self, center=None, feature='rsi'):
        if feature not in FEATURES:
            raise ValueError('Unsupported discovery feature')
        at = bisect_left(self.times, center) if center is not None else max(0, len(self.rows)-160)
        start, end = max(0, at-80), min(len(self.rows), at+160)
        v = self.values(feature)
        bars = [dict(time=r['open_time']//1000, open=r['open'], high=r['high'], low=r['low'], close=r['close'],
                     feature=float(v[i]) if np.isfinite(v[i]) else None, features=r['features'], context=self.contexts[i])
                for i, r in enumerate(self.rows[start:end], start)]
        markers = [dict(time=c['pivot']['origin_time']//1000, position='belowBar' if c['side']=='BUY' else 'aboveBar',
                        shape='arrowUp' if c['side']=='BUY' else 'arrowDown', color='#62ddb2' if c['side']=='BUY' else '#ff929c',
                        text=('L' if c['side']=='BUY' else 'H') + (' ≥1%' if c['status']=='GE_1' else ''), known_time=c['pivot']['known_time'])
                   for c in self.cases if start <= c['index'] < end]
        return dict(symbol=self.source['symbol'], timeframe=self.source['timeframe'], bars=bars, markers=markers,
                    feature=feature, center=self.times[min(at, len(self.times)-1)], first=self.times[0], last=self.times[-1], step=self.step)
