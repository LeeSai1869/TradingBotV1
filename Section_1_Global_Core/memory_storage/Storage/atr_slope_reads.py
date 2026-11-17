"""Read-time ATR slopes from retained EMA windows, with explicit legacy fallback.

SQL readers use their existing connection, so raw and feature reads share the
caller's SQLite snapshot. Missing provenance is not treated as a five-bar slope.
"""
import hashlib
import json
import math
from collections import deque
from contextlib import contextmanager

FIELDS = {f'ema{p}_slope_atr': p for p in (50, 200, 300)}


def fingerprint(config):
    return hashlib.sha256(json.dumps(
        config, sort_keys=True, separators=(',', ':')
    ).encode()).hexdigest()


def configurations(parameters=None):
    from Section_4_Features.features.shared_measurements import DEFAULTS, validate
    from Section_4_Features.execution.components import desired_parameters
    parameters = desired_parameters() if parameters is None else parameters
    current = {key: parameters.get(key, value) for key, value in DEFAULTS.items()}
    validate(current)
    return [dict(DEFAULTS), current]


def create_registry(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS feature_atr_slope_configs '
                 '(identity TEXT PRIMARY KEY, spec TEXT NOT NULL)')


def register_configurations(conn, parameters=None):
    """Persist exact configurations in the same transaction as retired values."""
    if not conn.in_transaction:
        raise RuntimeError('Configuration registration requires a write transaction')
    create_registry(conn)
    for config in configurations(parameters):
        conn.execute('INSERT OR IGNORE INTO feature_atr_slope_configs VALUES (?,?)',
                     (fingerprint(config), json.dumps(config,sort_keys=True,separators=(',',':'))))


def known_lengths(conn=None):
    from Section_4_Features.features.shared_measurements import DEFAULTS, validate
    result = {fingerprint(config): config['measurementSlopeLength']
              for config in configurations()}
    if conn is not None and conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='feature_atr_slope_configs'"
    ).fetchone():
        for identity, spec in conn.execute('SELECT identity,spec FROM feature_atr_slope_configs'):
            config = json.loads(spec)
            if not isinstance(config,dict) or set(config)!=set(DEFAULTS):
                raise ValueError('Invalid saved ATR slope configuration')
            validate(config)
            if fingerprint(config)!=identity:
                raise ValueError('ATR slope configuration fingerprint mismatch')
            result[identity]=config['measurementSlopeLength']
    return result


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


@contextmanager
def read_snapshot(conn):
    """Keep full feature reads and their raw windows in the caller's snapshot."""
    has_raw=install(conn)
    own=not conn.in_transaction
    if own:conn.execute('BEGIN')
    try:
        yield has_raw
    finally:
        if own:conn.rollback()


def resolve_rows(conn, rows):
    """Batch Core/chart reads: one prefix and bounded raw lookups per pair.

    Full feature rows already contain the retained EMA/ATR inputs. Reuse them
    rather than invoking a SQL callback and a historical query for each cell.
    The caller must hold read_snapshot (or its own explicit transaction).
    """
    if not rows:return
    if not conn.in_transaction:
        raise RuntimeError('Batch slope reads require an explicit snapshot')
    lengths=known_lengths(conn)
    groups={}
    for row in rows:groups.setdefault((row['symbol'],row['interval']),[]).append(row)
    columns=['open_time','formula_version','measurement_version','measurement_config_id',
             'measurement_contiguous_bars','atr','ema50','ema200','ema300']
    for (symbol,interval),group in groups.items():
        needed=[lengths[row['measurement_config_id']] for row in group
                if row['formula_version']==3 and row['measurement_version']=='shared-v1'
                and row['measurement_config_id'] in lengths]
        if not needed:continue
        maximum=max(needed)
        ordered=sorted(group,key=lambda row:row['open_time'])
        prefix=conn.execute('SELECT '+','.join('f.'+c for c in columns)+
            ',k.close_time,k.close FROM features f LEFT JOIN raw.klines k '
            'ON k.symbol=f.symbol AND k.interval=f.interval AND k.open_time=f.open_time '
            'WHERE f.symbol=? AND f.interval=? AND f.open_time<? '
            'ORDER BY f.open_time DESC LIMIT ?',
            (symbol,interval,ordered[0]['open_time'],maximum)).fetchall()
        window=deque((dict(zip(columns+['close_time','close'],row)) for row in reversed(prefix)),maxlen=maximum+1)
        raw={}
        times=[row['open_time'] for row in ordered]
        for offset in range(0,len(times),800):
            chunk=times[offset:offset+800]
            for stamp,close_time,close in conn.execute(
                'SELECT open_time,close_time,close FROM raw.klines WHERE symbol=? AND interval=? '
                'AND open_time IN ('+','.join('?' for _ in chunk)+')',[symbol,interval,*chunk]):
                raw[stamp]=(close_time,close)
        for row in ordered:
            item={column:row[column] for column in columns}
            item['close_time'],item['close']=raw.get(row['open_time'],(None,None))
            window.append(item)
            row.update(reconstruct(list(window),lengths))


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
    lengths = lengths_version = None
    cached_key = cached_result = None

    def resolve(symbol, interval, timestamp, period, stored):
        nonlocal lengths, lengths_version, cached_key, cached_result
        if symbol is None or timestamp is None or not has_raw:
            return stored
        # Reuse the three projections for a row on read-only connections only.
        # Data-version checks also invalidate the result after external commits.
        # Disabling this cache after local writes avoids rollback stale reads.
        version = (conn.execute('PRAGMA main.data_version').fetchone()[0],conn.total_changes)
        if lengths is None or lengths_version != version or conn.total_changes:
            lengths = known_lengths(conn)
            lengths_version = version
        key = (symbol, interval, timestamp, version,
               conn.execute('PRAGMA raw.data_version').fetchone()[0])
        if cached_key != key or conn.total_changes:
            result = read_values(conn, symbol, interval, timestamp, lengths)
            cached_key, cached_result = key, result
        return cached_result.get(f'ema{period}_slope_atr', stored)

    conn.create_function('feature_atr_slope', 5, resolve)
    return has_raw


def clear_verified(conn, keys, lengths, *, apply):
    """Check populated fields and clear only reconstructible, exactly equal values.

    Callers supply a fixed SQLite snapshot for a dry run, or a coordinated write
    transaction for apply. A mismatch raises before any feature UPDATE occurs.
    """
    if apply and not conn.in_transaction:
        raise RuntimeError('ATR clearing requires a write transaction')
    groups = {}
    report = dict(rows_checked=0,rows_cleared=0,values_cleared=0,values_retained=0)
    for symbol,interval,timestamp in dict.fromkeys(keys):
        old = conn.execute('SELECT rowid,'+','.join(FIELDS)+
            ' FROM features WHERE symbol=? AND interval=? AND open_time=?',
            (symbol,interval,timestamp)).fetchone()
        if old is None:
            raise RuntimeError('Feature row disappeared during ATR verification')
        report['rows_checked']+=1
        if all(value is None for value in old[1:]):
            continue
        derived = read_values(conn,symbol,interval,timestamp,lengths)
        names = []
        for field,value in zip(FIELDS,old[1:]):
            if value is None:
                continue
            if field not in derived:
                report['values_retained']+=1
                continue
            if value!=derived[field]:
                raise ValueError(f'ATR slope formula mismatch: {symbol} {interval} {timestamp} {field}; batch unchanged')
            names.append(field)
        if names:
            groups.setdefault(tuple(names),[]).append(old[0])
            report['rows_cleared']+=1
            report['values_cleared']+=len(names)
    if apply:
        for names,group in groups.items():
            for offset in range(0,len(group),900):
                ids=group[offset:offset+900]
                placeholders=','.join('?' for _ in ids)
                conn.execute('UPDATE features SET '+','.join(f+'=NULL' for f in names)+
                             ' WHERE rowid IN ('+placeholders+')',ids)
                bad=conn.execute('SELECT rowid FROM features WHERE rowid IN ('+placeholders+') AND ('+
                    ' OR '.join(f+' IS NOT NULL' for f in names)+') LIMIT 1',ids).fetchone()
                if bad:
                    raise RuntimeError('ATR slope clear read-back failed')
    return report


def retire_written(conn, keys, *, parameters=None):
    """Live/replay policy: persist inputs first, then verify and omit derivatives."""
    register_configurations(conn,parameters)
    if install(conn):
        return clear_verified(conn,keys,known_lengths(conn),apply=True)
