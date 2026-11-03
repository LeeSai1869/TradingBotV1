# 03 — STRUCTURE: contract 1.0.0

Status: DESIGN_ONLY. Inherits [COMMON.md](../COMMON.md); no runtime implementation
is added by this file. Proposed module: `engines/structure.py`.

## Responsibility

Interpret existing confirmed pivot/structure outputs and events without creating another swing algorithm.

## Inputs

Required for the relevant dimensions:

- Existing Section 4 confirmed pivots, classifications, BOS/CHOCH and structure state.
- Pivot origin time/bar and confirmation/known time.
- Closed OHLC and existing ATR-normalized break distances.

Optional/partial-input policy:

- Candidate/unconfirmed pivots may be exposed as candidates only, not confirmed events.

Public analytical dependencies: none.
See the feature audit for exact existing-field mappings and missing measurements.

## Classification vocabulary

| Field | Allowed values |
|---|---|
| `direction` | `BULLISH`, `BEARISH`, `NEUTRAL`, `UNKNOWN` |
| `condition` | `DEVELOPING`, `CONFIRMED`, `BROKEN`, `INVALIDATED`, `UNKNOWN` |
| `last_event` | `HIGHER_HIGH`, `HIGHER_LOW`, `LOWER_HIGH`, `LOWER_LOW`, `EQUAL_HIGH`, `EQUAL_LOW`, `BOS`, `CHOCH`, `SWING_FAILURE`, `NONE`, `UNKNOWN` |
| `active_structure` | `HH_HL`, `LH_LL`, `RANGE`, `MIXED`, `UNKNOWN` |

## Rule and scoring constraints

Map existing semantic outputs through an explicit adapter. Preserve original pivot IDs and known times. Wick crossing and confirmed-close break are distinct. A persistent last_event is not a new event each candle. Do not reinterpret legacy enums without a documented mapping.

Strength and confidence follow COMMON; publish the individual scoring components,
coverage budget and configuration hash before execution. Labels and thresholds
are research hypotheses until diagnostics and held-out evaluation support them.

## State and persistence

Last confirmed pivot/event IDs, known-time state, last processed event cursor; no duplicate pivot detector.

Core commits candle history and checkpoints. Distinct interpretation events have
stable IDs and origin/known times; persistent labels do not duplicate events.
No SQL, network fetches or cross-engine implementation imports belong here.

## Admission tests

- Pivot delay and immutable event origin.
- Repeated state emits no duplicate BOS/CHOCH event.
- Wick/close distinction.
- Reconstruction agrees with existing Section 4 events.
- All common causal, identity, version, missing-data and restart gates.
