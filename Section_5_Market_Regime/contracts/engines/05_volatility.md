# 05 — VOLATILITY: contract 1.0.0

Status: DESIGN_ONLY. Inherits [COMMON.md](../COMMON.md); no runtime implementation
is added by this file. Proposed module: `engines/volatility.py`.

## Responsibility

Classify fluctuation magnitude, change and shocks; volatility has no inherent directional vote.

## Inputs

Required for the relevant dimensions:

- Existing ATR, true range/candle anatomy and closed-price data.
- Shared NATR and past-only percentile baseline.
- Shared realized log-return volatility, BB width and change measurements.

Optional/partial-input policy:

- Return skewness is required only for distribution; missing skewness means distribution UNKNOWN, not SYMMETRIC.
- Market-calendar/gap policy must be available for session assets.

Public analytical dependencies: none.
See the feature audit for exact existing-field mappings and missing measurements.

## Classification vocabulary

| Field | Allowed values |
|---|---|
| `level` | `EXTREMELY_LOW`, `LOW`, `NORMAL`, `HIGH`, `EXTREME`, `UNKNOWN` |
| `state` | `CONTRACTING`, `STABLE`, `EXPANDING`, `UNKNOWN` |
| `distribution` | `SYMMETRIC`, `SKEWED`, `UNKNOWN` |
| `shock` | `NONE`, `MODERATE`, `EXTREME`, `UNKNOWN` |

## Rule and scoring constraints

Use same-timeframe rolling relative levels and an independent shock rule. Initial percentile bands: <10 EXTREMELY_LOW, [10,25) LOW, [25,75) NORMAL, [75,90) HIGH, >=90 EXTREME. Raw high volatility is not proof of skewness or a shock. Zero movement/degenerate baselines have explicit flags and rules.

Strength and confidence follow COMMON; publish the individual scoring components,
coverage budget and configuration hash before execution. Labels and thresholds
are research hypotheses until diagnostics and held-out evaluation support them.

## State and persistence

Level/change/shock confirmation counters and last shock event; numerical distributions stay in Section 4.

Core commits candle history and checkpoints. Distinct interpretation events have
stable IDs and origin/known times; persistent labels do not duplicate events.
No SQL, network fetches or cross-engine implementation imports belong here.

## Admission tests

- Compression then expansion.
- Constant-price and constant nonzero-volatility histories.
- Isolated shock versus sustained high volatility.
- Calendar gaps, split-adjustment mismatch and warmup.
- All common causal, identity, version, missing-data and restart gates.
