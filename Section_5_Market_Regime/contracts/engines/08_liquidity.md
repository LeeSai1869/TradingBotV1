# 08 — LIQUIDITY: contract 1.0.0

Status: RUNNER_CONNECTED. Inherits [COMMON.md](../COMMON.md).
Implementation: `engines/liquidity.py`; exact v1 scopes, rules and limitations:
[LIQUIDITY_V1.md](../../LIQUIDITY_V1.md).

## Responsibility

Expose structural hypotheses, observed execution liquidity and derivatives conditions as separately valid dimensions.

## Inputs

Required for the relevant dimensions:

- For structural dimension: existing confirmed levels, equal-high/low and range/session measurements.
- For sweep dimension: known pre-existing levels and closed OHLC/wick/volume evidence.

Optional/partial-input policy:

- For observed book: Core synchronized depth/spread/slippage/persistence with venue/market and coverage.
- For derivatives: funding, OI and sampled liquidation packets with freshness/known times.
- Estimated liquidation maps must be explicitly labeled modeled and sourced.

Public analytical dependencies: none.
See the feature audit for exact existing-field mappings and missing measurements.

## Classification vocabulary

| Field | Allowed values |
|---|---|
| `structural_side` | `BUY_SIDE_NEAR`, `SELL_SIDE_NEAR`, `AT_LEVEL`, `MID_RANGE`, `UNKNOWN` |
| `sweep` | `BSL_SWEEP`, `SSL_SWEEP`, `NONE`, `UNKNOWN` |
| `sweep_status` | `POTENTIAL`, `CONFIRMED_REJECTION`, `ACCEPTANCE_ABOVE`, `ACCEPTANCE_BELOW`, `NONE`, `UNKNOWN` |
| `book_state` | `DEEP`, `NORMAL`, `THIN`, `WITHDRAWING`, `UNKNOWN` |
| `derivatives_state` | `BUILDING`, `UNWINDING`, `STABLE`, `UNKNOWN` |

## Rule and scoring constraints

Each subdimension reports its own status/coverage. Structural pools are inferred locations, not resting orders. Later acceptance/rejection is a new event, not a rewritten sweep. Added/removed displayed depth is not a claim to identify individual cancellations or trader intent. Never fill unobserved depth bands with zero or infer missing historical books from candles.

Strength and confidence follow COMMON; publish the individual scoring components,
coverage budget and configuration hash before execution. Labels and thresholds
are research hypotheses until diagnostics and held-out evaluation support them.

## State and persistence

Structural/sweep event cursors and interpretation persistence only. Existing independent recorder retains book reconstruction, raw archive and flow state.

Core commits candle history and checkpoints. Distinct interpretation events have
stable IDs and origin/known times; persistent labels do not duplicate events.
No SQL, network fetches or cross-engine implementation imports belong here.

## Admission tests

- Known-level sweep, later rejection and later acceptance.
- Depth-window limitations and sequence gaps.
- Stale funding/OI versus genuine zeros.
- Spot/perpetual identity and cross-market basis validation.
- All common causal, identity, version, missing-data and restart gates.
