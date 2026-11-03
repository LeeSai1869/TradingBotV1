# Phase v1.0.0 — causal cycle hypotheses

Phase describes a developing cycle hypothesis. It neither measures hidden
institutional positions nor issues BUY/SELL decisions. All thresholds below are
configurable research defaults, not established predictive parameters.

## Boundaries and execution

- Section 4 remains the owner of reusable numerical features. No feature formulas,
  columns, UI, confidence/opportunity logic or trading rules change in this release.
- Phase consumes public, exact-version, same-candle Trend v1, Structure v1.1 and
  Participation v1 outputs. It imports no other engine implementations.
- Core admits exact stored rows, config/source expectations and immutable lineage
  references. Only Structure's current `new_events` projection is included; no wide
  child feature packet is copied. Trend's transitive Structure dependency is bound
  into the parent source generation as well.
- Core persists inputs, results and checkpoint state atomically in intelligence.db.
  Missing dependency checkpoints cause a bounded wait, not false unavailable rows.
  Genuine unavailable classifications produce UNKNOWN and clear the active sequence.
- The existing runner processes Phase independently per active coin/timeframe.
  All child work, including Trend's nested Structure work, counts within the existing
  row budget. At least five rows of turn budget are needed; a turn uses at most
  `floor(limit/5)` Phase rows plus four times that many child rows. Existing scheduler
  limits, decision processing and UI remain in place.
- Automatic processing uses the existing fixed recent seed (32 closed candles) and
  follows new closes. It cannot infer an unobserved earlier cycle. Optional explicit
  historical research uses `run_regime.py --engine PHASE --since ...`.

## Inputs and causal sequence

The existing `range_high/range_low` are rolling high/low over `rangeLookback=100`,
including the current candle. Reuse `atr`, ER(20), five-bar NATR/BBW changes, source
continuity and shared validity metadata. No separate rolling range or ATR is built.

1. **Preceding direction.** Require five consecutive observed closed-candle Trend
   outputs with ESTABLISHED condition, CONFIRMED direction, and agreement with
   CONFIRMED Structure. This gives MARKUP/MARKDOWN and records the streak's origin
   and current known time. An anchor not refreshed within 200 observations expires
   before a new range; a captured range freezes its own preceding-trend reference.
2. **Capture a range.** Require at least 100 contiguous source candles, positive ATR,
   ordered positive bounds, ER <= .30, neutral Trend or RANGE Structure, and both
   NATR/BBW changes <= .05 (not rapidly expanding). Width must be <= 6 ATR. Freeze
   the observed low/high/ATR and range ID at the capture candle. Require five observed
   range candles before collecting hypothesis evidence. This is not a claim that
   the whole preceding 100-bar window was already a confirmed range.
3. **Later corroboration.** Only candles after capture and after range development
   can contribute. With price closing inside the frozen range:
   - Demand evidence: a lower-edge wick reclaim with a positive body, close at least
     25% up the range, and HIGH/EXTREME Participation with CONFIRMING price progress;
     or a newly confirmed HIGHER_LOW, whose pivot originates strictly after capture
     and inside the range, accompanied by NORMAL/HIGH/EXTREME Participation.
   - Supply evidence mirrors that rule: upper-edge wick rejection/negative body,
     close at least 25% below the top, or a later confirmed LOWER_HIGH.
   These are price/volume corroborations, not aggressor measurements. Each side gets
   at most one evidence record per candle, retaining the last two records. Require
   two separate evidence candles. Opposing two-sided evidence cancels the hypothesis
   into TRANSITION; the engine does not choose a preferred narrative.
4. **Developing label.** Demand after a bearish trend gives ACCUMULATION; demand after
   a bullish trend gives REACCUMULATION. Supply after bullish gives DISTRIBUTION;
   supply after bearish gives REDISTRIBUTION. Missing prior direction or missing
   corroboration leaves TRANSITION. Sideways price alone never gives accumulation.
5. **Confirmation.** Require three consecutive closes more than .1 captured ATR
   outside the relevant edge, matching confirmed Trend direction, and a same-sequence
   producer-confirmed BOS/CHOCH in that direction during the current breakout run.
   Its reference origin must be known and within the captured range's time span.
   Confirmation belongs to the current candle; it never relabels the earlier range.
   This confirms the **cycle hypothesis under these rules**, not institutional intent.
   An ordinary range without a supported hypothesis can resolve to MARKUP/MARKDOWN
   under the same directional breakout/structural confirmation rule; it is never
   retrospectively called accumulation/distribution.
6. **Failure/invalidation.** A close through the opposite buffered edge invalidates
   a supported hypothesis immediately at that close. Returning inside the breakout
   buffer before confirmation creates FAILED_BREAKOUT and resets that attempt.
   Switching breakout sides also fails the prior attempt. A range expires after
   120 observed candles. Resolution clears the range on the following candle; later
   directional establishment produces a new MARKUP/MARKDOWN state.

A hypothesis confirmed on a breakout candle retains its cycle label with
`development=CONFIRMED` for that candle. Subsequent candles establish their own
phase. A phase transition/event includes the current known time and a separate
range origin; origin and knowledge time are never interchangeable.

## Missingness, continuity and previews

Identity, market, timeframe, config/source bindings, units, availability, finite
measurements and versioned dependencies are checked. Gaps reset the sequence.
Unknown/invalid required child evidence also resets it rather than carrying a
previous phase as fresh knowledge. Zero ATR and degenerate range cannot capture a
range; no division by zero or invented geometry occurs. The current calendar
adapter supports 24/7 UTC crypto, using actual source close times for continuity.

Phase is a closed-candle engine. A provisional request returns the prior confirmed
classification and UNKNOWN candidate, no new events, and unchanged stored state;
current same-candle confirmed dependencies are not assumed to exist intrabar.

## Scores and diagnostics

Fixed input budgets: Trend .25, Structure .25, Participation .20, range inputs .20,
volatility-change inputs .10. Each child budget is multiplied by its valid coverage.
Missing budgets never gain weight through renormalization. All required child
outputs must be usable before Phase interprets a sequence. A typical candle-only
Participation coverage of .75 caps total Phase coverage at .95.

Sequence completion is .25 for TRANSITION, .5 for a supported developing hypothesis,
and 1 for a confirmed directional phase, confirmed hypothesis or explicit invalidation.
Strength = 100 * sequence completion. Confidence = coverage * sequence completion.
These are transparent evidence/completion scores, not directional advantage,
reliability estimates, return forecasts or win probabilities. An invalidation can
have complete evidence without being a favorable setup.

Diagnostics include phase/development counts, event counts, classification changes,
mean phase duration, quality counts and pending candles. Real-market distributions
and held-out outcome evaluation are still necessary before strategy use.

Benchmark relative strength and observed trade-level absorption are not admitted
inputs in v1. They are future optional corroborators requiring matched point-in-time
source contracts. Phase does not silently synthesize them from candle volume.
