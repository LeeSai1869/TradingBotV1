# Volatility v1 experimental specification

Direction-free Section 5 interpretation of existing Section 4 measurements.
No ATR, Bollinger, return distribution or trading signal is recalculated here.
The current Core adapter supports unadjusted Binance spot 24/7 UTC candles;
stock/session/adjustment policies require a dedicated adapter before admission.

## Independent dimensions

Level uses NATR's full prior-500 observation percentile: <10 extremely low,
[10,25) low, [25,75) normal, [75,90) high, >=90 extreme. Current observations
are excluded from Section 4's baseline. BBW percentile is separate corroboration,
not averaged into NATR's rank. Constant nonzero baselines rank 50 but carry a
degeneracy flag and half rank-evidence confidence. Missing rank is not zero.

State uses the existing five-interval NATR and BBW fractional changes: both
>=+.05 expanding; both <=−.05 contracting; both strictly inside ±.05 stable;
disagreement is unknown. Level/state each require three consecutive proposals.

A complete observed flat window (NATR=0, BB width=0, realized return SD=0,
zero_price_movement=true, at least return_length+1 contiguous closes) is explicitly
extremely low and stable without requiring 500 prior observations. This is an
absolute-zero observation, not filling missing ranks/undefined 0/0 changes with
zero. Distribution remains unknown when return SD is zero: skewness is undefined.

Distribution needs valid positive realized return SD and existing finite skewness:
|skewness|>=1 skewed, otherwise symmetric. Three candles confirm this dimension.
Symmetric means below this skewness threshold, not Gaussian or light-tailed.
Neither skewness sign nor volatility level is a bullish/bearish vote.

Shock is independent of percentile level: max(current candle_range, absolute
opening gap from prior close) / **prior** ATR. >=3 moderate, >=5 extreme,
otherwise none. This is an intrabar-range/opening-gap shock model, not a claim
that a missing true-range feature is available. Current ATR is not used as the
shock denominator because it already incorporates the observation being tested.
One closed candle confirms a shock by default, allowing isolated shocks to be
reported immediately. Repeated severity emits no duplicate event; transitions
into moderate/extreme emit a severity-transition record with the candle's origin
bar and closed known time, not a fabricated intrabar trigger timestamp.

Valid prior ATR=0 with range=gap=0 is none; positive movement against a zero prior
ATR is unavailable with ZERO_SHOCK_BASELINE, not infinity/extreme by fiat. Missing
prior ATR/close is unavailable. Shock comparison also requires at least ATR-length
plus one contiguous source candles; a legacy ATR seed is not treated as freshly
warmed immediately after a raw gap. Raw candle gaps reset all dimensions and suppress
shock comparison against a stale previous bar. Calendar month continuity uses
stored close times, never a fixed day count.

## Scores and coverage

Fixed budget: NATR level .30, BBW level corroboration .10, joint change .25,
return distribution .15, shock model .20. No missing-source renormalization.
Rank confidence is halved for a full constant nonzero baseline. BBW agreement
is full for the same percentile band, half for adjacent bands, zero for wider
conflict. Absolute flat evidence uses the full observed-zero level budget.
Other families contribute their budget times their own confirmation progress.
Input coverage and confirmation evidence are separate; scores are not probability.

Strength is NATR percentile (relative volatility magnitude), or 0 for observed
flat movement; unavailable when that dimension lacks usable observations.
Complete finite source inputs can still disagree; conflict flags are explicit.
Shock/state/distribution may be available while percentile level is warming.
Expected source windows: prior ranks500, change5, log-return SD/skew20. Settings
and thresholds are frozen validated VolatilityConfig values, not hidden constants.

Core owns automatic bounded processing, versioned history, immutable projected
inputs and atomic checkpoints. There are no analytical dependencies, new feature
columns, downloads, workers, chart overlays or BUY/SELL/confidence/opportunity
changes. Historical publication availability remains explicitly reconstructed.
These thresholds are hypotheses needing real-data diagnostics and evaluation.
