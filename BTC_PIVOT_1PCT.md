# Every BTC pivot: 1% benchmark, five timeframes

The research anchor is the actual historical pivot, not an existing BUY/SELL
signal or its confidence score. Every native confirmed PIVOT_LOW is a BUY
research point; every native confirmed PIVOT_HIGH is a SELL research point.
The study CLI now defaults to 1%; explicit older 2% commands still work and
existing reports are preserved. The benchmark is **1% before the next opposite pivot**, independently for 15m,
30m, 1h, 4h and 1d. There is no recent-candle cap or sampling of the cohort.
Unavailable sources stop the batch explicitly; they do not produce invented data.

Run on the machine holding the historical databases:

```sh
python3 -m pip install -r requirements-research.txt
python3 study_btc_pivots.py --push-report
```

The coordinator freezes a common UTC cutoff at batch start. `--until 2026-11-05`
can reproduce the cutoff of the earlier uploaded 15m study. To study one timeframe
first, use `--timeframes 15m`; rerun others explicitly with the same cutoff if
comparing their periods. All requested sources must have a compatible committed
feature prefix and no pending feature repair. This command does **not** repair
or recalculate features. Completed earlier reports remain if a later frame fails.

## Each timeframe produces three files

In `research_reports/BTC_1pct/`:

1. `..._pivots_v1.json.gz`: every pivot and its outcome, first 1% touch, next
   opposite pivot, confirmation delay, coverage and censoring. For chart browsing,
   only three hit and three non-hit examples have full raw contexts embedded.
   **That example selection does not limit the all-pivot comparison below.**
2. `..._features_v1.json.gz`: statistics for every pivot's measurements from
   12 candles before through 24 candles after its actual origin. Every stored
   numeric feature is processed in bounded batches, plus raw candle geometry,
   ATR-normalized movement, volume, absolute DI spread, DI dominance and independent
   three-candle DI+ / DI− turns. Explicit low-cardinality categorical features
   have frequency tables. Non-numeric IDs/event payloads are listed as not
   averaged, not silently described as analyzed numeric information.
3. `..._features_v1.html`: offline interactive feature selector with HIT versus
   complete NO_HIT trajectories for pivot lows and highs. Hover each point for
   its available sample count. Annual comparisons, ranges, standard deviations,
   censored cohorts and categorical counts remain in the compressed JSON.

`--push-report` publishes each completed artifact immediately through the existing
report-only Git publisher. It expects `main`, stages only the report in question,
and stops on push failure. Original 2% and earlier 1% reports are not edited.
A repeated run with the same filename will update that report via a new Git commit;
use a different `--output-dir` to retain separate versions in the working tree.

The existing Analysis workspace pivot viewer accepts the new cohort files. Its
threshold labels follow the loaded report, including 1%. Any individual native
pivot can still request all stored feature values from the existing context API,
including the event/string payloads not averaged in the comparison.

## Comparison and timing contract

- Pivot origin is offset **0**. Values at 0 are available only when that candle
  closes. The exact candle high/low is a retrospective ideal price, not proof of
  an executable entry at that price.
- Negative offsets use their own closed-candle measurements. Positive offsets
  are explicitly later evidence. A DI peak centered on the preceding candle is
  marked confirmed only at the current candle close after all three observations.
- No simultaneous DI+ / DI− turns are required. Their events are independent.
  Candidate pivots remain contextual observations, never an automatic trigger.
- Benchmark touches use candles **after** the origin candle, retaining the source
  study's convention. The unknown high/low ordering inside the origin candle is
  not assumed. Separately, timing diagnostics count pivots where the origin
  candle's close had already moved 1% from its extreme: this identifies recovery
  already missed by waiting for that close. Native pivot prices are checked
  against raw candle highs/lows across the full cohort.
- HIT, complete NO_HIT and censored swings stay separate. First-touch timing and
  whether 1% had already happened by formal confirmation are retained.
- Every stored numeric field has available count, mean, population standard
  deviation, minimum and maximum at each offset, separately by side/outcome and
  year. Missing exact candles or incompatible feature rows never become zero.
- An annual comparison helps expose period differences, but does not control for
  volatility, prove causation, or provide an untouched validation period. In
  particular, volatile conditions make a fixed 1% excursion easier to reach.
- Independent local/4h/daily Regime and Trend histories are joined at the last
  closed candle before the pivot origin, and again at the pivot-origin close.
  Conditional classification counts and exact missing/partial coverage are
  retained in `engine_context`. No current or forming HTF state fills missing
  history; this step does not backfill/recalculate engine histories.
- Legacy regime/trend labels are explicitly legacy features. They are not a
  substitute for independently versioned Section 5 engine histories. Those
  histories still need sufficient coverage for a proper context comparison.
- Structure-related inputs retain the previously identified count>2 defect until
  the staged correction is independently deployed. They must not be promoted
  into a new trading gate just because a retrospective association looks good.

The output lets us examine what distinguishes useful turning points, the order
in which evidence develops, and what becomes recognizable before confirmation.
It does not automatically optimize a setup, apply rules, or claim an achievable
win rate. Promising sequences need replay with information available at the time,
then separate execution/fee/stop evaluation and chronological validation.

## Resource use and boundaries

NumPy is an optional **research-only** dependency, not added to the standalone
trading requirements. The comparison reads each numeric column batch across the
frozen source once, rather than exporting hundreds of duplicated full-feature
windows for each pivot. CPU priority is lowered where supported. Long SQLite read
snapshots and analytical processing still consume RAM/disk/CPU and may retain WAL
pages: use research memory/the spare laptop when possible. Memory is bounded by
one column batch, pivot-offset indexes, the source report and aggregate results;
it does not materialize a full pivots × offsets × all-features cube.

No runner scheduling, feature formulas, live BUY/SELL rules, confidence weights,
opportunity geometry, accounts or positions are changed. The only UI change is
correct threshold text within the historical pivot research panel.

Validation:

```sh
python3 -m unittest discover -s tests -p 'test_all_pivot_features.py'
python3 -m unittest discover -s tests -p 'test_pivot_*.py'
```

## ATR units in the first uploaded feature reports

The first exporter reused `atr_percent` for both the stored legacy ATR/close
fraction and derived 100*ATR/close percentage. This duplicated its group keys
and mixed scales in that one feature's visual curve. The source formulas and
other features were unchanged. The exporter now uses `atr_pct_of_close` for the
derived percentage, keeps legacy `atr_percent` as a fraction, and records unit
notes. Existing uploaded files remain preserved; the accompanying findings
analysis explicitly recovers the second, percentage-valued groups after verifying
identical sample counts and the 100x scaling relationship. No full candle replay
is needed to recover those numbers. Do not interpret the old mixed-scale
`atr_percent` plot as one consistent unit.
