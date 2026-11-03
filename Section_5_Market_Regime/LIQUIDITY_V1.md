# Liquidity analytical engine v1.0.0

Separate inferred structural locations, causal sweep outcomes, observed execution
conditions and derivatives positioning changes. These are descriptive hypotheses
and observations, not BUY/SELL rules or hidden-position/future-liquidation maps.

## Boundaries and persistence

Section 4 formulas, existing recorder/archive/storage, chart display and trading
rules remain unchanged. Section 5 imports no SQL, network clients, book reconstructor
or other engine implementation. Core reads a bounded, read-only as-of projection
and commits minimal immutable inputs, results and checkpoint state to intelligence.db.
The existing bounded runner includes this engine per active coin/timeframe, using
its saved recent 32-closed-candle seed and following new closes. Optional historical
research uses `run_regime.py --engine LIQUIDITY`; manual commands are not required.

Already committed inputs survive recorder pruning and reproduce exactly. Current
live data never fills an old candle. Corrected source generations/operator revisions
create separate runs. Provisional requests retain the previous classification,
return UNKNOWN candidates/no events and never advance stored state.

## Structural locations and sweep sequences

Reuse existing shifted prev_high_liquidity/prev_low_liquidity over 20 prior candles,
requiring 21 contiguous source bars. These exclude the current candle. Previous-day
high/low are also known before the current bar. Confirmed Section 4 pivot events
retain producer IDs and origin/known times; a newly confirmed pivot becomes eligible
on the **next** candle. Keep only the latest high/low pivot, expiring after 500 observed
candles. Gaps reset state; malformed pivot batches cannot partially update it.

Deduplicate exact equal references. BSL forward candidates are high-side references
at/above the close; SSL candidates low-side references at/below it. AT_LEVEL means
within 1 bp of a known reference. Otherwise the nearer forward side within 50 bps
is BUY_SIDE_NEAR/SELL_SIDE_NEAR. Distant references or equal-distance ties give
MID_RANGE. Missing forward targets remain null. These are inferred locations, not
resting quantities, hidden stops or guarantees that price will seek a level.

A pre-existing reference crossed by more than 1 bp, after the previous close was on
the appropriate side, starts BSL_SWEEP/SSL_SWEEP with POTENTIAL status. A crossing
can be a breakout rather than a rejection. Track at most one frozen reference per
side. Its starting candle cannot confirm its own subsequent outcome.

Require two later consecutive closed candles beyond the 1 bp reference buffer:
BSL closes below confirm rejection; above indicate ACCEPTANCE_ABOVE. SSL closes
above confirm rejection; below indicate ACCEPTANCE_BELOW. A resolution has its own
current known time and references the original sweep ID/origin; the original event
is never rewritten. Neutral closes reset confirmation counts. Unresolved sequences
expire after five subsequent candles. Gaps reset sequences. Simultaneous opposite
sequences/results retain their records but use TWO_SIDED_SWEEP_AMBIGUITY and UNKNOWN
top-level sweep labels. NONE requires adequate high/low/prior-close coverage.

## Observed source admission

Core reads at most two recorder samples and one latest-gap value per candle using
one read-only SQLite snapshot per batch. Only selected metrics/context are projected,
not chart bands/raw books. Missing/corrupt optional storage does not block structural
processing or create a recorder database. Timestamped symbol **and wildcard** gaps
are checked; current recorder status is never used retrospectively.

Samples must be explicitly observed Binance USDT perpetual data for the exact
instrument, available by candle as_of, with publication/sample age <=10 seconds.
A synchronized book also requires a positive sequence ID, consistent non-crossed
quotes, receipt/exchange times not in the future, age <=10 seconds and no later gap.
The existing recorder owns sequence bridging; no second book is reconstructed.

Chart identity currently is **Binance spot**, recorder identity **USDT perpetual**.
Core explicitly declares RELATED_PERPETUAL_CONTEXT with the closed spot price/time
and fresh perpetual mid. Section 5 recomputes basis and requires absolute basis
<=100 bps. Accepted observations retain perpetual identity in measurements.observed.scope
and PERPETUAL_CONTEXT_IS_NOT_SPOT_DEPTH. They never become spot depth or converted
structural levels. Exact perpetual chart identities can use EXACT_MARKET. Other
associations/venues/mismatched instruments are rejected. The basis bound is an
experimental admission heuristic, not a cross-market execution guarantee.

## Execution and trade flow

Default band: 10 bps. Reference trade size: 10,000 USDT. Both sides must actually
cover the band and provide valid depth and estimated buy/sell slippage for that size.
Missing deeper bands never become zero.

- THIN: minimum side depth <2 times reference notional, spread >2 bps, or either
  side's estimated slippage >5 bps.
- DEEP: minimum side depth >=10 times reference notional with acceptable spread and
  slippage. Otherwise NORMAL.
- WITHDRAWING overrides these when recorded 10-bps depth falls >=50% on either side
  over a gap-free recorder window <=10 seconds with a positive prior baseline.
  Other band choices do not reuse the 10-bps change field.

These are size-relative research thresholds, not universal depth rankings. Displayed
withdrawal does not identify cancellations/spoofing/intent. Slippage is relative to
mid and excludes fees/latency/subsequent cancellations. Resting depth is cancellable.

Optional recent flow requires continuous trades, a complete 60-second rolling window,
coverage >=.99, observed duration 59.5–70 seconds and no intervening gap. Actual buy/sell
aggressor notionals give imbalance; zero traded total has null imbalance, not invented
dominance. Imbalance magnitude >=.6 with <=2 bps absolute price progress is only
absorption **evidence**. Partial windows remain unavailable. Candle colour is never
used as an aggressor proxy.

## Derivatives

OI needs a real earlier sample published at/before as_of minus 5 minutes. Context
receipt/exchange times must be fresh (<=120 seconds), baseline OI positive, same
market/instrument and no intervening gap. Actual OI measurement interval must be
3–7 minutes and is exposed. Current zero OI is valid; zero baseline is not divided by.
OI change >=+.5% gives BUILDING, <=-.5% UNWINDING, otherwise STABLE. It describes
position size, not whether longs outnumber shorts or price must decline.

Mark/index and indicative funding require their own <=10-second freshness. Genuine
zero funding stays zero; missing/stale context stays null. Reported long/short
liquidations retain their exact gap-free short recorder window (<=10 seconds),
labeled SAMPLED_EXCHANGE_REPORTS_NOT_ALL_LIQUIDATIONS. They are not whole-candle
totals, a full census or future liquidation-price clusters.

## Scores, diagnostics and scope

Fixed evidence budgets: structural sides .25 (.125 each); sweep observation/known
pending reference .25 (.125 each); covered book/quotes/slippage .25; complete recent
flow .05; OI change with baseline .10; fresh mark/index/funding .05; explicit sampled
liquidation window .05. Missing budgets never gain weight through renormalization.
Candle-only coverage can reach .50. Confidence equals admitted evidence coverage,
not a win probability or calibrated reliability estimate. Strength is null without
a book; otherwise 100 times minimum side depth relative to the configured DEEP
capacity, capped at 100. It measures execution capacity, not reversal strength.

Every family contribution and observed scope is exposed. Dimensions remain
independent: a candle gap resets structural sequences but does not invent a feed
gap if a valid point observation exists. Overall GAP/INVALID quality still reports
candle-data problems. Diagnostics count independent dimensions, events, quality and
classification changes. Thresholds need real-market/held-out evaluation.

Observed state is a **point snapshot near candle close**, not a whole-timeframe
average. Flow/derivatives retain their declared recent intervals. Candle-wide
aggregation, cross-venue comparison and modeled liquidation maps are not claimed.
Recorder point samples retain six hours; its minute summaries retain 90 days. This
engine uses point samples: an unrecorded/pruned period stays unavailable rather than
substituting a summary for a book. Committed analytical inputs survive that pruning.
