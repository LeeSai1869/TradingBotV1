# Current-move pivots and Market Structure display

## Adopted rule

After the first confirmed high/low pair exists, the candidate tracks the highest
high after the preceding low's origin or the lowest low after the preceding high's
origin. Strictly new extremes replace the candidate. Opposite extremes already
observed after that origin are retained even if recognition was delayed.

The reversal distance is 25% of the **current move** between the last confirmed
opposite pivot and the current candidate. For a candidate high it is
`0.25 × (candidate high − last confirmed low)`; for a candidate low it is
`0.25 × (last confirmed high − candidate low)`. A new extreme updates this distance. Confirmation also needs two
consecutive strictly lower closes for a high or higher closes for a low. The
current close must satisfy the price-distance condition. Equal/interrupted closes,
new extremes and missing candle continuity reset close confluence. No candidate
can confirm on its own origin candle, and a candle cannot confirm both directions.

The existing first-pair bootstrap remains because the new reference cannot be
computed before two confirmed pivots exist. It does not fabricate seed pivots.
After bootstrap the exported `pivot_rules_version` is `current-move-v2`; the
new `pivot_reference_range`, `pivot_confirmation_level` and `pivot_reverse_closes`
fields make the active calculation observable. They describe the current candidate,
including the new opposite candidate immediately after a confirmation.

State is JSON-checkpointed and independent of structure/BOS resets. A structure
break does not erase the price-swing candidate or its confluence. Decimal-derived
thresholds handle inclusive equality without the old binary-float near misses.

The archived Pine source still documents the original rule. A reviewed conversion
override retains this new Python rule and its bootstrap when regenerating code.
This is not a tested TradingView port. Two conversion dependencies removed in the
prior cleanup were restored so the checked-in conversion tools and their existing
tests remain usable; they do not run in the market-data loop.

## Historical update

This replaces confirmed-pair-v1. Existing v1 checkpoints/partial repairs cannot
be relabeled or reused as v2 history: the geometry changes which pivots confirm.
The writer schedules one targeted replay of affected columns from the beginning,
including replacement of an unfinished older-signature job. Its fair queue and
unchanged-current-indicator lane remain in place. No manual database deletion or
second replay command is required. Do not install the older pivot branch again.


The existing selective-repair framework detects the changed calculation units
from their fingerprints. It repairs structure fields and their actual dependency
closure in bounded, restart-safe batches, preserving the main checkpoint. It does
not rebuild the raw database or replay unrelated indicator columns. The migration
fixture verifies unchanged EMA, RSI, DMI/ADX, ATR and volume values and no change to
the current DI strategy generation. Dependent annotations (including some momentum
anchor context) legitimately recalculate when their structure inputs change.

Older structure values can be masked while their repair is pending. Completing a
large history takes time; the update does not override runner budgets, activate
paused pairs, or change coin/timeframe policies. Do not delete databases or run a
full replay to install this change.

Read-only progress check from the repository root:

```bash
python3 Section_13_Development/diagnostics/check_pivot_rules.py --symbol ENAUSDT --interval 15m
```

`REPAIR_PENDING` means the bounded job is still working. `UPDATED` means the latest
stored row uses the new rule and no pair repair is registered. `AWAITING_UPDATED_WRITER`
means a new-rule row has not yet been written; check the running checkout/pair policy.

## Display corrections

- PH/PL now include the engine's current protected-level references even when the
  level was first published before the loaded window. In-view levels draw dashed
  horizontal references. Off-screen levels show price labels with direction arrows,
  without expanding autoscale and shrinking the candles. These prices are not
  replaced with recent highs/lows just to make them visible.
- Independently controlled confirmed-high and confirmed-low trend lines connect
  confirmed pivot origins. Existing enabled SH/SL preferences enable their lines on
  migration unless a line was explicitly disabled. Pending candidates never become
  confirmed line points.
- Only the current CH or CL is shown once a later candle has closed. A candidate
  whose origin predates its activation is still displayed; it no longer depends
  on a one-candle discovery window.
- The established range band remains conditional on an actual `STRUCTURE_RANGE`
  and finite, ordered stored bounds. A `STRUCTURE_BEAR` or `STRUCTURE_BULL` with no
  range is not shaded. The settings explain this condition.

The exported ENA sample's old protected prices were 0.0726 (PH) and 0.0702 (PL),
below its roughly 0.10 visible candles, and its latest range bounds were absent.
Those facts explain missing references/bands independently of pivot confirmation.

## Validation

The production state machine reproduces all 568 approved confirmations in the
seeded 6,000-candle ENA 15m trial. Tests cover checkpoint serialization, 1h/4h pivot
restart parity on synthetic candles, first-pair bootstrap, producer event identity,
legacy selective repair versus a fresh full calculation, and preservation of
unrelated numeric columns. The real chart browser test exercises settings,
protected price edge labels, both lines, a valid range band and market switching.

Cold-start full-history results need not equal the seeded offline trial: the trial
started with the known pair at its export boundary. Earlier recursive history can
change subsequent anchors. No predictive accuracy or return claims are made.
