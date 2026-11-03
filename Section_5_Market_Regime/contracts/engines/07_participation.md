# 07 — PARTICIPATION: contract 1.0.0

Status: RUNNER_CONNECTED. Inherits [COMMON.md](../COMMON.md).
Implementation: `engines/participation.py`; exact v1 rules: [PARTICIPATION_V1.md](../../PARTICIPATION_V1.md).

## Responsibility

Describe activity and its relation to price; actual aggressor dominance requires observed trade data.

## Inputs

Required for the relevant dimensions:

- Closed volume, volume units and valid shared volume average/RVOL.
- Shared price displacement/return and volume-change measurements.

Optional/partial-input policy:

- Matched observed aggressor buy/sell notional, trade count, coverage and known times.
- Separate spot/perpetual activity; do not join live perpetual flow onto old spot candles.

Public analytical dependencies: none.
See the feature audit for exact existing-field mappings and missing measurements.

## Classification vocabulary

| Field | Allowed values |
|---|---|
| `activity` | `VERY_LOW`, `LOW`, `NORMAL`, `HIGH`, `EXTREME`, `UNKNOWN` |
| `participation` | `INCREASING`, `STABLE`, `DECLINING`, `UNKNOWN` |
| `dominance` | `BUY_DOMINANT`, `SELL_DOMINANT`, `BALANCED`, `UNKNOWN` |
| `confirmation` | `CONFIRMING`, `DIVERGING`, `NEUTRAL`, `UNKNOWN` |

## Rule and scoring constraints

Use same-source relative volume and price-progress evidence. RVOL thresholds/percentiles are configuration, not universal facts. Without actual aggressor flow, dominance is UNKNOWN; candle colour is not a buyer/seller volume proxy. High volume with little movement is potential absorption/two-sided activity, not certain intent.

Strength and confidence follow COMMON; publish the individual scoring components,
coverage budget and configuration hash before execution. Labels and thresholds
are research hypotheses until diagnostics and held-out evaluation support them.

## State and persistence

Classification counters and last interpretation/event; volume baselines and flow windows come from the shared stores.

Core commits candle history and checkpoints. Distinct interpretation events have
stable IDs and origin/known times; persistent labels do not duplicate events.
No SQL, network fetches or cross-engine implementation imports belong here.

## Admission tests

- High/low volume movement and divergence.
- No volume versus genuine zero volume.
- Invalid legacy volume_ratio warmup fallback.
- Partial trade coverage cannot produce confident dominance.
- All common causal, identity, version, missing-data and restart gates.
