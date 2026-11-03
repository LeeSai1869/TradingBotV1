# Trend v1 experimental specification

Pure Section 5 interpretation, one source/instrument/timeframe at a time. Core
owns inputs, exact same-candle Structure dependency, persistence and bounded
runner turns. No indicator, pivot or BUY/SELL rule is recalculated/replaced.

## Measurements and direction

EMA family (one capped family): sign agreement of adjacent EMA7/25/50/100/200
pairs (average of four signs), average clipped EMA50/200 normalized slopes
(divide by reference .5 ATR), and close versus EMA50/200 (average two signs).
The family score = .50 alignment + .30 slopes + .20 price position, in [-1,1].
DI direction = existing signed normalized dominance. ADX measures strength only.
Structure direction = +1 bullish, -1 bearish, 0 explicitly neutral, only for a
compatible CONFIRMED same-candle Structure state. Unknown/broken/warmup/gap/invalid
Structure is unavailable; it is never substituted with neutral.

Directional score = .50 EMA + .30 DI + .20 Structure × dependency coverage.
Unavailable Structure contributes no vote and no extra normalization. EMA+DI
measurement evidence must support the proposed/held sign: Structure cannot
create or preserve a direction on zero or opposing measurement evidence. EMA and
ADX/DI inputs are required for direction; a measurement-only direction is allowed
when Structure is unavailable, with explicit reduced coverage and alignment.

Entry deadband ±.20; hold an existing bullish/bearish direction while its signed
score remains >=.10. Otherwise propose bullish >=.20, bearish <=-.20, neutral
inside the entry band. Three consecutive matching closed-candle proposals confirm
a change. A conflicting proposal resets pending evidence. A weakening positive
score is not automatically a bearish reversal.

## Strength, persistence, condition

Strength (0–100) = 100 × [.35 abs(EMA score) + .30 min(ADX/50,1) + .20 ER
+ .15 abs(positive-return fraction − negative-return fraction)]. ER and return
fractions must be valid and complete; missing values do not become zero strength.
Weak <25; moderate [25,50); strong [50,75); very strong >=75.

Persistence compares current strength with five contiguous valid closed candles
ago. Change >=5 points: increasing; <=-5: declining; otherwise stable. A missing
strength clears this history. The engine keeps at most persistence_bars+1 strength values (six by default).

Unknown direction -> unknown condition. Neutral, pending direction or conflicting
Structure -> unconfirmed. Aligned Structure + strength>=50 -> established.
Three consecutive declining observations with strength<50 and a confirmed
non-neutral direction -> exhausting. Other valid directional cases -> developing.
Exhausting describes measured weakening, not a promised price reversal.

## Coverage and confidence (not win probability)

Fixed coverage budget: .40 complete EMA family, scaled by min(contiguous source
bars / longest configured EMA period, 1) while its recursive seed is young; .25 complete ADX/DI family;
.15 complete ER/return-consistency family; .20 × valid Structure coverage.
Measurement-only coverage cannot exceed .80. No missing-source renormalization.

Confidence is the sum of family evidence contributions times direction-confirmation
progress. EMA and DI use max(0, direction_sign × family_score); neutral uses
1−abs(score). Movement uses (ER+abs(positive−negative))/2 for a directional
proposal, or (1−ER+flat_fraction)/2 for neutral. Structure contributes only when
aligned or explicitly neutral with a neutral proposal. All component values,
raw scores, coverage, confirmation counts and dependency references are exposed.
Strength and confidence intentionally measure different properties.

## Causality, source compatibility and operation

Expected shared windows are ER20, slopes5 and return fractions20; configuration
must match the source feature parameters. Configured EMA slot periods must be
positive and ordered fast to slow. Existing first-close EMA seeding is preserved;
short history reduces its evidence budget and is explicitly flagged rather than
pretending a 200-period EMA has a full 200-candle history. Input units, finite ranges, identity,
closed time, available time and source versions are checked. Three return fractions
must sum to one. Gaps clear direction/persistence state; missing directional
inputs yield unknown and do not carry forward a stale label. Preview evaluates a
copy and never advances committed direction, duration or history.

Core reads the matching versioned Structure run, not a latest unrelated result.
Its identity, candle and source/config fingerprints enter Trend lineage. Historical
reconstruction explicitly simulates dependency availability at the source candle
close; original actual publication availability is not claimed. A genuine missing
Structure classification is allowed as measurement-only. A dependency processor
backlog blocks that Trend row instead of permanently mislabelling it unavailable.

The existing analytical processor schedules Trend after Structure. Dependency
processing shares the caller's row budget. Results use the same versioned store,
immutable projected inputs and atomic checkpoints. The automatic recent seed
remains fixed per source/config, while manual full-history runs remain available.
All thresholds/weights are research assumptions requiring real-data diagnostics
and held-out evaluation before strategy use. No UI or trading-policy change.
