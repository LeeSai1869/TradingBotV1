# Common engine contract — 1.0.0

## Identity and input snapshot

Identity is `(venue, market_type, instrument_id, timeframe, dataset_generation)`.
A display symbol is included but is not sufficient identity: spot and perpetual
BTCUSDT must not share state. Market metadata specifies quote currency, volume
units, calendar/session, candle convention and adjustment policy where applicable.
Stocks require a source/calendar adapter; this contract does not claim the current
crypto runner already supports stock sessions or corporate actions.

A snapshot contains:

- Candle open/close timestamps in UTC milliseconds, `closed` and `as_of`.
- Required canonical OHLC and measurements; volume only where required.
- Field-level validity, units, warmup/continuity, source identifier and version.
- Source event/origin time **and** known/available time, plus received time for
  observed external feeds. Only inputs known by `as_of` may be used.
- Public dependency outputs, their exact versions/config hashes/input generations.
- An immutable validated configuration and engine-owned previous state.

No engine accepts an unbounded candle table. Core provides bounded feature/output
snapshots. Rolling windows, normalization and reusable indicator computations are
Section 4 responsibilities. Engine state contains classification persistence and
interpretation-specific event sequences, not another ADX/ATR/EMA implementation.

## Result envelope

[result.schema.json](result.schema.json) validates the common envelope. Classification is a string
map whose permitted keys/values are specified in each engine contract. Engine
specific typed schemas will narrow measurements/evidence before runtime admission.

```json
{
  "contract_version": "1.0.0",
  "engine": "REGIME",
  "engine_version": "1.0.0",
  "state_schema_version": "1.0.0",
  "identity": {
    "venue": "binance", "market_type": "spot", "instrument_id": "BTCUSDT",
    "symbol": "BTCUSDT", "timeframe": "15m", "dataset_generation": "opaque-generation"
  },
  "candle_open_time": 0,
  "candle_close_time": 899999,
  "as_of": 900000,
  "available_at": 900010,
  "computed_at": 900010,
  "mode": "CONFIRMED",
  "classification": {"primary": "UNKNOWN", "direction": "UNKNOWN", "volatility_level": "UNKNOWN", "volatility_change": "UNKNOWN", "stability": "UNKNOWN"},
  "candidate_classification": {"primary": "UNKNOWN", "direction": "UNKNOWN", "volatility_level": "UNKNOWN", "volatility_change": "UNKNOWN", "stability": "UNKNOWN"},
  "strength": null,
  "confidence": 0.0,
  "coverage": 0.0,
  "data_quality": "WARMUP",
  "quality_flags": ["INSUFFICIENT_HISTORY"],
  "measurements": {},
  "confirmation": {"status": "UNAVAILABLE", "candidate_bars": 0, "required_bars": 3},
  "previous_state": {},
  "evidence": [],
  "config_hash": "opaque-config-hash",
  "input_signature": "opaque-input-version-hash",
  "provenance": {"mode": "LIVE", "source_versions": {}, "dependency_results": []}
}
```

Times above illustrate units/ordering, not market readings. `mode=CONFIRMED` means
the input candle is closed and the result is committed; it does not assert that
a non-UNKNOWN classification has completed confirmation. The separate confirmation
status expresses that distinction. `PROVISIONAL` results are never committed to
confirmed history or fed into a confirmed downstream engine.

`classification` is the confirmed state. `candidate_classification` is the current
closed-candle proposal (or the preview proposal in PROVISIONAL mode). A candidate
can differ while the confirmed state remains unchanged. `previous_state` records
the prior confirmed classifications/change time, not a duplicated raw checkpoint.

## Strength, confidence and missingness

- Strength: [0,100], magnitude of the measured property; nullable when unavailable.
- Confidence: [0,1], transparent rule-evidence/quality score, **not** win probability.
- Coverage: [0,1], valid input coverage against the full declared input budget.
- Data quality: VALID, PARTIAL, WARMUP, GAP, STALE or INVALID.
- Confirmation: CONFIRMED, PENDING or UNAVAILABLE. Required/candidate bars are
  explicit, not a misleading single `confirmed` boolean.

Each engine must publish scoring components, weights, neutral thresholds and
coverage rules before implementation. Optional missing sources reduce coverage;
renormalization must not turn a tiny available subset into high confidence.
Correlated features share a capped evidence family. A high internal consistency
score is not proof of predictive usefulness. Phase scores are not probabilities
until separately calibrated.

Missing required inputs yield UNKNOWN for the affected dimension, null measurement
values and explicit reason codes. A previous valid label may be reported as
historical `previous_state`, but must not be carried forward as fresh confirmed
knowledge through a gap. Partial independent dimensions may remain valid if their
own inputs are complete. Neutral and zero are legitimate measured values, not
synonyms for missingness. No NaN/Infinity may cross a public/JSON contract.

## Time and causality

Origin time is not knowledge time. A pivot at t can only influence a classification
when its confirmation becomes available. A later sweep confirmation is a new event;
it cannot rewrite a prior potential-sweep event as though confirmation existed then.
No negative shifts, centered windows or retrospective phase relabeling are allowed.

`available_at` is when the output actually became available; `computed_at` is its
calculation time. Historical reconstruction performed today must not pretend it
was published at the original candle close. Use provenance HISTORICAL_RECONSTRUCTION
and actual computation/availability timestamps. Backtests may simulate causal
availability at `as_of` only as an explicit assumption based on known-time source
records. Where original source publication times are absent, mark
AVAILABILITY_RECONSTRUCTED and do not claim a real-time tradable backtest.

Closed candles replay in canonical chronological order. Calendar-aware source
close times govern monthly/weekly/session boundaries; fixed milliseconds are not
a substitute for registry/calendar metadata. Missing, duplicate, out-of-order and
corrected input handling is specified before an engine is admitted.

## Versioning, persistence and replay

Core owns a logical `engine_results` history with per-engine views/tables as needed.
Do not create ten physical databases. Preserve the current candle/feature/ADCN
contracts; analytical history is not a reuse of legacy `final_score` columns.

Proposed result key:
`identity + candle_open_time + engine + engine_version + config_hash + input_signature`.
`input_signature` identifies source/formula/dependency generations, not a hash of
every historical candle copied into each row. Use per-row lineage references and
raw-data correction generations. Same semantic version with different parameters
must never collide. Same key with a differing deterministic result is an error;
volatile diagnostic/computed timestamps are excluded from deterministic comparison.

Checkpoint key additionally identifies state-schema version and the run. Core
commits output rows, progress and engine state atomically. Interrupted replay resumes
without duplicate rows/events. Configuration/source changes repair only affected
features, engines and downstream dependents. A stateful classifier may need replay
from its valid seed, not just the changed row. Unchanged feature columns are reused.

Preserve old runs for comparison until an explicit dependency-protected retirement
is approved. UI preferences never trigger recalculation. No engine-history schema,
Core adapter or new replay job is implemented by this contract-only release.


## Existing-store reproducibility gate

The current selective feature repair updates affected columns in place. An input
fingerprint alone does not preserve old numerical values. Before claiming exact
historical engine reproducibility, Core must retain the relevant versioned
configuration/code plus replayable raw-data generations, or an immutable projected
input bundle referenced by results. Corrected raw candles and external revisions
also need lineage. Do not copy the entire wide feature packet into every engine
row. Choose and test the minimal lineage strategy before persistence admission.

The JSON Schema validates shape/enums/ranges, not cross-field causality or engine
mathematics. Implementations must additionally check time ordering, registry
identity, compatible dependency versions, per-dimension validity and deterministic
state. Strict JSON parsers/writers must reject NaN/Infinity.
