# Calculation and historical storage policy

## Purpose and ownership

Calculate what the application needs. Permanently retain only values with an
identified historical consumer, evidence requirement, or measured economic reason
to avoid recomputation. Keep raw candles in `klines.db`, retained shared feature
history and calculation checkpoints in `features.db`, and Section 5 analytical
results and decision/evidence history in `ADCN.db`.

## Retention choices

| Treatment | Use when |
|---|---|
| Historical measurement | Current historical decisions, analytics or chart queries require the value, and repeated reconstruction is sufficiently expensive or slow |
| Event/change record | A pivot, zone, structural transition or lifecycle changes; preserve origin and recognition/availability times |
| Recent cache | Current displays require low latency, but indefinite historical persistence is unnecessary |
| Calculate on demand | A consumer needs a cheap transformation of retained inputs; calculate inside that consumer and persist only its justified final output |
| Canonical value only | Multiple names represent exactly the same value; adapt names at an interface instead of persisting duplicate values |

An expensive calculation is not automatically a reason for per-candle storage.
Measure its expected request frequency, reconstruction span, latency and cache
reuse. An expensive intermediate used only during a new candle's calculation can
remain transient if the owning engine checkpoint preserves enough state.

## Individual field review

For each candidate, record its producer, canonical name, formula/config version,
units, UI consumers, backend consumers, decision consumers, historical research
consumers, selective-replay dependencies and availability semantics. Dynamic
queries and configurable outputs count as consumers even without a literal field
reference in source code.

Measure populated frequency and actual storage contribution, calculation CPU
time, required lookback/state, expected access frequency and acceptable latency.
Choose historical retention, event storage, a bounded recent cache, on-demand
calculation, or retirement. Record the rationale and the reconstruction/restore
path. Do not substitute a new formula's reconstructed values for old published
evidence without preserving the distinction.

Retain original observations that cannot be reconstructed from candles. Preserve
stateful indicator initialization, checkpoints, gap handling, confirmed-event
lineage and recognition times. Selective replay must be adapted and tested before
removing intermediate historical values that it currently hydrates from storage.

## Alias retirement

First enumerate explicit non-identity alias mappings. Verify exact equivalence
under current calculations and inspect older formula versions for independently
populated or conflicting values. Trace SQL projections, dictionaries, configurable
UI outputs, alerts, engine input contracts, exports and replay paths.

Migrate internal consumers to canonical names or provide an explicit read-boundary
adapter. Preserve independently meaningful historical values until equivalence
has been established. Test both old database rows and newly written rows, then
stop duplicate writes and migrate existing storage. Remove physical alias columns
only after supported readers and writers can operate without them. A compatibility
name may remain in an API without another stored value.

Do not remove a same-named decision field from ADCN merely because a feature alias
has that name; ownership and semantics must be checked separately.

## Rollout and verification

Use bounded, resumable data changes with read-back verification, progress markers,
and a recovery path. Check application displays, alerts, Section 5 inputs, decision
outputs, restart continuation and selective replay. Coordinate service reloads
when necessary; do not silently activate a storage format that running readers
cannot interpret.

Logical retirement, reusable SQLite pages and physical disk reclamation are
different outcomes. Report them separately. A full database rebuild or VACUUM
requires its own working-space and availability assessment.

## Current review scope

The first review covers the 26 explicit non-identity feature aliases. The earlier
552 fields with no named consumer found form a preliminary candidate list, not a
safe-deletion list. Review those fields individually only after alias retirement.
No blanket removal of those fields or their calculations is authorized by this
policy.

### Verified alias storage implementation

The semantic audit verified 24 mappings; the two `swing_pivot_*_confirmed`
fields have absent canonical counterparts and remain independent stored columns.
The 24 verified aliases are represented by SQLite **VIRTUAL generated columns**:
their public names remain queryable, but their values occupy no per-row storage.
Writers inspect `table_xinfo` and write physical columns only. Consumer schema
discovery also uses `table_xinfo` so generated names remain visible to existing
UI, alert, engine and replay contracts.

The retirement tool checks every original row for conflicting populated pairs,
backfills canonical NULLs from legacy alias values, copies the canonical values,
and verifies all stored fields and checkpoint tables before replacing the file.
A conflicting pair aborts retirement. The original file is retained through
cutover and new-write verification. Storage-only retirement changes neither the
indicator formulas nor the calculation version. Historical version tags remain.
