"""Bounded read-only check of ATR adapters against retained historical values."""
import argparse
from contextlib import closing
import json
import sqlite3
from Section_1_Global_Core.memory_storage.Storage import features_store as store
from Section_1_Global_Core.memory_storage.Storage import atr_slope_reads as slopes, klines_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.sample <= 10000:
        parser.error('--sample must be between 1 and 10000')
    if not klines_store.DB_PATH.is_file():
        parser.error('Raw candle database is unavailable')
    lengths = slopes.known_lengths()
    fields = list(slopes.FIELDS)
    checked = resolved = preserved = stored_bad = reader_bad = 0
    examples = []
    with closing(sqlite3.connect(
        store.DB_PATH.resolve().as_uri() + '?mode=ro', uri=True, timeout=5
    )) as c:
        slopes.install(c)
        c.execute('PRAGMA query_only=ON')
        # A bounded snapshot keeps the original and derived values consistent
        # during this sample even when the live writer is active.
        c.execute('BEGIN')
        rows = c.execute(
            'SELECT f.symbol,f.interval,f.open_time,' +
            ','.join('f.' + f for f in fields) + ',' +
            ','.join(store.read_expression(f) for f in fields) +
            ' FROM features f WHERE formula_version=3 ORDER BY rowid DESC LIMIT ?',
            (args.sample,)
        ).fetchall()
        for row in rows:
            expected = slopes.read_values(c, *row[:3], lengths)
            for offset, field in enumerate(fields):
                original, actual = row[3+offset], row[6+offset]
                if field in expected:
                    resolved += 1
                    if original != expected[field]:
                        stored_bad += 1
                        if len(examples) < 3:
                            examples.append(dict(symbol=row[0], interval=row[1],
                                open_time=row[2], field=field, stored=original,
                                derived=expected[field]))
                else:
                    preserved += 1
                if actual != expected.get(field, original):
                    reader_bad += 1
            checked += 1
    print(json.dumps(dict(rows_checked=checked, reconstructed_values=resolved,
        preserved_values=preserved, stored_formula_mismatches=stored_bad,
        reader_mismatches=reader_bad, examples=examples), indent=2, allow_nan=False))
    print('No database values or settings changed.')
    if stored_bad or reader_bad:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
