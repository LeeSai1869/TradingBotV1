# 06 — PHASE: contract 1.0.0

Status: RUNNER_CONNECTED. Inherits [COMMON.md](../COMMON.md).
Implementation: `engines/phase.py`. Exact v1 sequence rules, defaults and limitations:
[PHASE_V1.md](../../PHASE_V1.md).

## Responsibility

Describe a developing cycle hypothesis from a causal sequence; never assert hidden institutional buying from a sideways range.

## Inputs

Required for the relevant dimensions:

- Versioned same-timeframe Trend, Structure and Participation.
- Shared range boundaries/duration, volatility-change and failed-breakout measurements.
- Origin and known times for sequence events.

Optional/partial-input policy:

- Benchmark relative strength where valid point-in-time benchmark coverage exists.
- Observed absorption can corroborate only with matching venue/market/coverage.

Public analytical dependencies: TREND, STRUCTURE, PARTICIPATION.
See the feature audit for exact existing-field mappings and missing measurements.

## Classification vocabulary

| Field | Allowed values |
|---|---|
| `phase` | `ACCUMULATION`, `MARKUP`, `DISTRIBUTION`, `MARKDOWN`, `REACCUMULATION`, `REDISTRIBUTION`, `TRANSITION`, `UNKNOWN` |
| `development` | `DEVELOPING`, `CONFIRMED`, `INVALIDATED`, `UNKNOWN` |
| `preceding_trend` | `BULLISH`, `BEARISH`, `NEUTRAL`, `UNKNOWN` |

## Rule and scoring constraints

Require an ordered preceding trend → range development → supply/demand evidence sequence. Accumulation/distribution stays DEVELOPING until defined structural confirmation; do not backdate that confirmation. Reaccumulation/redistribution requires a known prior trend. Implement UNKNOWN/TRANSITION before speculative labels. Evidence scores are not probabilities.

Strength and confidence follow COMMON; publish the individual scoring components,
coverage budget and configuration hash before execution. Labels and thresholds
are research hypotheses until diagnostics and held-out evaluation support them.

## State and persistence

Bounded hypothesis sequence, preceding trend reference, range ID, confirmation/invalidation times and event cursor.

Core commits candle history and checkpoints. Distinct interpretation events have
stable IDs and origin/known times; persistent labels do not duplicate events.
No SQL, network fetches or cross-engine implementation imports belong here.

## Admission tests

- Ordinary consolidation versus supported cycle hypothesis.
- Continuation range versus reversal range.
- Invalidation and repeated failed breakouts.
- Prefix reconstruction never labels an earlier range with later knowledge.
- All common causal, identity, version, missing-data and restart gates.
