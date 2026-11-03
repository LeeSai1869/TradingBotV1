# Section 5 analytical-engine blueprint — contract release 1.0.0

## Agreed ownership

| Owner | Responsibility | Must not do |
|---|---|---|
| Section 1 Core | Ingestion, source identity, public gateways, scheduling, quality metadata, persistence and replay transactions | Hide analytical rules in SQL or duplicate engine logic |
| Section 2 Inputs | Validated feature/engine configuration snapshots | Mutate settings halfway through a candle/batch |
| Section 4 Features | Reusable numerical measurements, indicators, existing pivot/zone events | Calculate a second copy per analytical consumer |
| Section 5 Intelligence | Independent, explainable interpretations through public versioned contracts | Open private databases, fetch feeds, place trades or alter other engines' state |
| Section 8 Decisions | BUY/SELL decision policy | Treat every bullish classification as a BUY |
| Section 9 Confidence / Section 10 Opportunity | Existing price-point evidence and anchored opportunity plans | Be silently replaced by Section 5 classification confidence or bias |
| Section 11 UI | Display contracted results, provenance and unavailable states | Recalculate classifications from chart visibility/viewport |

Independence means separate modules, contracts, configuration and tests. It does
not mean one process, downloader, thread, database or feature history per engine.

## Planned modules, not files to execute yet

```text
Section_5_Market_Regime/
    contracts/                       # this release: design only
    engines/                         # future pure analytical modules
        regime.py
        trend.py
        structure.py
        momentum.py
        volatility.py
        phase.py
        participation.py
        liquidity.py                 # structural/sweep/book/derivatives functions
        sentiment.py
        bias.py
    aggregation.py                   # future explicit cross-timeframe component
    contracts.py                     # future typed envelopes/validation
    config.py                        # future configuration snapshot adapter
    diagnostics.py                   # future summaries; no hidden classifications
```

A small file per engine is the starting point. Split a complex engine into a
subdirectory only when necessary. Persistence/checkpoint implementations belong
in Core, not in these engine modules. Existing Section 5 source remains active;
these future files must not shadow its exports or create duplicate calculations.

## Registry and dependency graph

[registry.json](registry.json) records all ten engine contracts, proposed modules,
input owners, feature gaps and dependencies. It is not an automatic scheduler.

- REGIME: Section 4 measurement snapshots only.
- STRUCTURE: adapter/classifier over existing confirmed Section 4 structure/events.
- MOMENTUM: Section 4 measurements, including existing DI anchors.
- VOLATILITY: Section 4 volatility measurements.
- PARTICIPATION: Section 4 volume/price measurements; optional observed trade data.
- TREND: Section 4 measurements + STRUCTURE output.
- LIQUIDITY: existing structural/sweep measurements and Core's observed book,
  trade and derivatives packets. It does not require Phase or Bias.
- PHASE: TREND + STRUCTURE + PARTICIPATION + Section 4 shared measurements.
- SENTIMENT: timestamped external source features; price context is separately
  labeled, never a substitute for unavailable external sentiment.
- BIAS: the other nine same-timeframe outputs through their public contracts.

This is a directed acyclic graph. An optional dependency cannot become a hidden
mandatory dependency. No base engine consumes Bias or an aggregation of itself.

## Timeframe model

Every engine handles one venue/market/instrument/timeframe at a time. The Core
scheduler fans out over the existing configured timeframe registry. No hard-coded
list or maximum number of timeframes is introduced inside engines. Paused scopes
retain history and do not silently resume downloads.

The canonical initial route is:

```text
Core sources → Section 4 shared features → Section 5 base engines
    → same-timeframe Bias → per-engine Multi-Timeframe Aggregator → UI/report
```

Bias is available independently on each timeframe. The aggregator may aggregate
any engine family, including Bias. A future overall cross-timeframe Bias would
need its own contract/name and must not reuse both raw per-timeframe votes and
aggregated copies of those same votes. It is not included in v1 implementation.

## Boundary interface

Proposed callable: `evaluate(snapshot, config, previous_state) -> (result, state)`.
Inputs are immutable snapshots. State is owned by that engine and pair, serialized
with an explicit state-schema version. Processing previews copies confirmed state;
it never commits a provisional mutation. Core owns I/O, execution order and atomic
result/checkpoint commits. See [COMMON.md](COMMON.md).

No engine imports another engine's implementation. An input adapter accepts its
public result envelope and verifies the version/configuration/dependency identity.
No global symbol/timeframe state is shared between engine instances.

## Scope of the first implementation

Finalize Regime mathematics/configuration, add only its missing Section 4 features,
then implement and evaluate Regime in shadow mode. Do not implement all ten at
once. Preserve current Section 5 outputs and all current consumers until explicit
compatibility and performance gates pass. Contracts for later engines establish
ownership and acceptance criteria; their rule sets are not claimed validated.
