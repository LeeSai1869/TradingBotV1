# 01 — REGIME: contract 1.0.0

Status: DESIGN_ONLY. Inherits [COMMON.md](../COMMON.md); no runtime implementation
is added by this file. Proposed module: `engines/regime.py`.

## Responsibility

Identify the market environment; never emit entries or predict the next candle.

## Inputs

Required for the relevant dimensions:

- Closed OHLC; shared ADX, DI+/DI− and signed normalized dominance.
- Shared ER(20), NATR and NATR percentile(500).
- Shared BB width/percentile(500) for volatility-change corroboration.

Optional/partial-input policy:

- EMA slope/alignment measurements; existing confirmed break events for diagnostics only.

Public analytical dependencies: none.
See the feature audit for exact existing-field mappings and missing measurements.

## Classification vocabulary

| Field | Allowed values |
|---|---|
| `primary` | `TRENDING`, `RANGING`, `TRANSITIONAL`, `UNKNOWN` |
| `direction` | `BULLISH`, `BEARISH`, `NEUTRAL`, `UNKNOWN` |
| `volatility_level` | `EXTREMELY_LOW`, `LOW`, `NORMAL`, `HIGH`, `EXTREME`, `UNKNOWN` |
| `volatility_change` | `CONTRACTING`, `STABLE`, `EXPANDING`, `UNKNOWN` |
| `stability` | `STABLE`, `TRANSITIONING`, `UNKNOWN` |

## Rule and scoring constraints

Use the explicit draft rules below; no opaque vote over dozens of indicators.

Strength and confidence follow COMMON; publish the individual scoring components,
coverage budget and configuration hash before execution. Labels and thresholds
are research hypotheses until diagnostics and held-out evaluation support them.

## State and persistence

Confirmed primary/direction tuple, candidate tuple/count, last change/known time; separate volatility-state persistence.

Core commits candle history and checkpoints. Distinct interpretation events have
stable IDs and origin/known times; persistent labels do not duplicate events.
No SQL, network fetches or cross-engine implementation imports belong here.

## Admission tests

- All regime transitions and false breakouts.
- Temporary pullback, DI deadband and entry/exit hysteresis.
- Flat series, constant percentile baseline, warmup and gap reset.
- Prefix-only replay equals full-run prefix; checkpoint restart equivalence.
- All common causal, identity, version, missing-data and restart gates.

## Regime v1 experimental defaults and exact candidate rules

| Setting | Starting value |
|---|---:|
| ADX trend entry / hold | 25 / 21 |
| ADX range entry | 18 |
| ER trend entry / hold | 0.45 / 0.35 |
| ER range entry | 0.30 |
| Absolute DI dominance entry / hold | 0.10 / 0.05 |
| Closed-candle primary/direction confirmations | 3 |
| NATR / BBW percentile baseline | 500 prior valid candles |
| ER window | 20 intervals |

These are explicit starting assumptions, not optimal or validated values.

1. Missing required directional inputs: primary UNKNOWN, confirmation UNAVAILABLE.
   Independently valid volatility measurements may still be reported.
2. A current confirmed TRENDING direction is held when ADX >=21, ER >=0.35 and
   dominance keeps that sign with magnitude >=0.05.
3. Otherwise propose TRENDING when ADX >=25, ER >=0.45 and |dominance| >=0.10;
   direction is its sign. Equality qualifies. Valid DI total=0 defines dominance
   0 with a quality flag; missing DI does not.
4. Otherwise propose RANGING when ADX <=18, ER <=0.30 and |dominance| <=0.10;
   direction NEUTRAL. Hold logic is evaluated before this rule.
5. Otherwise propose TRANSITIONAL. Direction is NEUTRAL within the entry deadband,
   otherwise the signed directional evidence; it is descriptive, not an entry.
6. Three consecutive valid closed-candle proposals for the same primary/direction
   tuple confirm a change. A different proposal resets its count. A matching
   confirmed tuple cancels a pending change. Gaps reset pending evidence and make
   fresh classifications unavailable until inputs are valid again.
7. No structural acceleration shortcut in v1. Separate volatility level/change
   rules do not override the confirmed primary tuple.

The volatility level uses the bands in the Volatility contract. BBW percentile
and NATR-change jointly corroborate change; disagreement produces UNKNOWN change
until the exact change windows/deadbands are finalized. This is an explicit
remaining mathematical gate, not permission to invent a threshold in runtime.
Scoring weights, volatility-change deadbands and dimension-specific warmup must
be finalized in the Regime implementation specification before coding that engine.
