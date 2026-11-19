"""Freeze spot candles for pivot discovery and the strategy workspace, read-only."""

if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from Section_1_Global_Core import data_policy, pivot_research, regime_inputs
from Section_1_Global_Core.btc_hour_sequence_source import clean
from Section_1_Global_Core.memory_storage.Storage import engine_store
from Section_4_Features.execution.components import desired_parameters, catalog
from Section_5_Market_Regime.engines import structure, trend, regime

MODULES = {'STRUCTURE': structure, 'TREND': trend, 'REGIME': regime}
EXTRA = '''volume rsi prev_rsi rsi_change di_spread di_direction prev_di_plus prev_di_minus
atr atr_percent atr_ma_ratio atr_change relative_volume volume_ratio volume_ma
body_percent upper_wick lower_wick candle_range candle_range_atr close_location
change_percent displacement_atr ema300 ema50_distance_pct ema200_distance_pct
nearest_support nearest_resistance support_zone_low support_zone_high resistance_zone_low
resistance_zone_high nearest_buy_liquidity_price nearest_sell_liquidity_price
liquidity_high_distance liquidity_low_distance candidate_pivot candidate_pivot_high_price
candidate_pivot_high_time candidate_pivot_low_price candidate_pivot_low_time
vwap vwap_upper1 vwap_lower1 bb_upper bb_lower bb_width_percentile
distance_to_swing_high_pct distance_to_swing_low_pct'''.split()


def export(symbol, frame, output, *, until=None, progress=print):
    pivot_research.validate(symbol, frame)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frozen = output.with_name(output.name + '.measurements.partial.gz')
    partial = output.with_name(output.name + '.partial')
    now = int(time.time() * 1000)
    bound = min(now, until) if until is not None else now
    conn = regime_inputs.open_sources()
    try:
        required = set().union(*(set(m.FIELDS) for m in MODULES.values()))
        columns = {r[1] for r in conn.execute('PRAGMA table_xinfo(features)')}
        fields = tuple(sorted(required | (set(EXTRA) & columns)))
        feature_catalog = catalog()
        metadata_fields = tuple(f for f in fields if f not in feature_catalog.export_inverse
                                or feature_catalog.export_inverse[f] in feature_catalog.final)
        metadata = regime_inputs.source_metadata(conn, symbol, frame, 'initial', metadata_fields)
        cap = conn.execute('SELECT last_open_time FROM feature_engine_state WHERE symbol=? AND interval=?', (symbol, frame)).fetchone()[0]
        bound = min(bound, cap + pivot_research.DURATIONS[frame])
        parameters = desired_parameters()
        engines = {name: dict(version=m.VERSION, source_sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()) for name, m in MODULES.items()}
        signature = engine_store.digest(dict(metadata=metadata, engines=engines, fields=fields))
        identity = dict(venue='binance', market_type='spot', instrument_id=symbol, symbol=symbol,
                        timeframe=frame, dataset_generation=engine_store.digest(metadata))
        units = {k: v for m in MODULES.values() for k, v in m.UNITS.items()}
        units.update({k: 'research_only' for k in fields if k not in units})
        after = -1
        count = 0
        reason = ''
        conn.rollback()
        # Release the SQLite snapshot after EVERY page, before compression or
        # classifier work. Fixed cutoff and generation checks bind the pages.
        with gzip.open(frozen, 'wt') as out:
            while True:
                with data_policy.snapshot_guard(timeout=1):
                    conn.execute('BEGIN')
                    try:
                        if regime_inputs.source_metadata(conn, symbol, frame, 'initial', metadata_fields) != metadata:
                            raise ValueError('Feature generation/config changed while freezing; retry the export')
                        batch, reason = regime_inputs.project(conn, symbol, frame, after, 2048, identity, signature,
                                                              metadata, parameters, bound, fields, units)
                    finally:
                        conn.rollback()
                for s in batch:
                    out.write(json.dumps(clean(dict(open_time=s['candle_open_time'], close_time=s['candle_close_time'],
                                                   **s['candle'], features=s['features'])), separators=(',', ':'), allow_nan=False) + '\n')
                if batch:
                    after = batch[-1]['candle_open_time']
                    count += len(batch)
                if progress:
                    progress(dict(stage='freeze', symbol=symbol, timeframe=frame, candles=count, through=after, reason=reason))
                if reason or len(batch) < 2048:
                    break
    finally:
        conn.close()
    if not count:
        raise ValueError('No committed candles available: ' + reason)

    states = {name: None for name in MODULES}
    pivots = {}
    invalid_events = 0
    first = None
    stored_fields = [f for f in fields if f != 'structure_events']
    context_table, context_ids = [], {}
    header = dict(version='pivot-candle-source-v1', symbol=symbol, timeframe=frame, source_id=signature,
                  observed_as_of=bound, source_metadata=metadata, engines=engines, parameters=parameters,
                  exported_feature_columns=stored_fields,
                  missing_requested_features=sorted(set(EXTRA) - columns), stop_reason=reason,
                  provenance='Stored spot measurements; current Section 5 STRUCTURE -> TREND and REGIME replayed offline from the first stored candle. No production outputs written. Native pivots are reference labels only.')
    with gzip.open(frozen, 'rt') as stream, gzip.open(partial, 'wt') as out:
        out.write(json.dumps(header, separators=(',', ':'), allow_nan=False)[:-1] + ',"packed_candles":[')
        for i, line in enumerate(stream):
            row = json.loads(line)
            start, end, f = row['open_time'], row['close_time'], row['features']
            if first is None:
                first = start
            if f.get('structure_events_version') == 'structure-events-v1' and f.get('structure_event_status') == 'READY':
                for event in pivot_research.pivot_events(f.get('structure_events'), start, end):
                    pivots[event['id']] = event
            else:
                invalid_events += 1
            candle = {k: row[k] for k in ('open', 'high', 'low', 'close')}
            s = dict(identity=identity, candle_open_time=start, candle_close_time=end, as_of=end + 1,
                     computed_at=now, closed=True, candle=candle, features=f, units=units,
                     feature_parameters=parameters,
                     field_validity={k: 'VALID' if v is not None else 'UNAVAILABLE' for k, v in f.items()},
                     field_available_at={k: end + 1 for k in f}, input_signature=signature,
                     source_versions=metadata, quality_flags=['AVAILABILITY_RECONSTRUCTED'],
                     provenance_mode='HISTORICAL_RECONSTRUCTION')
            results = {}
            for name, module in MODULES.items():
                if name == 'TREND':
                    dep = results['STRUCTURE']
                    s['dependencies'] = {'STRUCTURE': dep}
                    s['dependency_refs'] = {'STRUCTURE': f'offline-structure:{start}'}
                    s['dependency_expectations'] = {'STRUCTURE': {k: dep[k] for k in ('engine_version', 'config_hash', 'input_signature')}}
                result, states[name] = module.evaluate(s, previous_state=states[name])
                results[name] = result
            refs = []
            for result in results.values():
                value = {k: result[k] for k in ('classification', 'data_quality', 'coverage')}
                key = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
                if key not in context_ids:
                    context_ids[key] = len(context_table)
                    context_table.append(value)
                refs.append(context_ids[key])
            packed = [start, end, *(row[k] for k in ('open', 'high', 'low', 'close')), f.get('volume'), [f.get(k) for k in stored_fields], refs]
            out.write((',' if i else '') + json.dumps(packed, separators=(',', ':'), allow_nan=False))
            if progress and (i + 1) % 10000 == 0:
                progress(dict(stage='offline_context', symbol=symbol, timeframe=frame, candles=i + 1, total=count))
        tail = dict(native_pivots=sorted(pivots.values(), key=lambda e: (e['origin_time'], e['known_time'], e['id'])),
                    coverage=dict(first=first, last=after, candles=count), invalid_event_rows=invalid_events,
                    engine_history={}, context_table=context_table)
        out.write('],' + json.dumps(tail, separators=(',', ':'), allow_nan=False)[1:])
    partial.replace(output)
    frozen.unlink()
    if progress:
        progress(dict(stage='complete', path=str(output.resolve()), candles=count, native_pivots=len(pivots)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--symbol', required=True)
    p.add_argument('--timeframe', choices=pivot_research.TIMEFRAMES, default='15m')
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    export(args.symbol.upper(), args.timeframe, args.output, progress=lambda v: print(json.dumps(v), flush=True))
