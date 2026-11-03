# 02 — TREND: contract 1.0.0

Status: RUNNER_CONNECTED. Pure module: `engines/trend.py`.
Inherits [COMMON.md](../COMMON.md); the exact experimental scoring, hysteresis,
warmup and dependency policies are specified in [TREND_V1.md](../../TREND_V1.md).

## Responsibility

Describe direction, strength and persistence; do not redetect pivots or emit BUY/SELL.

## Inputs

Required for the relevant dimensions:

- Closed price; existing EMA 7/25/50/100/200 and ADX/DI measurements.
- Shared ATR-normalized EMA slopes, ER and directional-consistency window.
- Versioned same-timeframe STRUCTURE output.

Optional/partial-input policy:

- Structure may be unavailable during pivot warmup: allow a separately labeled measurement-only result with reduced coverage, never pretend alignment.

Public analytical dependencies: STRUCTURE.
See the feature audit for exact existing-field mappings and missing measurements.

## Classification vocabulary

| Field | Allowed values |
|---|---|
| `direction` | `BULLISH`, `BEARISH`, `NEUTRAL`, `UNKNOWN` |
| `strength_band` | `WEAK`, `MODERATE`, `STRONG`, `VERY_STRONG`, `UNKNOWN` |
| `persistence` | `INCREASING`, `STABLE`, `DECLINING`, `UNKNOWN` |
| `condition` | `DEVELOPING`, `ESTABLISHED`, `EXHAUSTING`, `UNCONFIRMED`, `UNKNOWN` |
| `structural_alignment` | `ALIGNED`, `CONFLICTED`, `NEUTRAL`, `UNAVAILABLE` |

## Rule and scoring constraints

Aggregate EMA evidence as one capped family, ADX/DI as one and confirmed structure as another. Direction and strength are separate. Weakening is not reversal. Entry/exit deadbands and persistence are configured, not inferred from candle colour.

Strength and confidence follow COMMON; publish the individual scoring components,
coverage budget and configuration hash before execution. Labels and thresholds
are research hypotheses until diagnostics and held-out evaluation support them.

## State and persistence

Confirmed direction and candidate/count, strength history summary, duration since known trend change; only bounded state.

Core commits candle history and checkpoints. Distinct interpretation events have
stable IDs and origin/known times; persistent labels do not duplicate events.
No SQL, network fetches or cross-engine implementation imports belong here.

## Admission tests

- Slow trends and high-ADX pullbacks.
- Whipsaws and conflicting structure/EMAs.
- Weakening trend without reversal.
- Structure unavailable versus explicitly neutral.
- All common causal, identity, version, missing-data and restart gates.
