"""Read-only audit of exact BTC 1h low -> immediate high pairs.

Uses the preserved row export, never opens production databases or changes rules.
All predicates are descriptive hypotheses, fixed here rather than optimized.
"""
import argparse
import bisect
import collections
import csv
import gzip
import hashlib
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

STEP = 3_600_000
PKT = ZoneInfo('Asia/Karachi')
OVERLAPS = {
    'activity_AND_extension_AND_adx': ('all', ('rvol_ge_1', 'extension_ge_1pct', 'adx_ge_25')),
    'pressure_AND_spread_AND_price_same_close': ('all', ('pressure_peak_now', 'spread_peak_now', 'close_recovering')),
    'activity_OR_extension': ('any', ('rvol_ge_1', 'extension_ge_1pct')),
    'pressure_OR_price_recovery': ('any', ('pressure_peak_now', 'close_recovering')),
}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def stamp(value):
    return datetime.fromtimestamp(value / 1000, PKT).isoformat()


def summary(values):
    values = sorted(v for v in values if finite(v))
    return dict(n=len(values), mean=statistics.mean(values) if values else None,
                median=statistics.median(values) if values else None,
                minimum=values[0] if values else None, maximum=values[-1] if values else None)


def full_candle(row):
    prices = [row[k] for k in ('open', 'high', 'low', 'close')]
    return (row['close_time'] + 1 - row['open_time'] == STEP
            and all(finite(v) and v > 0 for v in prices)
            and row['low'] <= min(prices) <= max(prices) <= row['high'])


def metrics(rows, index):
    row = rows[index]
    f = row['features'] if full_candle(row) and row['feature_valid'] and not row['features'].get('measurement_gap') else {}
    out = {k: f.get(k) for k in ('rsi', 'adx', 'relative_volume', 'di_plus', 'di_minus')}
    atr, ema = f.get('atr'), f.get('ema50')
    span = row['high'] - row['low']
    out.update(atr_pct=100 * atr / row['close'] if finite(atr) and atr > 0 else None,
               range_atr=span / atr if finite(atr) and atr > 0 else None,
               ema50_distance_abs_pct=100 * abs(row['close'] / ema - 1) if finite(ema) and ema > 0 else None,
               lower_wick_fraction=(min(row['open'], row['close']) - row['low']) / span if span > 0 else None,
               upper_wick_fraction=(row['high'] - max(row['open'], row['close'])) / span if span > 0 else None)
    plus, minus = f.get('di_plus'), f.get('di_minus')
    out['abs_di_spread'] = abs(plus - minus) if finite(plus) and finite(minus) else None
    return out


def condition_values(rows, index, side):
    row = rows[index]
    m = metrics(rows, index)
    f = row['features'] if row['feature_valid'] and not row['features'].get('measurement_gap') else {}
    prev = rows[index - 1] if index and full_candle(rows[index - 1]) and rows[index - 1]['close_time'] + 1 == row['open_time'] else None
    pf = prev['features'] if prev and prev['feature_valid'] and not prev['features'].get('measurement_gap') else {}

    def compare(a, b, predicate):
        return predicate(a, b) if finite(a) and finite(b) else None

    def threshold(key, value):
        return compare(m[key], value, lambda a, b: a >= b)

    def turn(key):
        if index < 2 or not prev or rows[index - 2]['close_time'] + 1 != prev['open_time']:
            return None
        trio = [r['features'].get(key) if full_candle(r) and r['feature_valid'] and not r['features'].get('measurement_gap') else None
                for r in rows[index - 2:index + 1]]
        return trio[0] < trio[1] > trio[2] if all(finite(v) for v in trio) else None

    if index >= 2 and prev and rows[index - 2]['close_time'] + 1 == prev['open_time']:
        spreads = [metrics(rows, j)['abs_di_spread'] for j in range(index - 2, index + 1)]
        spread_peak = spreads[0] < spreads[1] > spreads[2] if all(finite(v) for v in spreads) else None
    else:
        spread_peak = None
    pressure = 'di_minus' if side == 'LOW' else 'di_plus'
    peak = turn(pressure)
    out = dict(rvol_ge_1=threshold('relative_volume', 1), adx_ge_25=threshold('adx', 25),
               atr_pct_ge_1=threshold('atr_pct', 1), range_ge_1_atr=threshold('range_atr', 1),
               abs_spread_ge_10=threshold('abs_di_spread', 10),
               extension_ge_1pct=threshold('ema50_distance_abs_pct', 1),
               pressure_peak_now=peak, spread_peak_now=spread_peak,
               simultaneous_pressure_spread_peak=peak and spread_peak if peak is not None and spread_peak is not None else None,
               pressure_declining=compare(f.get(pressure), pf.get(pressure), lambda a, b: a < b))
    if side == 'LOW':
        out.update(rsi_below_30=compare(m['rsi'], 30, lambda a, b: a < b),
                   di_minus_dominant=compare(m['di_minus'], m['di_plus'], lambda a, b: a > b),
                   di_plus_rising=compare(m['di_plus'], pf.get('di_plus'), lambda a, b: a > b),
                   rsi_rising=compare(m['rsi'], pf.get('rsi'), lambda a, b: a > b),
                   green_candle=row['close'] > row['open'],
                   close_recovering=compare(row['close'], prev['close'] if prev else None, lambda a, b: a > b),
                   close_above_previous_high=compare(row['close'], prev['high'] if prev else None, lambda a, b: a > b),
                   close_below_ema50=compare(row['close'], f.get('ema50'), lambda a, b: a < b),
                   lower_wick_ge_40pct=threshold('lower_wick_fraction', .4))
        context = 'UNAVAILABLE'
        if prev and finite(pf.get('ema50')) and finite(pf.get('ema50_slope_atr')):
            context = ('UP_PROXY' if prev['close'] >= pf['ema50'] and pf['ema50_slope_atr'] > 0
                       else 'DOWN_PROXY' if prev['close'] < pf['ema50'] and pf['ema50_slope_atr'] < 0
                       else 'MIXED_PROXY')
        out['proxy_context'] = context
    else:
        out.update(rsi_above_70=compare(m['rsi'], 70, lambda a, b: a > b),
                   di_plus_dominant=compare(m['di_plus'], m['di_minus'], lambda a, b: a > b),
                   red_candle=row['close'] < row['open'],
                   close_weakening=compare(row['close'], prev['close'] if prev else None, lambda a, b: a < b),
                   upper_wick_ge_40pct=threshold('upper_wick_fraction', .4))
    return out


def frequency(cases, stage, condition):
    values = [(c, c[stage]['conditions'].get(condition)) for c in cases]
    known = [(c, v) for c, v in values if type(v) is bool]
    false_cases = [c['id'] for c, v in known if not v]
    return dict(total=len(cases), evaluable=len(known), missing=len(cases) - len(known),
                true=sum(v for _, v in known), false=len(false_cases),
                pct=100 * sum(v for _, v in known) / len(known) if known else None,
                counterexample_ids=false_cases[:3])


def pct(value):
    return f"{value:.2f}%" if value is not None else 'unavailable'


def analyze(packet):
    assert packet['symbol'] == 'BTCUSDT' and packet['timeframe'] == '1h'
    rows = packet['candles']
    indices = {r['open_time']: i for i, r in enumerate(rows)}
    assert len(indices) == len(rows)
    assert all(a['open_time'] < b['open_time'] for a, b in zip(rows, rows[1:]))
    highs = sorted((c['pivot']['origin_time'], c['id']) for c in packet['pivots'] if c['side'] == 'SELL_SIDE')
    high_times = [t for t, _ in highs]
    cases, mismatches, exclusions = [], [], []
    for source in packet['pivots']:
        if source['side'] != 'BUY_SIDE':
            continue
        low, high = source['pivot'], source['next_opposite']
        if high is None:
            exclusions.append(dict(id=source['id'], reason='NO_NEXT_HIGH'))
            continue
        i, j = indices[low['origin_time']], indices[high['origin_time']]
        assert j > i
        next_index = bisect.bisect_right(high_times, low['origin_time'])
        assert highs[next_index][1] == high['id'], 'Not the immediate next native high'
        assert low['price'] == rows[i]['low'] and high['price'] == rows[j]['high']
        gain = 100 * (high['price'] / low['price'] - 1)
        hit = high['price'] >= low['price'] * 1.01
        gap = any(rows[k - 1]['close_time'] + 1 != rows[k]['open_time'] for k in range(i + 1, j + 1))
        invalid_candle = any(not full_candle(r) for r in rows[i:j + 1])
        if hit != (source['origin']['status'] == 'HIT'):
            mismatches.append(dict(id=source['id'], low_pkt=stamp(low['origin_time']),
                                   pair_gain_pct=gain, older_touch_status=source['origin']['status'], raw_gap=gap))
        status = 'CENSORED_RAW_GAP' if gap else 'CENSORED_SHORT_OR_INVALID_CANDLE' if invalid_candle else 'HIT' if hit else 'NO_HIT'
        close = rows[i]['close']
        known = low['known_time']
        touch = next((r['close_time'] + 1 for r in rows[i + 1:j + 1] if r['high'] >= low['price'] * 1.01), None)
        item = dict(id=source['id'], high_id=high['id'], status=status,
                    low_pkt=stamp(low['origin_time']), high_pkt=stamp(high['origin_time']),
                    low=low['price'], high=high['price'], pair_gain_pct=gain, duration_hours=j - i,
                    year=datetime.fromtimestamp(low['origin_time'] / 1000, PKT).year,
                    native_low_known_pkt=stamp(known), native_high_known_pkt=stamp(high['known_time']),
                    origin_close_already_up_1pct=close >= low['price'] * 1.01,
                    target_touched_by_low_confirmation=touch is not None and touch <= known,
                    low_confirmation_delay_hours=(known - low['origin_time']) / STEP,
                    high_confirmation_delay_hours=(high['known_time'] - high['origin_time']) / STEP,
                    remaining_gross_from_origin_close_pct=100 * (high['price'] / close - 1),
                    remaining_gross_from_next_open_pct=100 * (high['price'] / rows[i + 1]['open'] - 1),
                    origin=dict(metrics=metrics(rows, i), conditions=condition_values(rows, i, 'LOW')),
                    prior=dict(metrics=metrics(rows, i - 1) if i else {}, conditions=condition_values(rows, i - 1, 'LOW') if i else {}),
                    endpoint=dict(metrics=metrics(rows, j), conditions=condition_values(rows, j, 'HIGH')))
        if i and (not full_candle(rows[i - 1]) or rows[i - 1]['close_time'] + 1 != rows[i]['open_time']):
            item['prior'] = dict(metrics={}, conditions={})
        cases.append(item)
    hits = [c for c in cases if c['status'] == 'HIT']
    nonhits = [c for c in cases if c['status'] == 'NO_HIT']
    complete = hits + nonhits
    out = dict(version='btc-1h-exact-spot-pair-audit-v1', source_id=packet['source_id'],
               observed_as_of_pkt=stamp(packet['observed_as_of']), first_candle_pkt=stamp(rows[0]['open_time']),
               candles=len(rows), lows=sum(c['side'] == 'BUY_SIDE' for c in packet['pivots']),
               outcomes=dict(collections.Counter(c['status'] for c in cases)), exclusions=exclusions,
               exact_pair_hit_pct=100 * len(hits) / len(complete),
               older_touch_label_disagreements=mismatches, profiles={}, predicates={}, context_groups=[],
               overlap_definitions=OVERLAPS, overlap_groups=[],
               timing=dict(hits=len(hits), origin_close_already_up_1pct=sum(c['origin_close_already_up_1pct'] for c in hits),
                           target_touched_by_low_confirmation=sum(c['target_touched_by_low_confirmation'] for c in hits),
                           low_confirmation_delay_hours=summary(c['low_confirmation_delay_hours'] for c in hits),
                           high_confirmation_delay_hours=summary(c['high_confirmation_delay_hours'] for c in hits),
                           remaining_gross_from_next_open_pct=summary(c['remaining_gross_from_next_open_pct'] for c in hits),
                           remaining_gross_from_next_open_ge_1pct=sum(c['remaining_gross_from_next_open_pct'] >= 1 for c in hits)),
               interpretation='Retrospective exact native pivot pairs. These are not trade returns or precision of a real-time signal. No threshold optimization, independent holdout, costs, stop fills or portfolio simulation.')
    for stage in ('prior', 'origin', 'endpoint'):
        out['profiles'][stage] = {k: dict(HIT=summary(c[stage]['metrics'].get(k) for c in hits),
                                               NO_HIT=summary(c[stage]['metrics'].get(k) for c in nonhits))
                                  for k in metrics(rows, 100)}
        names = sorted({k for c in complete for k, v in c[stage]['conditions'].items() if type(v) is bool})
        out['predicates'][stage] = {name: dict(HIT=frequency(hits, stage, name), NO_HIT=frequency(nonhits, stage, name)) for name in names}
    out['universal_tested_origin_predicates'] = [k for k, v in out['predicates']['origin'].items()
                                                if v['HIT']['missing'] == 0 and v['HIT']['false'] == 0]
    for name, (operator, names) in OVERLAPS.items():
        for context in ('ALL', 'UP_PROXY', 'DOWN_PROXY', 'MIXED_PROXY'):
            cohort = [c for c in complete if context == 'ALL' or c['origin']['conditions']['proxy_context'] == context]
            groups = {}
            for outcome in ('HIT', 'NO_HIT'):
                group = [c for c in cohort if c['status'] == outcome]
                known, matched = 0, 0
                for c in group:
                    values = [c['origin']['conditions'].get(k) for k in names]
                    # Three-valued AND/OR: unresolved inputs never become false or zero.
                    value = (False if False in values else None if None in values else True) if operator == 'all' else (True if True in values else None if None in values else False)
                    if value is not None:
                        known += 1
                        matched += value
                groups[outcome] = dict(total=len(group), evaluable=known, missing=len(group) - known,
                                       true=matched, pct=100 * matched / known if known else None)
            out['overlap_groups'].append(dict(name=name, context=context, **groups))
    # Fixed volatility bands and prior EMA context expose confounding; these are not S5 labels.
    for context in ('ALL', 'UP_PROXY', 'DOWN_PROXY', 'MIXED_PROXY', 'UNAVAILABLE'):
        for band, lower, upper in (('ALL', 0, math.inf), ('<0.5%', 0, .5), ('0.5-1%', .5, 1), ('1-2%', 1, 2), ('>=2%', 2, math.inf)):
            cohort = [c for c in complete if (context == 'ALL' or c['origin']['conditions']['proxy_context'] == context)
                      and (band == 'ALL' or finite(c['prior']['metrics'].get('atr_pct')) and lower <= c['prior']['metrics']['atr_pct'] < upper)]
            hs = [c for c in cohort if c['status'] == 'HIT']
            out['context_groups'].append(dict(context=context, prior_atr_band=band, n=len(cohort), hits=len(hs),
                                              hit_pct=100 * len(hs) / len(cohort) if cohort else None,
                                              rvol_ge_1=dict(HIT=frequency(hs, 'origin', 'rvol_ge_1'),
                                                             NO_HIT=frequency([c for c in cohort if c['status'] == 'NO_HIT'], 'origin', 'rvol_ge_1'))))
    out['annual'] = [dict(year=y, n=sum(c['year'] == y for c in complete),
                          hits=sum(c['year'] == y for c in hits)) for y in sorted({c['year'] for c in complete})]
    assert sum(out['outcomes'].values()) + len(exclusions) == out['lows']
    return out, cases


def write_readme(out, path):
    lines = ['# BTC 1h: exact spot upswing overlap audit', '',
             f"Frozen Binance BTCUSDT 1h source: {out['first_candle_pkt']} through {out['observed_as_of_pkt']}. This is historical research, not a live chart call.", '',
             '**Definition:** every native pivot LOW paired with the first later native pivot HIGH. A hit requires `100 * (high / low - 1) >= 1%`. No later high is substituted. Raw endpoint prices and first-opposite identities are checked for every pair. Pairs crossing missing, shortened or invalid raw candles are censored.', '',
             f"{out['candles']:,} candles; {out['lows']:,} lows; outcomes: {out['outcomes']}. Resolved exact-pair hit share: {out['exact_pair_hit_pct']:.2f}%. These are hindsight swing labels, not trading win rates.", '',
             f"The older touch-based label disagrees with the exact endpoint label in {len(out['older_touch_label_disagreements'])} pairs: {sum(v['raw_gap'] for v in out['older_touch_label_disagreements'])} cross raw gaps. The remaining contiguous disagreements touched +1% somewhere before the next high but that next native high itself was below +1%. All incomplete price paths are excluded from both comparison cohorts.", '',
             '## What is common?', '',
             'No tested origin-close predicate is true for every qualifying upswing with full measurement coverage. The tested universe is listed below; this does not prove that no other feature or combination could be universal. Trivial statements such as positive prices are not useful signals.', '',
             '| Condition at LOW origin close | >=1% pairs: true / evaluable | Smaller pairs: true / evaluable | Missing in >=1% pairs |',
             '|---|---:|---:|---:|']
    for name, values in out['predicates']['origin'].items():
        h, n = values['HIT'], values['NO_HIT']
        lines.append(f"| {name} | {h['true']:,}/{h['evaluable']:,} ({pct(h['pct'])}) | {n['true']:,}/{n['evaluable']:,} ({pct(n['pct'])}) | {h['missing']} |")
    lines += ['', '## Recurring measurements, not entry thresholds', '',
              'Means below use only the exact contiguous-pair cohorts. `atr_pct` is 100*ATR/close; RVOL is the stored current-inclusive volume ratio; extension is absolute close/EMA50 distance in percent. Missing measurements are excluded per field, with exact counts/ranges in statistics.json.', '',
              '| Measurement | Prior candle: >=1% / smaller | Origin close: >=1% / smaller |', '|---|---:|---:|']
    for name in ('atr_pct', 'relative_volume', 'range_atr', 'ema50_distance_abs_pct', 'abs_di_spread', 'adx', 'rsi'):
        p, v = out['profiles']['prior'][name], out['profiles']['origin'][name]
        lines.append(f"| {name} | {p['HIT']['mean']:.3f} / {p['NO_HIT']['mean']:.3f} | {v['HIT']['mean']:.3f} / {v['NO_HIT']['mean']:.3f} |")
    lines += ['', 'A fixed 1% target is easier in high volatility. These effects are descriptive, correlated and selected using future pivot membership; they cannot establish signal precision or independent votes.', '',
              '## Different starting conditions', '',
              'These are simple prior-close EMA50 position/slope proxies, explicitly separate from Section 5 Regime/Trend. UP requires prior close >= prior EMA50 and positive prior normalized EMA50 slope; DOWN uses close below and negative slope; remaining valid observations are MIXED. They are never substituted for missing independent engine history.', '',
              '| Prior context | Resolved pairs | >=1% pairs | Share |', '|---|---:|---:|---:|']
    for g in out['context_groups']:
        if g['prior_atr_band'] == 'ALL' and g['context'] != 'ALL':
            lines.append(f"| {g['context']} | {g['n']:,} | {g['hits']:,} | {pct(g['hit_pct'])} |")
    lines += ['', '| Prior ATR as % of close | Resolved pairs | >=1% pairs | Share |', '|---|---:|---:|---:|']
    for g in out['context_groups']:
        if g['context'] == 'ALL' and g['prior_atr_band'] != 'ALL':
            lines.append(f"| {g['prior_atr_band']} | {g['n']:,} | {g['hits']:,} | {pct(g['hit_pct'])} |")
    lines += ['', '## Fixed overlap checks', '',
              'These definitions were fixed in the audit script, without a threshold search. Tighter simultaneous conjunctions discard many qualifying swings. OR conditions cover more swings but also cover more smaller swings. Exact missingness and each context slice remain in statistics.json. All rows are still hindsight-selected native lows, so these percentages are not live-signal precision.', '',
              '| Origin-close overlap | >=1% pair coverage | Smaller-pair coverage |', '|---|---:|---:|']
    for g in out['overlap_groups']:
        if g['context'] == 'ALL':
            h, n = g['HIT'], g['NO_HIT']
            lines.append(f"| {g['name']} | {h['true']:,}/{h['evaluable']:,} ({pct(h['pct'])}) | {n['true']:,}/{n['evaluable']:,} ({pct(n['pct'])}) |")
    t = out['timing']
    lines += ['', '## Timing and spot execution', '',
              f"Among {t['hits']:,} exact qualifying pairs, {t['origin_close_already_up_1pct']:,} ({100*t['origin_close_already_up_1pct']/t['hits']:.2f}%) already closed >=1% above the low on the origin candle. Another event cannot be assigned to an earlier minute using the final hourly values.", '',
              f"The target touched on a subsequent candle by native-low confirmation in {t['target_touched_by_low_confirmation']:,} ({100*t['target_touched_by_low_confirmation']/t['hits']:.2f}%) qualifying pairs. Median recognition delay is {t['low_confirmation_delay_hours']['median']:.1f} hours from low candle OPEN and {t['high_confirmation_delay_hours']['median']:.1f} hours from high candle OPEN. The origin close itself is one hour after its open.", '',
              f"Only {t['remaining_gross_from_next_open_ge_1pct']:,}/{t['hits']:,} qualifying pairs still have >=1% gross distance from the next candle OPEN to the eventual immediate high. Even this assumes an ideal exit at that unknown future high; it is not achievable P&L or evidence of a real-time low entry.", '',
              'SELL evidence is measured at the immediate HIGH ending these same upswings, rather than treating every subsequent 1% drop as a short profit:', '',
              '| Condition at endpoint HIGH close | True / evaluable in qualifying upswings |', '|---|---:|']
    for name in ('di_plus_dominant', 'pressure_declining', 'pressure_peak_now', 'spread_peak_now', 'rsi_above_70', 'red_candle', 'close_weakening', 'rvol_ge_1'):
        g = out['predicates']['endpoint'][name]['HIT']
        lines.append(f"| {name} | {g['true']:,}/{g['evaluable']:,} ({pct(g['pct'])}) |")
    lines += ['', 'These are endpoint descriptions, not permission to sell at an unrecognized high. A live SELL needs causal price failure or an executable risk/target rule while holding BTC. A spot system stays in BTC or cash; it does not book short profit.', '',
              '## Files and reproduction', '',
              '- `statistics.json`: exact denominators, missingness, example counterexample IDs, contexts, timing and source hash.',
              '- `pairs.csv`: every pair, including failures and raw-gap exclusions, endpoint IDs/times and prices.',
              '- `INDICATOR_SPEC.md`: proposed spot state machine and Section 5 assessment.',
              '- `PROTOTYPE_RESULTS.md`: failed first causal BUY/SELL hypothesis, model costs and replay commands.',
              '- `section5_readiness.json`: separate read-only operational snapshot, if supplied.', '',
              '```sh', 'python3 research_reports/BTC_1h_spot_overlap/reproduce.py', '```', '',
              'No native or legacy structure labels become trading gates here. The preserved 2017–2026 export is an older feature generation; current source fixes and pending replay must be checked before transferring findings. Preserved engine history is sparse, so regime-conditioned overlap is not established. No thresholds were optimized, no independent holdout was tested, and no live rules, engine budgets, checkpoints or databases were changed.', '']
    path.write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('research_reports/BTC_1h_sequences/source_v1.json.gz'))
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    data = args.input.read_bytes()
    out, cases = analyze(json.loads(gzip.decompress(data)))
    out['source_file'] = str(args.input)
    out['source_sha256'] = hashlib.sha256(data).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'statistics.json').write_text(json.dumps(out, indent=2, allow_nan=False) + '\n')
    fields = [k for k in cases[0] if k not in ('origin', 'prior', 'endpoint')]
    with (args.output_dir / 'pairs.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: c[k] for k in fields} for c in cases)
    write_readme(out, args.output_dir / 'README.md')
    print(json.dumps(dict(outcomes=out['outcomes'], exact_pair_hit_pct=out['exact_pair_hit_pct'],
                          universal_tested_predicates=out['universal_tested_origin_predicates'],
                          source_sha256=out['source_sha256']), indent=2))


if __name__ == '__main__':
    main()
