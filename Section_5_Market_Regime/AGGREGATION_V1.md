# Multi-Timeframe Aggregator v1.0.0

Aggregate one public engine family across independently calculated timeframes.
Do not recompute indicators, turn classifications into BUY/SELL, or average several
small timeframes into a directional prediction that overrules a larger timeframe.
The pure implementation imports only its own immutable configuration.

## Input and publication contract

Core records which default normal-runner run supplied each symbol/timeframe/engine
scope. A changed run or known unavailable state creates a timestamped binding. An
unavailable/replaying generation blocks fallback to an older convenient run.
Versioned public source projections are indexed by run/publication observation time;
no full historical engine-result scan or index migration over old history is needed.
New sources keep exact stored result IDs/config/input versions. Source projections
omit wide measurements, but retain explicit context scope for derivatives-only
Sentiment and related-market Liquidity.

Actual mode uses bindings and indexed publications observed by the requested as_of.
Indexing starts with this release; results not observed before that point are
explicitly missing, even if older engine history exists. This conservative limitation
does not invent original availability. Historical research can opt into the separate
RECONSTRUCTED_CLOSE policy: today's compatible run and at most two index-bounded
candle-time rows select the last close known by the simulated time. Original actual
available_at remains visible with SIMULATED_CLOSE_AVAILABILITY_NOT_ORIGINAL_PUBLICATION.
The normal runner never enables that simulation policy.

Core rejects outdated producer code/config generations, changed data deletion epochs,
wrong feature generations, pending Section 4 replay and incompatible identity. The
producer fingerprint includes direct/transitive dependencies (e.g. Phase's Trend,
Structure and Participation) without importing their implementations into aggregation.
Per-timeframe dataset generations may legitimately differ; they are bound individually
rather than falsely required to share one hash. Aggregate identity has no timeframe;
its symbol epoch and the individually referenced scopes remain traceable.

Select the latest known result, then reject unusable data. Never search backward for
a valid pre-gap label after a newer invalid one. Only closed CONFIRMED-mode results
with VALID/PARTIAL quality and actual source knowledge <=as_of are eligible. By
default source confirmation status must be CONFIRMED; allowing PENDING is a separate
explicit policy. Candidates are never substituted for confirmed classification.
Exact source versions/configs must agree across the family; mixed cohorts are excluded.

## Registry, hierarchy and freshness

Read the existing configured timeframe registry; there is no fixed timeframe list
or maximum embedded in the pure aggregator. Core supports registry unit descriptors
s/m/h/d/w/M. Calendar-month advancement uses actual UTC month lengths, including
leap years; 1M is not silently 30 days.

Defaults (research policy, configurable):

- Short: duration <=15 minutes; medium: <=4 hours; long: above 4 hours.
- Equal horizon importance among configured active groups.
- Equal timeframe importance **within** each group; positive per-timeframe overrides
  are supported, with exact registry-name validation.
- A result stays fresh through its next expected candle close plus 30 seconds of
  grace. Month boundaries advance calendrically from the source's actual close.
- Minimum full-scope coverage .50; minimum two admitted, non-UNKNOWN source states
  to assess multi-timeframe alignment.
- A horizon dimension needs >=.67 of its full configured group evidence budget to
  report a dominant state. Otherwise MIXED/UNKNOWN preserves uncertainty.

Disabled scopes stay in diagnostics but leave the configured budget. Missing,
stale, unconfirmed and incompatible **active** scopes keep their budget and contribute
zero. Equal groups mean ten minute-level timeframes cannot outvote one daily frame.
Evidence is not renormalized over the available subset. Each timeframe contributes
one latest result, not repeated bars treated as independent confirmation.

## Output semantics

Per-timeframe reports retain classification, context scope, exact source ID, known
and available times, age, coverage/confidence or an exclusion reason. Horizons retain
separate categorical dimensions and support. In particular Regime's behaviour,
direction and volatility remain separate; high volatility is not a bullish vote.

Pairwise structured conflicts retain dimension, timeframes/horizons, states and known
times. Opposite BULLISH/BEARISH `direction` values across horizons are COUNTERTREND,
with explicit shorter/longer timeframe references. Within a horizon they are
DIRECTIONAL_OPPOSITION. Other unequal categorical attributes are STATE_DISAGREEMENT;
phase/funding/strength labels are not secretly mapped into trading directions.

Overall alignment:

- UNKNOWN: insufficient full-scope evidence, too few timeframes/known states.
- CONFLICTED: adequate coverage but opposing directional states exist.
- PARTIALLY_ALIGNED: other state disagreements or missing active scopes.
- ALIGNED: adequate compatible evidence with no known-state disagreements.

No averaged overall_direction or BUY/SELL is produced. Overall coverage/confidence
is the sum of full-scope slot weights times admitted source coverage/confidence.
It is evidence availability, not statistical independence or win probability.
Sentiment's .40 source coverage cannot silently become full-source sentiment; its
partial scope remains visible. Confidence is never increased by missing inputs.

## Storage, normal processing and historical review

Core stores MTF bindings, deduplicated public source projections, immutable input
references, aggregation policy/source archives, results and latest pointers in the
existing intelligence.db, using separate owner-managed tables. Numerical engine
histories and schemas are unchanged. Exact input reconstruction resolves stored
references without reading current feature values. Atomic writes reject divergent
same-key results; source/config/policy changes produce traceable new generations.
Current-policy live and explicit historical queries have separate scopes.

The existing analytical runner may index and aggregate one family after a base-engine
visit, only when its existing row/time budget has space. Aggregate result rows count
inside that budget. There is no extra thread, loop over all families, or scheduler.
A deadline yield writes no incomplete matrix. Base results remain committed if
optional aggregation fails; aggregation never gates decision events or feeds back
into its own base classifiers.

Normal processing records only input/reference/exclusion changes, not an identical
matrix every timer tick. Expiry changes are recorded; raw age changes alone are not.
Manual inspection recalculates freshness at its requested time. No automatic deletion
of historical analytical or aggregation data is introduced.

After pulling, restart the existing runner; no manual command is required to populate
new aggregates. Optional inspection:

```bash
python3 aggregate_market.py --engine TREND --symbols BTCUSDT ETHUSDT --summary
```

The command reads stored/indexed results; it does not run missing base engines. Early
missing/replay/warmup states are expected until active scopes publish. Optional
`--as-of` uses actual observed availability. `--reconstructed-close` is explicitly
simulated historical availability, never a claim of original live tradability.

No UI, strategy, feature formulas, existing classifier rules, confidence/opportunity
rules or live recorder behavior changes. Bias remains a separate future per-timeframe
synthesis engine; aggregating its output later must not create a dependency cycle.
