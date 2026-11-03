# Multi-Timeframe Aggregator — contract 1.0.0

Status: RUNNER_CONNECTED. Section 5 module `aggregation.py`. Exact v1 policy:
[AGGREGATION_V1.md](../AGGREGATION_V1.md). This is not an
extra indicator or a hidden dependency inside each analytical engine.

## Input

One engine family and one venue/market/instrument at an explicit `as_of`, plus:

- Registry-defined configured/active timeframes and calendar/order metadata.
- Latest valid committed result per timeframe **known by as_of**, with exact result
  ID, input/config versions, age, quality and confirmation.
- Explicit aggregation policy: horizon groups, importance weights, maximum age,
  required coverage and allowed version compatibility. No numerical defaults are
  claimed universally valid for all trading horizons.

Do not take a later 4H close when reconstructing a 5m observation. Use an as-of
join over result availability, not origin/open timestamp. Reconstructed-history
availability assumptions must remain visible. No fixed list/maximum of timeframes
is embedded in the component; month/session duration comes from the registry.

## Output

A separate aggregation envelope contains identity (without a single timeframe),
engine family, aggregator version/config hash, as_of/available_at/computed_at,
referenced timeframe result IDs, per-horizon summaries, coverage/quality,
overall evidence confidence and alignment:

`ALIGNED`, `PARTIALLY_ALIGNED`, `CONFLICTED`, or `UNKNOWN`.

Conflicts are structured records of the involved timeframes, states and known
times. Report a short-term bearish state against a longer bullish state as a
countertrend conflict, not as an averaged bearish majority. For Regime, aggregate
behaviour/direction/volatility dimensions separately.

Stale/missing/incompatible outputs remain in diagnostics with exclusion reasons.
They do not become neutral votes. Required coverage is evaluated against the full
configured horizon budget, not just the available subset. Do not count repeated
bars from a small timeframe as independent confirmations of a larger timeframe.

## Ownership and persistence

Core performs as-of selection and stores versioned aggregation history/checkpoints.
The aggregator consumes public result envelopes only; no OHLCV, indicators, SQL,
network fetching or base-engine implementation imports. Use the dependency route
in BLUEPRINT: per-timeframe base engines → per-timeframe Bias → aggregation.

Result identity includes source identity, engine family, as_of, aggregator
version/config and exact input-result set. Missing results changing to available
creates a traceable new input generation, not silent historical mutation.

## Admission gates

Test mixed horizons, unknown/stale sources, disabled scopes, calendar boundaries,
late publication, data correction generations, version incompatibility and
prefix-only reconstruction. Demonstrate that changing one timeframe recomputes
only affected aggregates. Aggregator outputs never feed back into their own base
classifiers, and never create BUY/SELL decisions.
