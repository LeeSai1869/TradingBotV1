# BTC 1h spot indicator: research design and Section 5 review

Assessment date: 13 November 2026, Pakistan time. This is a reviewable research
design. Entry/exit thresholds and risk parameters have not been validated or
connected to production signals.

An initial offline BUY/SELL prototype has now been created and replayed. It
failed the cost-adjusted comparison: see [PROTOTYPE_RESULTS.md](PROTOTYPE_RESULTS.md).
The proposed development direction below remains a hypothesis; this particular
prototype is rejected for live use.

## Evidence we can use

The exact-pair audit in [README.md](README.md) retains 8,290 qualifying upswings,
4,635 smaller upswings and 21 incomplete price paths. No tested origin-close
condition describes every qualifying move. High ATR, activity, EMA extension and
DI separation recur more often in the qualifying cohort. They describe readiness
and the potential size of a move; they do not identify its final low in real time.

A fixed overlap of RVOL >=1, absolute EMA50 extension >=1%, and ADX >=25 covers
only about 26.6% of evaluable qualifying lows, versus 6.7% of smaller lows. Its
coverage also differs by prior context: about 16.9% in the up proxy and 37.7% in
the down proxy. Requiring the same conjunction in every market condition would
discard most qualifying swings. These thresholds are exploratory assumptions,
not selected optimal values or live-signal precision estimates.

RSI <30 appears at about 19.1% of qualifying lows. A DI-minus peak recognized
on the origin close appears at about 17.9%. Simultaneous pressure and spread
peaks appear at about 8.6%. Their absence cannot by itself rule out an upswing.
The pressure peak describes the preceding candle and becomes known only when
the third candle closes. Price recovery, DI pressure turns, spread turns and
candidate updates must retain their separate recognition times.

## Separate setup branches

| Setup hypothesis | Context to classify before the trigger | Evidence sequence to investigate | Failure to watch |
|---|---|---|---|
| Trend pullback | Upward local/4h trend, daily conflict retained | Pullback to a previously known support/value area; selling pressure eases; buying pressure resumes with price acceptance | Reclaim fails or known support breaks |
| Downside exhaustion/reversal | Downward trend or negative extension; stronger adverse context explicitly recorded | Extended selloff with activity; independent pressure weakening; later reclaim of a price level already known at that time | New lows while the candidate keeps extending; activity without price recovery |
| Range rebound | Independently classified range and known lower boundary | Lower-boundary test or failed breakdown; close back inside; renewed demand | Acceptance below the boundary |

These are hypotheses, not claims that every successful pivot belongs to a
confirmed named setup. The present UP/DOWN/MIXED EMA proxies are only descriptive
slices. They do not validate Section 5 Trend, Regime or Phase. A mixed proxy is
not proof of a range, and a downward proxy does not imply a safe countertrend BUY.

Use the same evidence families across branches, while allowing their direction,
sequence and importance to differ:

1. **Location:** previously known support, value area, range edge or extension.
   A retrospective final pivot is an outcome label, never an entry requirement.
2. **Room/activity:** volatility, participation and remaining distance to known
   overhead barriers. Large ATR can mean both greater opportunity and greater risk.
3. **Pressure change:** DI-minus weakening, DI-plus recovery and spread behavior,
   retaining individual event times. Spread, DI dominance and ADX share inputs;
   counting them as three independent confirmations inflates evidence.
4. **Price acceptance:** a close/reclaim or failed breakdown observable at the
   signal time. A DI turn without favorable price response remains a watch event.
5. **Execution/risk:** an available fill, explicit invalidation, acceptable
   distance to the first barrier, and costs measured from the actual entry.

An initial classifier can output a setup ID, readiness observations, trigger
event, invalidation, provenance and missingness without issuing BUY. Compare
each branch's incremental contribution against the same eligible baseline
before deciding which observations should become mandatory gates or weights.
Do not invent a calibrated probability from an unvalidated confluence score.

## Spot state and timing

`FLAT -> WATCHING -> LONG -> EXIT_PENDING -> FLAT` is the proposed position
state. WATCHING records a causal candidate and expires or cancels when its
location/context fails. LONG starts only after an accepted BUY fill. Ignore
further BUY events while LONG; a SELL closes existing BTC. There are no shorts.

Research entry orders start at the next contiguous valid open after the trigger
close. Do not place a signal back on the eventual low. About 73% of qualifying
swings had already touched +1% by native-low recognition; about 25.5% had already
closed +1% above their low on the origin candle itself. Earlier entries require
separate lower-timeframe replay with only information known at each minute.
[TradingView's repainting documentation](https://www.tradingview.com/pine-script-docs/concepts/repainting/)
explains why retroactively plotted pivots and unconfirmed values need special care.

Exits should be tested separately: a previously known target/barrier, loss of
price control, structural invalidation, a protective stop and a time expiry.
Native HIGH confirmation is an outcome/audit event, not the only exit gate.
A falling DI-plus value alone does not establish price failure. Do not require
every exit to have the entry's activity/extension pattern.

The current objective labels a **1% gross extreme-to-extreme swing**. Retain it
for recall measurement. A separate execution objective measures net movement
from the actual BUY fill, including both sides' fees and slippage. For proportional
buy/sell costs `cb`/`cs`, net return is `(sell/buy)*(1-cs)/(1+cb)-1` under that
cash-cost convention. Use account-specific fees, rather than assuming the
analyzer's example fee: [Binance's fee schedule](https://www.binance.com/en/fee/trading).
When a stop and target occur within one hourly candle, preserve ambiguous order
or resolve it with finer data; do not silently award the target first.

## Is Section 5 expanding properly?

**The ownership and engine separation are sound. Historical readiness and
runtime verification are still incomplete.**

The code has ten separate engines, independent configurations, Core-owned
persistence, immutable input lineage, same-candle dependency contracts and a
separate multi-timeframe aggregator. Bias caps Trend/Structure correlation and
does not turn a funding proxy into an independent sentiment vote. Section 8
retains BUY/SELL policy ownership. These are appropriate boundaries for the
setup branches above.

The separate [operational snapshot](section5_readiness.json) was read at
11:16 PKT on 13 November 2026:

| BTC 1h engine | History rows classified | Pending rows | State |
|---|---:|---:|---|
| Regime | 200 | 80,674 | BACKFILLING |
| Structure | 300 | 80,574 | BACKFILLING |
| Trend | 100 | 80,774 | BACKFILLING |
| Momentum | 100 | 80,774 | BACKFILLING |
| Volatility | 100 | 80,774 | BACKFILLING |
| Participation | 0 | Target unavailable | NOT_STARTED |
| Phase | 0 | Target unavailable | NOT_STARTED |
| Liquidity | 0 | Target unavailable | NOT_STARTED |
| Sentiment | 100 | 80,774 | BACKFILLING; coverage is separately limited |
| Bias | 0 | Target unavailable | Waiting for indexed Momentum publication |

All BTC 1h/4h/daily live engine records were flagged STALE_OR_BACKLOG at that
inspection. The BTC 1h records refer to the candle opening 12 November at
21:00 PKT, closing 22:00; this is not a current 13 November classification.
The configured universe is 50 active symbols x 8 timeframes, or 4,000 engine
scopes. A report filter for BTC does not reduce that runner universe.

Three operational issues need attention before adding more engines/features:

1. **Running scheduler may predate the current source.** The runner log was still
   being written at 11:23 PKT, with `stage=downloads/features`,
   `upstream_pending_pairs=110`, and consecutive cycles showing zero analytical
   maintenance. Current `pipeline_scheduler.py`, modified at 10:38 PKT, instead
   announces `per-pair catch-up` and passes explicit ready pairs downstream.
   This is evidence of a possible loaded-code/deployment mismatch, not proof
   that the present source globally blocks every ready pair. Verify the loaded
   runner version and its first maintenance cycles after a controlled restart.
   Older error-log tails also contain SQLite lock failures; those tails were
   last modified 12 November at 22:38 and do not establish ongoing lock failures.
2. **History does not have a guaranteed independent row allocation.** In current
   `analytical_processor.maintenance`, history receives
   `min(history_max_bars, max_bars-total)`. A mocked saturation probe with
   200 live rows and `history_max_bars=200` passes **0** rows to history. This
   conflicts with the separate-budget wording in SECTION5_HISTORY.md. The
   pipeline currently supplies a larger 10,000-row cap, so this probe identifies
   a starvation possibility, not the demonstrated cause of today's backlog.
   Specify the intended combined cap versus reserved history share, then add
   a regression where live work actually exhausts its allocation.
3. **Stored coverage and mathematical validation are different.** Complete
   compatible 1h/4h/daily history, preserve UNKNOWN/partial external evidence,
   then re-export the row study. Today's book, funding, news or social data
   cannot reconstruct observations never recorded historically. Current structure
   fixes also require compatible feature replay before transferring this older
   export's results into a new strategy.

The Section 5 README and blueprint retain some earlier design-only statements
above later delivered-engine updates; operational status should come from the
versioned registry/readiness output rather than those old milestone paragraphs.

## Validation and next implementation gate

The selected engine/contract/scheduling/readiness suite passed 100 tests after
installing its missing `jsonschema` dependency in `/tmp`. The separate analytical
history suite passed 9 tests. These validate selected deterministic contracts and
fixtures, not market prediction. A repository import-boundary test independently
failed because `Section_4_Features/conversion/validate_export.py` is missing;
that file was already deleted in the working tree before this review.

The exact-pair audit checked every endpoint against its raw high/low and checked
that each high really is the first later native high. It separately censors gaps
and shortened candles, preserves failed pairs and records source SHA-256.

Freeze a causal branch specification only after coverage/replay review. Replay
all eligible closed candles, including candidates that never become native
pivots. Measure trade precision, big-swing recall, entry delay, adverse excursion,
net return, time in position and drawdown. Compare against a simple baseline at
the same costs and available timestamps. All 2017–5 November 2026 data in this
review has been inspected; it cannot be called an untouched holdout. Use later
uninspected observations for validation after freezing the rules.

This review does not change the live signal policy, scheduler, active universe,
engine configurations, production histories or databases.
