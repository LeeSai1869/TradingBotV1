# 04 — MOMENTUM: contract 1.0.0

Status: DESIGN_ONLY. Inherits [COMMON.md](../COMMON.md); no runtime implementation
is added by this file. Proposed module: `engines/momentum.py`.

## Responsibility

Describe directional movement strength and its change, independently of trend or the Section 8 signal.

## Inputs

Required for the relevant dimensions:

- Existing RSI, DI+/DI−, signed spread and confirmed DI-anchor outputs.
- Shared ROC, ATR-normalized multi-bar displacement and its acceleration.
- Source/confirmation times for price-linked momentum anchors.

Optional/partial-input policy:

- Shared MACD/histogram if explicitly enabled; not mandatory in v1.
- Divergence and rejection provide corroboration, not proof of exhaustion.

Public analytical dependencies: none.
See the feature audit for exact existing-field mappings and missing measurements.

## Classification vocabulary

| Field | Allowed values |
|---|---|
| `direction` | `BULLISH`, `BEARISH`, `NEUTRAL`, `UNKNOWN` |
| `strength_band` | `WEAK`, `MODERATE`, `STRONG`, `VERY_STRONG`, `UNKNOWN` |
| `acceleration` | `ACCELERATING`, `STABLE`, `DECELERATING`, `UNKNOWN` |
| `condition` | `BUILDING`, `SUSTAINING`, `WEAKENING`, `EXHAUSTING`, `UNKNOWN` |

## Rule and scoring constraints

Direction follows signed movement evidence with a neutral deadband. Acceleration follows change in absolute movement strength: negative signed momentum becoming more negative is bearish acceleration, not generic deceleration. EXHAUSTING needs persistent weakening plus corroboration. Reuse the existing DI anchors rather than rebuilding them.

Strength and confidence follow COMMON; publish the individual scoring components,
coverage budget and configuration hash before execution. Labels and thresholds
are research hypotheses until diagnostics and held-out evaluation support them.

## State and persistence

Classification persistence counters and last known anchor IDs; rolling numerical measurements remain in Section 4.

Core commits candle history and checkpoints. Distinct interpretation events have
stable IDs and origin/known times; persistent labels do not duplicate events.
No SQL, network fetches or cross-engine implementation imports belong here.

## Admission tests

- Positive and negative impulses.
- Bearish acceleration versus numerical increase/decrease.
- Plateaus and noisy turns.
- Anchor confirmation lag and unavailable origin lookup.
- All common causal, identity, version, missing-data and restart gates.
