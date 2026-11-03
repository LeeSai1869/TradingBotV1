# Implementation sequence and acceptance gates

## This release

Contracts only. No runtime imports of registry/schema documents, no calculation
changes, no new feature columns, no database migration and no runner restart are
required. Existing Section 5 and all decision/confidence/opportunity consumers
remain untouched. Mathematical hypotheses in later-engine contracts are not
claimed implemented or validated.

## Stage 1 — formalize Regime and its shared inputs

1. Reconcile field semantics with FEATURE_AUDIT and the current feature manifest.
2. Finalize Regime's pending scoring components, volatility-change windows,
   deadbands, per-dimension warmup and zero/gap policy. Freeze a validated config.
3. Implement missing measurements in Section 4 under narrow dependency ownership.
   Add hand-calculated fixtures and streaming/batch/checkpoint parity checks.
4. Define the public Core snapshot adapter and historical lineage strategy. Pure
   Section 5 code must not import Section 4 execution internals or private stores.
5. Implement only `engines/regime.py`, its typed schema/state and isolated tests.
6. Add Core-owned versioned persistence/checkpoints through existing bounded
   scheduling. Do not introduce another bulk downloader/worker just for Regime.
7. Run shadow history for selected configured pairs, then broaden by the registry
   after measuring workload. Do not manufacture data for paused/incomplete scopes.
8. Compare against the current Section 5 interpretation without replacing it.
   An explicit adapter/consumer migration is a separate reviewed implementation.

## Stage 2 — later engines

Structure is first an adapter over existing events. Trend consumes that adapter;
Momentum/Volatility/Participation reuse shared measurements. Phase follows only
when its dependencies and sequence rules are supported. Liquidity consumes the
existing recorder/gateways. Sentiment stays unavailable without actual sources.
Bias and the separate aggregator come last. The DAG, rather than a marketing
engine list, determines scheduling order.

## Required correctness and performance checks

- Hand-computed feature/classification fixtures, warmup and every boundary value.
- Prefix causality: appending future candles cannot change prior outputs/events.
- Same inputs/config/generations reproduce the same deterministic payload.
- Batch, streaming and checkpoint/restart equivalence for each pair.
- Duplicate timestamps, out-of-order bars, gaps, corrected inputs and partial data.
- Independent symbol, market and timeframe states; previews do not mutate commits.
- No missing-as-zero values or uncalibrated probability claims.
- Version/config/input-generation isolation; same-key divergence is rejected.
- Dependency-directed replay touches only changed outputs and real dependents.
- Engine code has no private storage/network imports or cross-engine internals.
- Benchmarks report compute rows/s, cold/warm state restoration, I/O/commit cost,
  scheduler wait, peak memory and end-to-end catch-up. Module splitting alone is
  not a performance explanation; measure the actual bottleneck.

## Analytical diagnostics

Report counts/distributions by symbol/timeframe, UNKNOWN/partial coverage and its
reasons, state durations, switches per 1,000 valid candles, confirmation delay,
pending/canceled transitions and time in unstable states. Report cold-start and
gap recovery separately. Inspect trending/ranging/shocked/flat paths and compare
against declared baselines. Track changes by engine/config/input version.

These are diagnostics, not profit evidence. Before using classifications to
filter a strategy, freeze thresholds and evaluate chronological held-out periods,
trading costs and appropriate position/exit simulation. Do not tune on the test
period or declare a market phase correct merely because a later move fits it.

## Remaining design gates

The common envelope and engine boundaries are specified. Exact mathematical
scoring, optional-source weights, later-engine thresholds, every engine-specific
measurement/state schema, the Core public adapter, persistence migrations and UI
presentation are future implementation work. They must be explicit before those
engines enter the production scheduler. A schema-valid record alone does not
establish semantic correctness, data quality or predictive value.

## Section 4 foundation delivered

Stage 1 shared candle inputs are now implemented and covered by numerical,
checkpoint, dependency-replay and legacy-regression tests. See
[the feature contract](../../Section_4_Features/SHARED_MEASUREMENTS.md).
This does not change the existing Section 5 runtime. The next implementation unit
is Regime v1, after finalizing its scoring, public snapshot adapter and immutable
projected-input lineage/persistence described above.

## Regime v1 shadow implementation delivered

The first pure classifier, typed immutable configuration, public Core projection
adapter, immutable minimal input bundles and atomic versioned history/checkpoints
are implemented. See [REGIME_V1.md](../REGIME_V1.md) and `run_regime.py --help`.
It is deliberately on-demand: no scheduler, UI or decision migration is included.
Source/config/seed changes produce separate runs. Out-of-band raw edits require an
explicit revision; historical publication availability remains reconstructed.
Live shadow scheduling and later engines remain subsequent stages.

## Automatic maintenance and Structure state adapter

The existing processor registry now runs Core analytical maintenance after
features and decisions. Active pair/engine scopes rotate under a shared bounded
budget. Automatic runs use a saved recent 32-candle seed and then follow closes;
full historical research runs remain separately available. No UI or DI policy
migration is included. Structure's state/counter adapter is implemented with
explicit partial coverage; confirmed-pivot event lineage remains a source gap.

## Trend v1 delivered

The pure Trend classifier, independent immutable config, exact same-candle
Structure dependency projection/reference, atomic historical state and automatic
runner turn are implemented. Dependency processing shares the existing row budget.
No Section 4 formula, UI or strategy migration is included. See TREND_V1.md.

## Momentum v1 delivered

Pure Momentum interpretation and separate immutable configuration are connected
to the existing bounded analytical maintenance/store. Shared numerical features
and confirmed DI-anchor events are reused; no second detector or indicator is
created. Acceleration uses absolute-strength change, and exhaustion requires
persistent weakening with timed corroboration. See MOMENTUM_V1.md.
