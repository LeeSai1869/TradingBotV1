# BTC 1h combination comparison

Reproduced from the existing `analysis_v1.json.gz` on main commit
`7c83f92ccffc55fe95884a27bd016b8ccc660514`. The original analysis and source were
left unchanged. New artifacts: `combinations_v1.json` (definitions, denominators,
exclusions, chronological groups and matched IDs) and `combinations_v1.html`
(offline comparison dashboard).

The default four-condition filters require spread >=10, pressure-side DI
dominance, aligned local Trend, and aligned last-closed 4h **and** daily Trend.
The five-condition filters additionally require local Regime TRENDING. See
`BTC_1H_SEQUENCE_STUDY.md` for the exact schema and configurable predicates.

| Cohort | Side | Total | Missing required data | Eligible | Matched, four conditions | Matched, five conditions |
|---|---|---:|---:|---:|---:|---:|
| Native candidate-start | BUY | 12,946 | 12,938 | 8 | 0 | 0 |
| Native candidate-start | SELL | 12,947 | 12,939 | 8 | 0 | 0 |
| All active candidates, next-open 12h | BUY | 36,386 | 36,352 | 34 | 0 | 0 |
| All active candidates, next-open 12h | SELL | 44,304 | 44,259 | 45 | 0 | 0 |

Both filter versions have the same eligible denominators in this export; the
extra Regime requirement adds no missing rows to those already excluded. Every
eligible observation fails at least one filter predicate. Zero matched samples
means rates and mean returns are **unavailable**, not 0% success or a negative
strategy result. No threshold was relaxed to manufacture a winning subset.

Every 2017–2025 chronological candidate slice has zero eligible observations.
Only 2026 contains jointly available context: BUY 34 eligible / 3,585 total,
SELL 45 / 3,824 total, with zero matched observations. The same-coverage baselines
have only 30 complete BUY windows and 37 complete SELL windows; the remaining
4 and 8 are censored. Reused higher-timeframe context and overlapping hourly
windows are not independent samples. This coverage cannot establish a historical
combination advantage. Compatible historical engine coverage is needed before
interpreting filtered performance.

## Why the eligible observations do not match

Among the jointly available candidate observations, daily Trend is NEUTRAL in
all 34 BUY and 45 SELL rows. Therefore every row fails the default requirement
for both higher timeframes to align directionally. This is a genuine available
NEUTRAL classification, not missing data. The higher-timeframe pairs are:

| 4h Trend / daily Trend | BUY observations | SELL observations |
|---|---:|---:|
| BEARISH / NEUTRAL | 30 | 40 |
| NEUTRAL / NEUTRAL | 4 | 5 |

For the five-condition version, individual predicate failures are:

| Named condition | BUY failures / 34 eligible | SELL failures / 45 eligible |
|---|---:|---:|
| Spread >=10 | 12 | 14 |
| Pressure-side DI dominance | 7 | 7 |
| Aligned local Trend | 24 | 37 |
| Aligned last-closed 4h and daily Trend | 34 | 45 |
| Local Regime TRENDING | 25 | 27 |

Failure counts overlap. These few recently covered rows do not justify optimizing
the gates. First obtain compatible historical context in an isolated research
profile, then rerun the same definitions. A later separately labeled comparison
can contrast strict higher-timeframe alignment with a neutral-permitted condition,
retaining its denominators and yearly slices; it must not be presented as a
validated improvement selected from this small cohort.

The JSON retains each required field's exclusions. Counts overlap: a row missing
both local and daily context is excluded once, with both reasons recorded.
Native stages remain retrospective comparisons; causal candidate observations do
not require native membership. UTC years refer to observation/stage knowledge
time, and are inspected descriptive slices, not untouched holdouts. No live
strategy, formulas, scheduling, checkpoints or market data were changed.

Reproduce without market databases:

```sh
python3 study_btc_hour_sequences.py \
  --analysis-input research_reports/BTC_1h_sequences/analysis_v1.json.gz
```
