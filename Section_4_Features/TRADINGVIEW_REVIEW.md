# Full Section 4 / Section 5 conversion

The executable calculations in `sections_4&5_Tradingview` are translated into
**29 Section 4 main-feature modules and six Section 5 modules**. The complete
537-field MarketFeatures contract and six regime outputs are calculated and
persisted, with compatible aliases for existing clients. This replaces the earlier
partial translation. It does not add renderers for every advanced feature.

## Files and ownership

- Active individual features: [`individual/`](individual/README.md).
- Section 5: [`../Section_5_Market_Regime/features/`](../Section_5_Market_Regime/features/).
- Composition: `feature_builder.py`; bounded runner integration: `processor.py`.
- Shared execution state: `individual/context.py`; scalar/array primitives:
  `individual/runtime.py`; versioned JSON checkpoints: `individual/checkpoint.py`.
- The EMA, RSI, ATR, ADX/DI, WMA, VWAP and volume files contain their native
  calculation kernels as well as their source-referenced update functions.
- `features/registry.py` indexes the active individual modules. Small older pure
  APIs remain for import compatibility; they are not the runner's calculation path.
- Broad `market_location`, `market_liquidity`, `market_imbalance`, `bos_structure`
  implementations are removed from the legacy source. The converted
  `individual/support_resistance.py` owns the complete support/resistance lifecycle.

The previous Section 4/5 Python source is preserved in
`backups/pre_full_conversion_b5a67d7.zip`. Raw candles are not deleted or downloaded
by the conversion. The existing runner remains the only download/processing loop.

## Streaming and migration

Recursive averages start from the beginning of the raw history, with Pine's
initialization and missing-value handling. Persistent zones, IDs, touches,
institutional qualification, pivots, structure, FVGs, order blocks, breakers,
Fibonacci and session memory advance once per chronological closed candle.
State is scoped by symbol/timeframe, including the previous regime.

Permanent feature rows and their checkpoint commit in one SQLite transaction.
The checkpoint is a versioned JSON record in `features.db`, not another market
memory or a pickle. A restart resumes the committed prefix, rather than rebuilding
indicators from an arbitrary 500-bar tail. Parameters/source version and deletion
epochs are checked before resuming. Failed writes discard the transient engine;
admin deletion also removes its checkpoint.

Existing formula-v1/v2 rows are progressively recalculated as formula version 3.
Before their first replacement, the runner preserves the feature database as
`features.pre-pine-v3.db`. Replay uses bounded pages and a round-robin maintenance
budget between download cycles, including intervals with no new candles. Older
rows remain available while replay catches up. Large histories can take time;
`python3 check_coin.py ETHUSDT` reports the separate full-conversion cursor.

Forming-candle features come from a copy of the committed closed state. They never
write features or advance the checkpoint. They remain unavailable until that
checkpoint is adjacent to the forming candle. The UI reader observes new runner
checkpoints without restarting or using a stale in-process calculation cache.

## Source semantics and explicit corrections

The reference is a fragment: Section 3 `MTFData`, input definitions, the
`normalizeRelative` helper and the calling context are external. The adapter uses
one Binance UTC bar stream per symbol/timeframe. It supplies current/previous
OHLCV, full-session VWAP and volume average. Each stream is an independent Pine
execution context. A separate chart context with different raw OHLCV is not
implicitly mixed into a requested timeframe.

External defaults come from the existing repository: EMA inputs, RSI 7, ADX 10,
ATR 10/14, symmetric pivot length 5, volume/lookback inputs and FVG constants.
`Engine(..., parameters={...})` accepts the corresponding Pine input values.
`normalizeRelative` uses the existing Global Core `normalize_relative` helper.
A TradingView comparison must use matching inputs and execution context.

Confirmed source corrections are limited and explicit:

1. The `MarketFeatures.new(...)` arguments do not consistently match its declared
   field order: notably VWAP flags/levels and candle pattern fields. Python binds
   outputs by declared field name, with explicit aliases such as `vwapValue` and
   `prevDayHigh`, instead of reproducing those mislabelled positional slots.
2. The volume-profile expansion can decrement below bin zero forever on an empty
   neighbor tie. The converted loop chooses only available neighbors, guaranteeing
   progress without altering the in-range larger-neighbor/tie selection.
3. An earlier review incorrectly described `prevBodyPercent` as a duplicate
   function declaration. One occurrence is its type field and the other is its
   calculation; no correction is required for that field.

Other source behavior is retained rather than silently redesigned. In particular,
`nearestSellLiquidityPct` compares `internalLowDistance` in price units with
`externalLowDistancePct`; this source unit inconsistency needs a deliberate future
formula change. FVG invalidation requires zone interaction as written; a candle
that gaps wholly past a zone does not interact with it. Institutional qualification
remains restricted to 4H, and source references/availability flags are preserved.

Daily references implement `request.security`'s default historical lookahead-off,
gaps-off timing. Historical intraday daily expressions update at the daily close;
realtime values use the developing daily context. Consequently these references
can differ across historical/realtime evaluation, as in Pine. Higher-timeframe
bars require real 1D inputs: no daily high/low/open is fabricated from a weekly
candle. If 1D history is still absent, these outputs are null with
`daily_source_ready=false`; the runner fills those reference fields when the daily
history arrives, without holding up all other features. If 1D downloads are
intentionally disabled and no corresponding data exists, they remain unavailable.

## Validation and limits of the evidence

Tests cover every executable reference statement's module coverage, all 537
exported fields, independent Wilder/EMA vectors, all six regime states, FVG failure
memory, institutional ID ownership, empty-bin profile expansion, per-pair
isolation, JSON restart equivalence, live forks, bounded replay, non-destructive
backup, daily dependency repair and the combined storage gateway. Browser
regressions exercise the existing chart/indicator consumers after schema growth.

These are not a TradingView-export certification. No original TradingView
bar-by-bar output fixture was supplied. Full numerical parity should be checked
against a matching export, including the same history start, inputs and MTF
context; the source constructor corrections above also need to be reflected in
that comparison. The supplied comparison tool fails on mismatches and performs
no database writes:

```sh
python3 -m Section_4_Features.conversion.validate_export export.csv --symbol ETHUSDT --interval 15m --fields rsi adx ema50
```

The CSV needs `time,open,high,low,close,volume` and the expected field columns.
Empty expected cells mean Pine `na`. Use `--parameters` with a JSON input object;
`--daily-csv` supplies 1D raw bars for daily security references. It compares from
the first row, including warmup. It cannot establish full-history equivalence
from an export that omits the initialization history.

## Reproducible conversion

`python3 -m Section_4_Features.conversion.compile_reference` regenerates the
source-referenced update functions and field manifest. This is a build-time tool;
the app runs ordinary Python functions, never Pine parsing or `eval`. Unsupported
source syntax/dependencies fail explicitly. The source checksum, feature spans,
extra source lines and written outputs are in `individual/manifest.json`.

When changing formulas or state semantics, increment the checkpoint version and
replay the raw history. Do not resume an old checkpoint under new formulas.

## Main-feature consolidation

The regrouping preserves formulas, source-call IDs, calculation order, persistent
array names and all exported fields. Checkpoint version 3 remains compatible;
existing memory resumes without a replay caused solely by moving files. Liquidity,
support/resistance, sessions, order blocks with breakers, EMA metrics and ADX/DI
each have one owner. The manifest keeps their dependency stages explicit. The
converter emits these owners directly and removes superseded generated files.
Existing UI renderers/styles and HUD/alert field names remain available; this
refactor does not introduce new chart renderers for advanced zone features.
