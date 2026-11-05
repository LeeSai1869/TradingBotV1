# Regime, Trend, Confidence and Opportunity research

`audit_pivot_context.py` reads an existing next-opposite-pivot study. It never
starts a feature replay, writes a market database, changes a trading rule, or
rebuilds decision evidence. It runs at lower CPU priority on macOS/Linux. A long
SQLite read snapshot can retain WAL pages while the runner writes; run the full
study on the research machine/a consistent database copy when possible. Read-only
does not mean free of CPU, disk or memory cost.

## Full pivot comparison on the machine holding the database

```sh
python3 audit_pivot_context.py \
  --report research_reports/BTCUSDT_15m_all-history_2pct_pivots_v1.json.gz \
  --output research_reports/BTCUSDT_15m_regime_trend_confidence_opportunity_v1.json.gz \
  --push-report
```

There is no default 1,000-case limit. `--max-cases 1000` is an optional smoke run
and explicitly marks the output as a truncated prefix. Both the compressed JSON
and companion HTML are committed/pushed separately by `--push-report`, using the
existing report-only publisher. It expects `main` and never stages databases or
unrelated changes. A push failure leaves the report saved and returns failure.
Open the `.html` file in a browser for visual group comparisons and expandable
case details. No chart backend restart is required. Every audited case remains
in the JSON; HTML embeds aggregate tables and the first 40 case details.

The report and current feature generation/config must match. If they differ,
regenerate the source study instead of quietly joining repaired measurements to
old outcomes. The original source report is retained. No recalculation is
started by this audit when any source is unavailable.

## Actual saved BUY/SELL scores and bands

```sh
python3 audit_pivot_context.py \
  --report research_reports/BTCUSDT_15m_all-history_2pct_pivots_v1.json.gz \
  --saved-decisions \
  --output research_reports/BTCUSDT_15m_saved_decision_accuracy_v1.json.gz \
  --push-report
```

This is a **different cohort** from selected pivots. It reads immutable ADCN
snapshots for the current epoch and current Confidence/Opportunity model versions.
It preserves the original scores and Opportunity inventory/bounds exactly.
Snapshot count, excluded outdated/malformed anchors and stored decision row count
are reported. Empty/partial evidence is not silently reconstructed or treated as
complete coverage. These counts need not match: ADCN can have missing evidence
or retrospectively reconstructed snapshots. Snapshot provenance/recorded times
are retained; this is not proof that the live user received that score at the
historical time.

Measurement starts at the next candle open. For each signal, the horizon ends at
the next opposite native pivot whose origin is at/after that measurement start.
Missing endpoints are censored at the frozen source report cutoff. A signal's
own native opposite pivot can predate recognition, so this rule is explicitly
different from using the subsequent opposite *signal*. Neither scope simulates
positions, a 0.5% stop, trailing stops, fees, capital, fills or spot execution.
SELL means evaluating a spot exit/rebuy decline, not a short return.

## Temporal and vocabulary rules

- Independent Section 5 REGIME and TREND results are used, never relabeled legacy
  features. `legacy_regime` and `legacy_trend_maturity` remain separate diagnostics.
  The latter's FRESH/MATURE/WEAK states are not bullish/bearish direction.
- Record context immediately **before the pivot-origin candle opens**, and again
  at **recognition candle close**. The origin is a retrospective label, not an
  entry trigger. Scores/DI events use recognition inputs and their predecessors.
- At each instant, use the exact latest fully closed local, 4h and daily candle.
  A 15m recognition at 15:30 UTC can use the 08:00–12:00 4h candle, not the still
  forming 12:00–16:00 candle. A recognition exactly at 16:00 can use 12:00–16:00.
- Select the current indexed normal-runner producer/version/source generation.
  Never substitute a conveniently available old run, a stale prior candle or a
  current HTF classification for missing history. Missing states stay UNKNOWN.
- Histories computed later are explicitly HISTORICAL_RECONSTRUCTION. Closed-time
  information availability is different from actual publication time. This is
  not an as-actually-published trading replay.
- Classifications, source/run identifiers, quality, coverage, timestamp and score
  are retained for each join. PARTIAL quality remains explicit.

## What is measured

The portable HTML shows local/4h/1d regime and trend groups, joint contexts,
alignment, independent three-candle DI+ and DI− events, and confidence bins.
All groups retain side and calendar-year comparisons. Missing/unresolved outcomes
are separate; the resolved fraction's 2% hit rate is not a trading win rate.
Overlapping swings/events are dependent and a resolved fraction can be selected
by censoring. No group is automatically promoted into a live gate or strategy.

Confidence bins are /100 **evidence scores**, not calibrated probabilities.
Continuation and reversal modes are reported separately, with family breakdowns,
coverage and readiness. At reconstructed pivot points only, a diagnostic also
removes the structure family and measures score sensitivity. This is not a
corrected score or a replacement for the proper feature repair. Saved scores
are never changed by this diagnostic.

Opportunity areas are frozen at the recognition/decision anchor. The audit
reports native versus modeled geometry, distance, touch, no-touch, gap crossing
and censored windows. A gap past an area is not an observed touch. Rejection and
breakthrough excursions begin on the **candle after** the first touch, excluding
the unknown ordering inside the touch candle; these are movements relative to
band edges, not executable returns. Both can occur in the same window. No
unvalidated threshold converts those measurements into a claimed success.

Pivot-point Opportunity reconstruction uses scalar stored features and explicitly
**does not recreate the full historical persisted zone inventory**. Use saved
snapshots to evaluate the bands the app actually displayed. An absent layer is
missing geometry, not an incorrect prediction. A touched region need not reverse
price, and a 2-ATR-distant area need not be reached in a short swing.

## Available uploaded sample

```sh
python3 audit_pivot_context.py \
  --report research_reports/BTCUSDT_15m_all-history_2pct_pivots_v1.json.gz \
  --embedded-only \
  --output research_reports/BTCUSDT_15m_embedded_context_audit_v1.json.gz \
  --push-report
```

This opens **no market database** and audits only the 40 exported examples.
They were deliberately sampled from retrospective hits and non-hits; they are not
representative and cannot establish calibration or model accuracy. The uploaded
report contains no independent REGIME/TREND histories for local/4h/daily joins;
these remain unavailable until the full database-backed run is supplied.

## Structure correction: staged, not installed

`research_fixes/structure_latest_types.patch` changes the latest-high/latest-low
classification checks from count == 2 to count >= 2. Regression tests reproduce
the old failure at 3, 4 and 20 pivots and verify bearish/bullish/range handling
under the staged correction, including the original two-pivot foundation.

**The runtime producer is intentionally not modified.** Installing the patch
changes feature lineage and requires historical repair. Do that on research
memory, compare results, and prepare a deployment/migration separately so a simple
pull does not force the live runner through years of replay. This patch is not
a complete validation of structure age/origin semantics or all transition paths;
those still need historical inspection with corrected memory.

Validation:

```sh
python3 -m unittest discover -s tests -p 'test_pivot_context*.py'
python3 -m unittest discover -s tests -p 'test_structure_latest_types_preview.py'
git apply --check research_fixes/structure_latest_types.patch
```
