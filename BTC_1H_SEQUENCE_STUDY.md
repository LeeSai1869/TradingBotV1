# BTC one-hour candidate and DI sequence study

For configurable AND/OR rules over **every candle**, with multiple strategy
branches, alternating BUY/SELL trades and revision/failure comparisons, use
[`analyze_btc_hour_strategy.py`](analyze_btc_hour_strategy.py) as documented in
[`BTC_1H_STRATEGY_ANALYZER.md`](BTC_1H_STRATEGY_ANALYZER.md). The pivot/candidate
comparisons below are a separate descriptive research workflow.

Run from the project folder on the Mac holding the market databases:

```sh
git pull --ff-only origin main &&
python3 study_btc_hour_sequences.py --push-report
```

This reads the existing BTC 1h 1% native-pivot report, exports every closed 1h
candle in that frozen cohort, and analyzes every pivot. It does not recalculate
features or change live strategy rules, checkpoints, runner scheduling or app UI.
SQLite reads use snapshots; a long export can temporarily retain WAL pages while
the runner continues writing. The process lowers its CPU priority where supported.
Python's standard library is sufficient.

Each completed artifact is immediately committed and pushed independently under
`research_reports/BTC_1h_sequences/`:

- `source_v1.json.gz`: row-level candles, candidate measurements, DI values,
  archived scores and available compatible engine histories.
- `analysis_v1.json.gz`: every pivot, every active candidate observation,
  independent event sequences, grouped outcomes and context coverage.
- `analysis_v1.html`: full-cohort comparison tables and a paginated every-pivot
  inspector with price and DI timelines. Open locally in a browser. Dates use PKT.
  Git publishing uses `analysis_v1.html.gz` to keep the full dashboard compact;
  `gzip -dk research_reports/BTC_1h_sequences/analysis_v1.html.gz` expands it.

Publishing requires branch `main`; only the generated report is staged/committed.
No databases, credentials or account records are included. A changed feature
generation/config stops the study instead of mixing incompatible data. Native
outcomes are checked against the exported raw path; discrepancies retain both
versions and are reported explicitly. Grouped results use the exported raw path. Earlier uploads contain all pivot outcomes and aggregate
feature profiles, but cannot establish per-candle joint event sequences.

## Comparisons

Candidate phase start, first stored observation of the final extreme, origin
candle close and native pivot confirmation are separate stages. A final extreme
is identified retrospectively. Candidate updates and abandoned candidates remain
in the data; candidate appearance is not an entry trigger. Both stored high/low
reference updates and simultaneous independent DI events are retained.

DI+ and DI− strict three-close turns reuse the experimental strategy's definitions:
before-peak value < peak value > after-peak value. Recognition is at the third
close, not at the middle candle. Absolute spread turns are measured separately;
their timing need not coincide. Earlier known turns and event lags are retained.
The raw production DI predicate is a separate comparison; it is not a position
simulation or a replay of eligibility/alternation rules.

Fixed descriptive spread bins are [0,5), [5,10), [10,20), [20,35), [35,40),
and 40 or higher. They are not optimized trading thresholds. Raw DI, signed spread,
normalized dominance and ADX remain available. Archived score fields are labeled
unverified historical measurements; the current DI rule does not produce a
calibrated DI probability or final score. Missing scores remain null.

The requested post-SELL interpretations are separate:

- DI+ dips and rises while retaining both comparison levels.
- DI+ loses DI−, or both DI− and absolute spread, then rises.
- Touches without a strict breach have their own category.
- Regaining the pre-dip DI+ value is measured separately from the first up-tick.

All strict down-runs are retained, including plateaus, gaps and runs without an
observed recovery. A brief dip means one or two declining bars; all durations
remain available. Recoveries are linked to native highs from both candidate start
and origin close, over both the next-opposite-pivot window and a fixed 12 hours.
While DI+ > DI−, absolute spread cannot exceed DI+. A spread crossing is therefore
not independent confirmation of a DI− crossing. Comparing DI+ with itself is not
a meaningful additional condition.

## Outcomes and market context

Native lows are BUY research points and highs SELL research points. Their 1%
outcomes until the next opposite pivot are retrospective swing labels. Separate
1/3/6/12-hour outcomes start at the next candle open for all active candidate
observations and DI+ recoveries. Incomplete windows and gaps are censored;
same-candle opposing target touches have unknown order. No position, fees, stops,
trailing exits or executable profits are simulated. Downward movement after a
high is spot exit/rebuy research, not short-trade profit.

Local, 4h and daily context uses exact last-closed candles from compatible,
versioned Section 5 histories. All ten engine histories are exported where
available. Comparisons include Regime, Trend, instrument Bias, Liquidity,
Volatility and Sentiment, with explicit historical coverage. Missing history is
not replaced with current classifications, neutral values or legacy labels.
Historical reconstruction of close-time information does not prove it was
published live at that time. Legacy labels remain separately labeled.

Section 5 Bias describes BTC; no industry/sector breadth source is supplied.
Industry bias is unavailable. Liquidity classifications retain their provenance
and venue/scope: inferred structural levels and observed book/derivatives data
are separate. Today's order book is never used to fill historical gaps.

Grouped comparisons include complete failures and censored cases as well as
1% hits, both across the whole history and by UTC calendar year. Overlapping
observations are correlated. Descriptive differences do not establish a validated
entry rule; a later chronological evaluation must test any selected rule.

Once exported, analysis can run without the market databases:

```sh
python3 study_btc_hour_sequences.py \
  --input research_reports/BTC_1h_sequences/source_v1.json.gz
```

## Four/five-condition combination filtering

The research CLI now writes a separate `combination_filter` dimension to
`combinations_v1.json` and a self-contained `combinations_v1.html`. Normal source
analysis also embeds this dimension in the full dashboard and JSON. Existing
single-condition, pivot, candidate and recovery comparisons remain available.
To reuse the already exported analysis without databases or rewriting it:

```sh
python3 study_btc_hour_sequences.py \
  --analysis-input research_reports/BTC_1h_sequences/analysis_v1.json.gz
```

Four fixed named conditions are ANDed for each research side:

1. Absolute DI spread is at least 10 indicator points.
2. Pressure-side DI dominates: DI− for BUY, DI+ for SELL.
3. Local 1h Trend direction is BULLISH for BUY, BEARISH for SELL.
4. Both last-closed 4h and daily Trend directions agree with that direction.

The five-condition version adds local 1h Regime `primary == TRENDING`. The higher
timeframe condition explicitly contains two required predicates; named condition
counts are not counts of independent evidence. These are fixed descriptive
assumptions, not selected or optimized trading thresholds.

`--combination-filters path/to/filters.json` accepts a nonempty list of definitions.
Each definition has a unique `id`, `side` (`BUY`/`SELL`) and exactly four or five
named `conditions`. Each condition contains a nonempty `all` list of predicates.
For example, the spread condition is:

```json
{"name":"DI spread","all":[{"field":"di.abs_spread","min":10,"max":35}]}
```

Numeric `min` is inclusive and `max` exclusive. Classification predicates use
`eq` or `in`, e.g. `{"field":"1h:REGIME:primary","in":["TRENDING","RANGING"]}`.
Allowed fields are `di.abs_spread`, `di.dominant`, and
`<1h|4h|1d>:<REGIME|TREND>:<primary|direction|strength_band>`. Unsupported fields
fail before any export. To write the full default definitions for editing:

```sh
python3 -c 'import json; from study_btc_hour_sequences import default_combination_filters; print(json.dumps(default_combination_filters(), indent=2))' > /tmp/hour-filters.json
```

Native-pivot stages and all active candidate observations have separate tables.
Candidate outcomes use next-open 12-hour windows without selecting eventual
native pivots. Each table includes unfiltered N, missing-data exclusions, eligible
N, matched N and nonmatching N; both unfiltered and same-required-data baselines
are retained. Native hit rates use HIT + NO_HIT only. Candidate means use complete
windows only; censored observations and zero-sample results remain explicit.

Missing required fields exclude a row even if another predicate already fails.
Per-field and per-reason exclusions overlap and must not be summed as disjoint
counts. UNKNOWN classifications, invalid quality and missing, stale or forming
context are unavailable, never neutral. VALID/PARTIAL engine classifications are
accepted only for the exact last-closed candle at each stage's knowledge time.
This remains reconstructed historical context, not proof of live publication.

UTC calendar-year rows use stage knowledge time (candidate observation close),
including years with zero matches. For absent native stages, origin close is used
only to place their missing-stage exclusions. Chronological matched observation
IDs are exported for audit. These inspected yearly slices are descriptive and
overlap; no untouched holdout or execution backtest is claimed. Open the separate
HTML directly; it has no external chart/CDN dependency.
