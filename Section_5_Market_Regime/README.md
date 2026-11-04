# Section 5 — Market Intelligence

Section 5 is the agreed home for separate analytical engines. The directory name
`Section_5_Market_Regime` remains unchanged for import compatibility. The current
`Market_Regime.py`, `regime_packet.py` and `features/` modules keep their existing
behaviour until a tested, explicit migration is approved.

The new design is in [contracts/BLUEPRINT.md](contracts/BLUEPRINT.md). Start there,
then read the [common contract](contracts/COMMON.md),
[shared feature audit](contracts/FEATURE_AUDIT.md) and
[implementation gates](contracts/IMPLEMENTATION.md).

**Status: Regime, Structure, Trend, Momentum and Volatility run automatically.** The JSON
registry remains descriptive and is not imported by the runner. The existing
six-state calculations and all current consumers remain unchanged.

## First independent engine: Regime v1

[REGIME_V1.md](REGIME_V1.md) is the frozen experimental implementation spec.
`engines/regime.py` is pure and independent; Core owns `regime_inputs.py`,
`regime_research.py` and the shared analytical history store. Its research command remains available; automatic runner integration is described
below. It is not connected to chart or decision consumers. Structure now consumes producer-confirmed event lineage; Trend now consumes that same-candle public output; Momentum is implemented as described below; Volatility is implemented as described below; the other five engines remain design-only.

For a recent independently seeded research run:

```bash
python3 run_regime.py --symbols BTCUSDT ETHUSDT ENAUSDT --intervals 5m \
  --since 2026-10-01 --max-bars 1000 --summary --diagnostics
```

Repeat to resume. Omit `--since` to process from the available historical start.
The command uses at most the global budget, divided across the selected pairs,
with transactions capped at 200 candles. A quota can span several transactions.
Defaults come from active configured
symbols/timeframes; paused scopes are skipped. No downloads/restarts are started.
Pending Section 4 replay is reported explicitly and blocks the affected pair.

History is stored in `Section_1_Global_Core/memory_storage/Storage/intelligence.db`.
Different source/config/seed runs are retained with minimal immutable input
bundles and archived classifier/config source. Corrections outside the normal
feature-generation/policy-epoch pipeline require a new explicit `--revision`.
Do not label an old run current after out-of-band source edits. Historical results
are reconstructions with actual computation times, not proven live publications.

## Automatic runner integration

Regime and the [Structure state adapter](STRUCTURE_V1.md) now run through
`Section_1_Global_Core.analytical_processor` in the existing processor registry,
after features and decisions. One bounded shared turn visits active pair/engine
scopes round-robin (200 rows total, at most four visits, .20s soft time budget
checked between visits). There is no new downloader, daemon or unbounded loop.
Unavailable Section 4 inputs remain blocked; automatic processing also waits for
the latest closed-candle feature checkpoint so an old feature prefix is not
seeded as current analysis. Analytics never gate DI event progress.

For each source/config/pair, automatic processing saves a fixed seed from the
latest 32 committed closed candles, then resumes from its own checkpoint as new
candles close. The seed does not move each cycle. It is a recent classification
run, not a claim that every old candle has already been classified. Full historical
research runs and their earlier snapshots remain separate and preserved.

After pulling, use `python3 restart_runner.py`. No manual research command is
needed to keep these engines working. For inspection only:

```bash
python3 run_regime.py --automatic --symbols BTCUSDT --intervals 15m --summary --diagnostics
python3 run_regime.py --automatic --engine STRUCTURE --symbols BTCUSDT --intervals 15m --summary --diagnostics
```

The chart and BUY/SELL, confidence and opportunity consumers are unchanged.
Structure 1.1 consumes confirmed producer pivot/BOS/CHOCH events, including IDs
and origin/known times. Missing lineage or unavailable old break references remain
explicitly partial; candidate fields never substitute for confirmed events.

## Trend v1

[The Trend specification](TREND_V1.md) defines direction, strength, persistence
and structural alignment separately. It consumes existing shared indicators and
a versioned same-candle Structure result. It adds no Section 4 columns, UI
overlays, downloads or BUY/SELL filters. The existing analytical processor now
rotates Regime → Structure → Trend under the same shared work limits.

Dependency work counts inside the row budget. A Structure backlog blocks the
corresponding Trend point; a real unavailable/warming Structure classification
permits explicitly marked measurement-only output with reduced coverage.
Every Trend record retains the exact upstream result reference and a minimal
immutable dependency projection. Regime/Structure code and configuration remain
unchanged, and their existing runs are preserved.

After pulling, restart the normal runner. No repeated manual command is required.
For optional inspection:

```bash
python3 run_regime.py --automatic --engine TREND --symbols BTCUSDT --intervals 15m --summary --diagnostics
```

The command's legacy filename is retained; `--engine` chooses the classifier.
Thresholds are experimental and evidence confidence is not a win probability.

## Momentum v1

[MOMENTUM_V1.md](MOMENTUM_V1.md) defines the independent Momentum classifier.
It reuses RSI, ROC, ATR-normalized displacement/change, signed DI dominance,
confirmed DI turns and price-linked DI anchors. MACD is optional and disabled
by default. Direction, strength, acceleration and condition are separate outputs.

The existing runner rotates Momentum under the same shared budget. It creates
no Section 4 columns, downloader, daemon, chart overlay or BUY/SELL filter.
Other engine algorithms/configuration are unchanged. Directional confidence is
rule evidence, not a win probability. Future/malformed DI turns cannot confirm
exhaustion, and missing anchor history remains explicitly partial.

Pull and restart the runner once. For optional inspection only:

```bash
python3 run_regime.py --automatic --engine MOMENTUM --symbols BTCUSDT --intervals 15m --summary --diagnostics
```

Historical source publication times remain reconstructed; results retain exact
projected inputs and original confirmed anchor timestamps for audit/replay.

## Volatility v1

[VOLATILITY_V1.md](VOLATILITY_V1.md) defines direction-free relative level,
expansion/contraction, return skewness and prior-ATR shock dimensions. The
existing runner schedules it under the same bounded analytical work budget,
with persistent source/config-specific state and immutable historical inputs.
No Section 4 calculation/column, downloader, chart overlay or trading policy
is added. Earlier engine algorithms/configuration and runs are preserved.

Percentiles require their full prior baseline. Other dimensions can be available
while that baseline warms; zero-variance skewness and positive motion against
a zero prior ATR stay explicitly unavailable. Complete observed flat movement
has a separate absolute-zero rule, not invented percentile history.

Pull and restart the runner once. Optional inspection only:

```bash
python3 run_regime.py --automatic --engine VOLATILITY --symbols BTCUSDT --intervals 15m --summary --diagnostics
```

High volatility is not automatically a shock, bullish signal or bearish signal.
The experimental evidence scores are not probabilities or profit estimates.

## Participation v1

[Participation](PARTICIPATION_V1.md) is runner-connected independently per active
coin/timeframe. It reuses shared RVOL, volume change and price progress. Aggressor
dominance stays UNKNOWN without matched observed flow; candle-only coverage is .75
at most. No BUY/SELL, confidence/opportunity or UI rules are changed.

## Phase v1

[Phase](PHASE_V1.md) consumes exact persisted Trend, Structure and Participation
outputs plus existing range/volatility measurements. It tracks a preceding trend,
a frozen range and later corroboration before calling a cycle hypothesis; structural
confirmation, failed breakouts, invalidation and expiry have separate known times.
The normal bounded runner saves independent history for active coins/timeframes.

## Liquidity v1

[Liquidity](LIQUIDITY_V1.md) separates inferred locations/sweep outcomes from fresh
observed execution and derivatives context. The existing perpetual recorder is a
read-only input; spot/perpetual association requires explicit basis/freshness checks.
Unknown historical books stay unknown. The normal runner persists independent
results and minimal immutable inputs without changing chart display.

## Sentiment v1 (partial derivatives sources)

[Sentiment](SENTIMENT_V1.md) independently classifies indicative funding tilt,
point-to-point funding stability and observed leverage/liquidation risk from the
existing recorder. It is explicitly derivatives-only; crowding, normalized extremes,
news and social sources remain unavailable. Fixed full-source coverage caps this v1
at .40. The normal runner persists exact source evidence without UI/trading changes.

## Multi-Timeframe Aggregator v1

[Aggregation](AGGREGATION_V1.md) is runner-connected per public engine family.
It preserves horizon conflicts, full configured evidence budgets, actual publication
availability and source scope. Core stores deduplicated input references separately
from base-engine history. Optional inspection: `python3 aggregate_market.py --engine TREND --summary`.

## Bias v1

[Bias](BIAS_V1.md) completes the first-version synthesis layer. It consumes exact
same-candle public outputs, caps correlated Trend/Structure evidence, distinguishes
risk from preference, and reserves missing independent-sentiment coverage. It never
issues BUY/SELL or replaces Section 9 confidence. The normal runner saves Bias
history; MTF aggregation can consume Bias outputs without a circular dependency.

## Completion diagnostics and optional sources

See [operational readiness and causal outcome research](../MARKET_INTELLIGENCE_READINESS.md)
and [Sentiment 1.1 optional news/social](SENTIMENT_V1_1.md). Optional providers remain
disabled until explicitly configured; implementation does not establish profitability.

Transient market-data writer contention in analytical maintenance is deferred to the
next runner turn, preserving the scope cursor rather than waiting a full universe
rotation. The repeated waiting status is logged once; it is not an engine exception
traceback. This does not bypass the shared writer lock or feature-generation gates.
