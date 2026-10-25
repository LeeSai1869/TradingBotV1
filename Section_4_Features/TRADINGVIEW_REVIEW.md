# Full Section 4 / Section 5 conversion

Formula/input edits now use [selective historical replay](execution/SELECTIVE_REPLAY.md).
Matching existing formula-v3 checkpoints retain their progress; future edits
update only affected columns and dependents. Strategy and display edits do not
restart feature history.

The executable calculations in `sections_4&5_Tradingview` are translated into
**22 numbered Section 4 calculation modules and six Section 5 modules**. The complete
537-field MarketFeatures contract and six regime outputs are calculated and
persisted, with compatible aliases for existing clients. This replaces the earlier
partial translation. It does not add renderers for every advanced feature.

## Files and ownership

- Active calculations: [`features/`](features/README.md), one file per numbered 4.2 section.
- Section 5: [`../Section_5_Market_Regime/features/`](../Section_5_Market_Regime/features/).
- Composition: `feature_builder.py`; bounded runner integration: `processor.py`.
- Shared execution helpers: `execution/`; source metadata: `conversion/manifest.json`.
- Native indicator kernels live in their numbered owners: trend, momentum,
  volatility, VWAP and volume. There is one calculation path.
- Old pure implementations and the superseded `individual/` tree are removed.

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
numbered section boundaries and written outputs are in `conversion/manifest.json`.

When changing formulas or state semantics, increment the checkpoint version and
replay the raw history. Do not resume an old checkpoint under new formulas.

## Numbered-section ownership and replay isolation

File ownership follows the actual 4.2.x source headers, not inferred categories.
The complete 4.2.12 candle section includes engulfing, rejection, pivots and
break/retest. Range and swing location have their own numbered source sections.
Shared execution helpers and the source manifest live outside the feature folder.
Formulas, source-call IDs, exported fields and checkpoint version 3 are preserved;
existing memory resumes without recalculation solely because files moved.

A replay error previously escaped maintenance and aborted the rest of its pass.
Maintenance now reports the failing symbol/timeframe, retains its committed
checkpoint, and continues other pairs within the global budget. Orchestrator
maintenance failures also no longer prevent the event pass. Failed candles are
not skipped. Disabled timeframes remain paused. `check_coin.py SYMBOL --logs`
shows policy, pending raw candles after each checkpoint, and recent runner logs.
This fixes a demonstrated failure-isolation path; it does not establish why an
individual Mac stalled without that machine's diagnostic output.

The already-calculated `prevCandleRange` local was missing from the exported
legacy `prev_candle_range` field. That field is now included in new packets;
existing historical rows are not rewritten solely for this output addition.


## Runtime performance and display additions

The volume-profile histogram's inner loop now uses native arithmetic with the same
per-candle/per-bin addition order. The source converter emits this reviewed kernel;
all other VP outputs remain source-derived, and packet regression vectors remain
unchanged. Canonical field-name conversion is memoized. Checkpoint/formula version
3 remains compatible; no full replay is triggered by this optimization.

Eight additional display fields expose the selected dynamic/institutional S/R
zone's actual low/high from its persistent arrays. These do not change scoring or
existing output values. New rows include them, while old rows remain readable.
FVG rendering tracks qualified events and checkpoint-active gaps through their
source-candle invalidation; nearest-selection changes do not end a zone.


## Reviewed FVG corrections — 2026-10-24

The supplied Pine contained two confirmed source defects: bear normalization
bounds read the bull array and both used its maximum; bullish reaction activation
was never persisted on touch. Both the Pine reference and regenerated Python now
use the bear population's min/max and persist the bull active flag every pass.
A continuous touch counts once; completing and then starting another reaction
counts again, consistently for both directions.

Bear normalized reaction quality now uses `higher_is_better=True`, matching bull
quality. This is an intentional scoring-semantic correction: the old `False`
inverted quality, rather than clamping it. Existing low aliases, NA comparisons,
zero-divisor protection and reverse removal semantics remain unchanged.

The frozen component baseline is preserved. The source diff schedules 34 FVG
outputs/dependents for selective repair, never a full feature reset. Main replay
checkpoints and all unrelated columns remain intact; the repair's own historical
cursor is shown separately. The current DI/ADX decision strategy does not depend
on these FVG fields and therefore receives no new decision-generation reset.

## Reviewed market-structure corrections — 2026-10-25

See `MARKET_STRUCTURE_REVIEW.md` for confirmed findings and disagreements with
the submitted critique. The reference and generated Python now bootstrap the
first swing without an invented confirmed pivot, seed typed foundations from
actual confirmed pairs, refresh pre-establishment pairs by identity, avoid
re-appending a confirmed continuation pivot, and wait for fresh pairs after BOS.
Missing confirmation-array entries remain NA instead of raising out-of-bounds.
A forced BOS completion is verified to reset once, rather than increment every
later candle. The reviewed 700-bar vector changes 42 structure-dependent fields;
core EMA, DMI/ADX, RSI and VP outputs are unchanged. Affected state and downstream
columns are repaired using the dependency graph, including cross-candle feedback.
