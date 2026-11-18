# EMA distance and nearest-EMA review

This phase retires duplicate storage for ten version-3 outputs after exact
formula verification. Live calculations and retained EMA inputs remain unchanged.

| Fields | Exact formula/selection |
|---|---|
| `ema50_distance_pct`, `ema200_distance_pct`, `ema300_distance_pct` | `abs(close - EMA) / close * 100` |
| `ema50_200_gap_pct` | `abs(EMA50 - EMA200) / EMA200 * 100`; returns zero when EMA200 is missing or zero |
| `nearest_buy_ema`, its `_distance` and `_distance_pct` | Closest EMA strictly **above** close, absolute distance, distance / close * 100 |
| `nearest_sell_ema`, its `_distance` and `_distance_pct` | Closest EMA strictly **below** close, absolute distance, distance / close * 100 |

The nearest search visits EMA7, EMA25, EMA50, EMA100, EMA200 and EMA300 in that
order. Equal-to-price values are excluded; tied distances keep the first period.
These outputs are prices/distances, not the selected EMA's period identifier.
The buy/sell names and percentage units intentionally retain current semantics.
The percentages here multiply by 100, unlike the earlier EMA gap fractions.
Missing denominators, zero close, null inputs and nonfinite outputs preserve the
live runtime's propagation/cleaning behavior. Negative inputs are not normalized
or silently replaced with positive values by these adapters.

All required inputs are retained on the same feature row: candle close `c` and
the six EMA values. They do not require EMA replay, lookback reconstruction or
configuration-hash inference. Base EMA values remain stored.

## Consumers

`export_pivot_candles.py` explicitly requests EMA50/200 distances through
`regime_inputs.project`. `analyze_btc_pivot_study.py` consumes these fields in
frozen studies. Generic pivot comparison, BTC sequence export, strategy research,
Core/chart reads, configurable alerts and replay prerequisites can request the
family through the existing column catalog. Absence of additional named consumers
does not establish that any field is unused.

Normal reads derive version-3 values in Python; dynamic SQL/replay/research reads
use matching SQL formulas. Both ignore stored duplicates for version 3. Versions
1/2 and unknown versions retain their original stored values, including nulls.
Live calculations remain in `features/ema_structure.py`. WMA fields, structure
flags, legacy price-above/below flags and all retained EMA inputs are out of scope.

## Required historical verification

```
python3 check_ema_distance_readers.py
python3 -u check_ema_distance_readers.py --full
```

The default audit compares a bounded sample of stored/Python/SQL values. The
full audit additionally scans all version-3 rows through a captured rowid and
compares their stored values against Python formulas. SQL parity remains sampled
to avoid repeated scalar sorts across the entire history. The commands use
read-only connections and leave legacy rows, writes and stored history intact.
Any mismatch blocks storage retirement pending review. Physical compaction
remains deferred to the consolidated rebuild.

## Verified retirement

The local full audit compared 31,388,604 version-3 rows through rowid 49,821,484
with zero stored/Python mismatches and zero SQL mismatches in its 1,000-row sample.

Normal and selective-replay writers verify persisted derivatives against retained
same-row inputs, then clear their cells inside the feature/checkpoint transaction.
A mismatch aborts that transaction. Historical cleanup uses a separate
`ema_distances_v1` checkpoint; prior ATR cleanup metadata is untouched.

```
python3 -u retire_ema_distance_storage.py --apply
python3 retire_ema_distance_storage.py --status
python3 check_ema_distance_readers.py
```

Default execution without `--apply` is a bounded read-only dry run. Apply waits
for current writer output, captures a target rowid, and verifies every populated
version-3 value before clearing each batch. Progress and clears commit atomically.
Source identity changes stop resumption. Legacy values are preserved. Omitted
values are counted as reconstructed by the reader audit, rather than mismatches.
Physical columns remain; this does not promise a smaller filesystem file before
consolidated compaction. No recursive EMA history is recalculated.
