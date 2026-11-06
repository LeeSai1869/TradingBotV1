# BTC one-hour candidate and DI sequence study

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

Publishing requires branch `main`; only the generated report is staged/committed.
No databases, credentials or account records are included. A changed feature
generation/config or inconsistent frozen outcome stops the study instead of
mixing incompatible data. Earlier uploads contain all pivot outcomes and aggregate
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
