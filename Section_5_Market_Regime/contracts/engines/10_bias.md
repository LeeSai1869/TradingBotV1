# 10 — BIAS: contract 1.0.0

Status: RUNNER_CONNECTED. Inherits [COMMON.md](../COMMON.md).
Implementation: `engines/bias.py`; exact v1 synthesis rules and limitations:
[BIAS_V1.md](../../BIAS_V1.md).

## Responsibility

Synthesize same-timeframe analytical preference; never generate orders or replace Section 9 confidence.

## Inputs

Required for the relevant dimensions:

- Versioned public envelopes from available same-timeframe analytical engines.
- Declared directional-family weights, minimum coverage and neutral thresholds.

Optional/partial-input policy:

- Phase, observed liquidity and external sentiment may be unavailable; that reduces coverage.
- Regime and Volatility are contextual/risk inputs, not extra directional votes duplicating ADX/EMA evidence.

Public analytical dependencies: REGIME, TREND, STRUCTURE, MOMENTUM, VOLATILITY, PHASE, PARTICIPATION, LIQUIDITY, SENTIMENT.
See the feature audit for exact existing-field mappings and missing measurements.

## Classification vocabulary

| Field | Allowed values |
|---|---|
| `direction` | `STRONG_BULLISH`, `BULLISH`, `NEUTRAL`, `BEARISH`, `STRONG_BEARISH`, `UNKNOWN` |
| `risk` | `LOW`, `MODERATE`, `HIGH`, `EXTREME`, `UNKNOWN` |
| `alignment` | `ALIGNED`, `PARTIALLY_ALIGNED`, `CONFLICTED`, `UNKNOWN` |

## Rule and scoring constraints

Use only known valid inputs as of the decision-independent analysis time. Normalize directional evidence but retain full-budget coverage. Cap overlapping measurement families and expose supporting/conflicting sources. Do not consume both underlying and aggregated copies as separate votes. Insufficient coverage produces UNKNOWN; agreement among a tiny subset is not high confidence. Initial weights require held-out evaluation.

Strength and confidence follow COMMON; publish the individual scoring components,
coverage budget and configuration hash before execution. Labels and thresholds
are research hypotheses until diagnostics and held-out evaluation support them.

## State and persistence

Bias persistence/candidate counters and dependency IDs only; no raw indicator recomputation.

Core commits candle history and checkpoints. Distinct interpretation events have
stable IDs and origin/known times; persistent labels do not duplicate events.
No SQL, network fetches or cross-engine implementation imports belong here.

## Admission tests

- Opposing structure/momentum and neutral deadband.
- Missing engines and correlated-evidence caps.
- Risk changes without direction changes.
- Out-of-sample evaluation separate from classification stability.
- All common causal, identity, version, missing-data and restart gates.
