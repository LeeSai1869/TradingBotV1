# Market structure review

The review found real initialization defects, rather than evidence that every
NA comparison or every persistent flag is broken.

## Corrected behavior

* The first candidate high/low previously needed an already confirmed opposite
  swing, and both swing arrays start empty. Bootstrap now uses the previous
  candle's opposite extreme as an **unconfirmed initial anchor** for the existing
  25% retracement rule. It does not insert an invented confirmed pivot. Thereafter
  the latest confirmed opposite swing supplies that anchor as before.
* Confirmation is restricted to the candidate's direction and to a later closed
  candle. A direction switch cannot confirm both sides on the same candle.
* Before establishment, the old foundation block appended its foundation each
  candle. Merely preventing that duplication exposes another deadlock: the
  second typed pivot was only appended by continuation after establishment.
  Initialization now takes the two latest actual confirmed swings per side,
  classifies the latest relative to its foundation using the existing 20%
  equality band, and refreshes that pair only when its confirmed identity changes.
* BOS completion records an internal reset bar. A replacement foundation needs
  fresh confirmed pairs after that reset, rather than immediately recycling the
  just-invalidated structure. Continuation also checks pivot identity before
  appending an already confirmed swing again.
* Transition/BOS confirmation reads return NA when their structure-pivot array
  has no confirmed element. Strict runtime bounds checking remains enabled.

## Claims not supported by the current source

`newHighType` and `newLowType` are ordinary per-candle declarations, initialized
NA each call. `structureWasActiveBeforeBar` is recomputed from `structureState`
each candle. `activeBOS == 2` resets `activeBOS` to zero in the same block; it is
not inherently a repeated-event loop. Tests force a completion and verify that
later candles do not increment it again. A tracked high is superseded by a
higher high, not an arbitrary lower high; the claimed lower-high replacement
case does not follow from this candidate state machine.

`low` and `l` resolve to the same client OHLC value. `currentATR` is exported by
`volatility.py` before structure executes. A fixed established range is retained
until the engine changes/invalidates it; the display does not expand it to match
recent candles. Missing classifications while a candidate or foundation is
absent are intentional unknown values, not evidence of a valid pivot to invent.

## Scope and calculation cost

The Pine reference and its generated `market_structure.py` stay aligned. No
full conversion to native comparisons or a new state representation is included:
those would need independent NA-semantics and full replay verification. Repeated
foundation/continuation appends are removed at their source. Existing selective
plan caching remains active.

Historical repair updates market-structure fields and their dependency closure,
including consumers such as swing locations or structure-dependent features.
It preserves unrelated EMA, DMI/ADX, RSI and volume-profile columns and the main
checkpoint. Recursive state changes can affect subsequent historical candles;
it would be incorrect to patch just one timestamp or omit downstream consumers.
No duplicate dataset is created. UI settings, score controls and scheduling do
not invalidate formulas or create additional replay work.

## UI

Market Structure is available in Features: established range bands, protected
high/low levels, and confirmed swing high/low levels. Each output has visibility
and styles. The renderer uses stored levels; unknown or invalidated ranges end
coverage. FVG source-frame options apply on the source and lower charts, with
one overlay per gap when the generic and source-specific option are both on.
Score controls for S/R and FVG live in Display, with independent bulk score
selection. Scores require the corresponding zone to be visible and calculated.
Historical scores absent from stored data remain explicitly unavailable.

The now-active state-machine tests also exposed a selective-replay dependency
issue: a later persistent write (such as BOS cleanup) affects earlier consumers
on the **next** candle. The dependency graph now follows persistent-state writers
to those consumers as well as ordinary forward dependencies. Plans close these
dependencies even when resuming stored changed-unit sets. This can legitimately
expand affected structure-dependent columns; it is required to match a full
reference replay. Compiled-plan caching still avoids rebuilding identical plans.

A pending invalid-pivot transition previously looked for its confirmed pivot in
`structurePivotHighBar`/`structurePivotLowBar`, but invalid pivots are not added
to those accepted-structure arrays. Confirmation now checks the actual confirmed
swing arrays. This is a separate confirmed cause of stuck transitions; it does
not justify treating ordinary lower highs as candidate replacements. A focused
regression verifies the transition completes once when the actual swing matches.
