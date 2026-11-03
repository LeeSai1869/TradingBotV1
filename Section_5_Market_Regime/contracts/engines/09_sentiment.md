# 09 — SENTIMENT: contract 1.0.0

Status: RUNNER_CONNECTED, PARTIAL DERIVATIVES SOURCES. Inherits [COMMON.md](../COMMON.md).
Implementation: `engines/sentiment.py`; exact v1 scope and rules:
[SENTIMENT_V1.md](../../SENTIMENT_V1.md).

## Responsibility

Interpret observed sentiment sources and positioning risk without conflating optimism with a trading edge.

## Inputs

Required for the relevant dimensions:

- At least one declared external sentiment/positioning source for its relevant dimension.
- Shared same-source historical normalization and timestamps/publication/revision metadata.

Optional/partial-input policy:

- Funding, OI, venue-defined long/short ratios, crowd/social/news data are independently optional.
- Price-only context remains explicitly separate and cannot establish broad crowd sentiment.

Public analytical dependencies: none.
See the feature audit for exact existing-field mappings and missing measurements.

## Classification vocabulary

| Field | Allowed values |
|---|---|
| `sentiment` | `EXTREMELY_BULLISH`, `BULLISH`, `NEUTRAL`, `BEARISH`, `EXTREMELY_BEARISH`, `UNKNOWN` |
| `positioning` | `LONG_CROWDED`, `SHORT_CROWDED`, `BALANCED`, `UNKNOWN` |
| `stability` | `IMPROVING`, `STABLE`, `DETERIORATING`, `RAPIDLY_CHANGING`, `UNKNOWN` |
| `risk` | `LOW`, `MODERATE`, `HIGH`, `EXTREME`, `UNKNOWN` |

## Rule and scoring constraints

Separate source categories, latency and coverage. Funding is positioning evidence, not comprehensive sentiment. Long/short account ratios are not the ratio of all long/short contract notional; counterparties exist on both sides. OI/price combinations are contextual interpretations, not identification of intent. Unknown sources remain unavailable; no external feed is assumed implemented by this blueprint.

Strength and confidence follow COMMON; publish the individual scoring components,
coverage budget and configuration hash before execution. Labels and thresholds
are research hypotheses until diagnostics and held-out evaluation support them.

## State and persistence

Interpretation persistence, point-in-time source references and revisions; source ingestion and numerical normalization stay outside this engine.

Core commits candle history and checkpoints. Distinct interpretation events have
stable IDs and origin/known times; persistent labels do not duplicate events.
No SQL, network fetches or cross-engine implementation imports belong here.

## Admission tests

- Conflicting sources and concentrated coverage.
- Stale/revised daily data joined only after publication.
- Bullish mood with crowded-long risk.
- No sources returns UNKNOWN, not NEUTRAL.
- All common causal, identity, version, missing-data and restart gates.

V1 admits raw indicative funding tilt and explicit five-minute comparisons, not
normalized historical extremes. EXTREMELY_* sentiment and all crowding labels remain
unavailable pending proper normalization/source adapters. This partial scope is
mandatory in the result measurements; broad sentiment is not claimed.
