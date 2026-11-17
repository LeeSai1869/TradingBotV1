"""Read-time ATR slopes from retained EMA windows, with explicit legacy fallback.

This module does not change writes or clear stored values. SQL readers install
the provider on their existing connection, so raw and feature reads share the
caller's SQLite snapshot. Missing provenance is not treated as a five-bar slope.
"""
import hashlib
import json
import math

FIELDS = {f'ema{p}_slope_atr': p for p in (50, 200, 300)}


def fingerprint(config):
    return hashlib.sha256(json.dumps(
        config, sort_keys=True, separators=(',', ':')
    ).encode()).hexdigest()


def known_lengths():
    from Section_4_Features.features.shared_measurements import DEFAULTS, validate
    from Section_4_Features.execution.components import desired_parameters
    parameters = desired_parameters()
    current = {key: parameters.get(key, value) for key, value in DEFAULTS.items()}
    validate(current)
    return {fingerprint(config): config['measurementSlopeLength']
            for config in (DEFAULTS, current)}


def finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def reconstruct(rows, lengths):
    """Return resolved fields; absent keys require retaining the stored value.

    Rows are chronological, ending at the requested candle. Each includes raw
    candle boundaries, feature provenance and retained EMA/ATR inputs.
    """
    if not rows:
        return {}
    current = rows[-1]
    if (current['formula_version'] != 3
            or current['measurement_version'] != 'shared-v1'):
        return {}
    length = lengths.get(current['measurement_config_id'])
    if length is None or current['close_time'] is None:
        return {}
    bars = current['measurement_contiguous_bars']
    if not finite(bars) or bars < 0 or int(bars) != bars:
        return {}
    empty = dict.fromkeys(FIELDS)
    if (not finite(current['close']) or current['close'] <= 0
            or not finite(current['atr']) or current['atr'] <= 0
            or bars <= length):
        return empty
    # Current missing EMAs are unconditionally unavailable, even if earlier
    # retained history is incomplete. Resolve other fields only with evidence.
    result = {field: None for field, period in FIELDS.items()
              if not finite(current[f'ema{period}'])}
    window = rows[-length-1:]
    if len(window) != length + 1:
        return result
    for offset, row in enumerate(window):
        if (row['formula_version'] != 3
                or row['measurement_version'] != 'shared-v1'
                or row['measurement_config_id'] != current['measurement_config_id']
                or row['measurement_contiguous_bars'] != bars - length + offset
                or row['close_time'] is None
                or not finite(row['close']) or row['close'] <= 0):
            return result
        if offset and window[offset-1]['close_time'] + 1 != row['open_time']:
            return result
    for field, period in FIELDS.items():
        name = f'ema{period}'
        result[field] = ((current[name] - window[0][name]) / current['atr']
                         if all(finite(row[name]) for row in window) else None)
    return result


def expression(field, prefix='f', *, preserve_legacy=True):
    """SQL projection; call install(conn) before using it on a raw connection."""
    stored = f'{prefix}."{field}"' if preserve_legacy else 'NULL'
    return (f'feature_atr_slope({prefix}.symbol,{prefix}.interval,'
            f'{prefix}.open_time,{FIELDS[field]},{stored}) AS "{field}"')


def read_values(conn, symbol, interval, timestamp, lengths):
    """Return only provably reconstructed fields, for readers and parity audits.

    The connection must have the raw store attached as ``raw``. An absent key
    means the original stored value is still required, including a stored null.
    """
    head = conn.execute(
        'SELECT formula_version,measurement_version,measurement_config_id '
        'FROM features WHERE symbol=? AND interval=? AND open_time=?',
        (symbol, interval, timestamp)
    ).fetchone()
    length = (lengths.get(head[2]) if head and head[0] == 3
              and head[1] == 'shared-v1' else None)
    if length is None:
        return {}
    columns = ['open_time', 'formula_version', 'measurement_version',
               'measurement_config_id', 'measurement_contiguous_bars',
               'atr', 'ema50', 'ema200', 'ema300', 'close_time', 'close']
    rows = conn.execute(
        'SELECT ' + ','.join('f.' + c for c in columns[:9]) +
        ',k.close_time,k.close FROM features f LEFT JOIN raw.klines k '
        'ON k.symbol=f.symbol AND k.interval=f.interval '
        'AND k.open_time=f.open_time WHERE f.symbol=? AND f.interval=? '
        'AND f.open_time<=? ORDER BY f.open_time DESC LIMIT ?',
        (symbol, interval, timestamp, length + 1)
    ).fetchall()
    return reconstruct([dict(zip(columns, row)) for row in reversed(rows)], lengths)


def install(conn, *, attach_raw=True):
    """Register a bounded, read-only provider; never open an independent snapshot."""
    databases = {row[1]: row[2] for row in conn.execute('PRAGMA database_list')}
    if 'raw' not in databases and attach_raw:
        from . import klines_store
        if klines_store.DB_PATH.is_file():
            conn.execute('ATTACH DATABASE ? AS raw', (
                klines_store.DB_PATH.resolve().as_uri() + '?mode=ro',
            ))
            databases['raw'] = str(klines_store.DB_PATH)
    has_raw = ('raw' in databases and conn.execute(
        "SELECT 1 FROM raw.sqlite_master WHERE type='table' AND name='klines'"
    ).fetchone() is not None)
    lengths = None
    cached_key = cached_result = None

    def resolve(symbol, interval, timestamp, period, stored):
        nonlocal lengths, cached_key, cached_result
        if symbol is None or timestamp is None or not has_raw:
            return stored
        if lengths is None:
            lengths = known_lengths()
        # Reuse the three projections for a row on read-only connections only.
        # Data-version checks also invalidate the result after external commits.
        # Disabling this cache after local writes avoids rollback stale reads.
        key = (symbol, interval, timestamp,
               conn.execute('PRAGMA main.data_version').fetchone()[0],
               conn.execute('PRAGMA raw.data_version').fetchone()[0])
        if cached_key != key or conn.total_changes:
            cached_key = key
            cached_result = read_values(conn, symbol, interval, timestamp, lengths)
        return cached_result.get(f'ema{period}_slope_atr', stored)

    conn.create_function('feature_atr_slope', 5, resolve)
