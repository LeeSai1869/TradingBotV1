# Strategy inputs and deferred memory pruning

13 November 2026. The first BTC 1h overlap replay failed after costs; no candidate
below is described as a validated trading edge. See
[the exact-pair study](research_reports/BTC_1h_spot_overlap/README.md) and
[the failed causal prototype](research_reports/BTC_1h_spot_overlap/PROTOTYPE_RESULTS.md).

## What can be used now?

| Family | Current use | What it cannot establish yet | Storage decision now |
|---|---|---|---|
| Canonical OHLCV and candle times | Price response, executable next-open replay, continuity and outcome checks | Intrabar ordering of an hourly stop and target | Retain the canonical raw source |
| ATR/NATR, range and extension | Whether 1% has plausible room; normalize distance and risk | Direction or a safe reversal by themselves | Retain as research and risk inputs |
| RVOL/volume and price progress | Activity and participation context | Actual aggressor flow or guaranteed demand | Retain; preserve volume validity and denominator semantics |
| DI+, DI-, signed/absolute spread, ADX, RSI | Pressure state, independent turn events, recovery/exhaustion hypotheses | Universal entry conditions or independent votes from every correlated derivative | Retain the base measurements while testing their incremental contribution |
| Previously known S/R, EMA/value location, range boundaries | Where a pullback/reversal might make sense; overhead barriers and invalidation | A final low/high identifiable before its recognition time | Retain provisionally; require current compatible replay for structure-derived fields |
| Candidate pivots | Developing location and changes in the current extreme | A guaranteed final pivot or an automatic BUY/SELL | Research/watch context only |
| Confirmed native pivot events | Historical outcome labels, recognition-delay and big-swing recall measurement | An executable fill at the retrospective extreme | Retain lineage and origin/known times for validation |
| Section 5 Regime/Trend/Volatility/Participation | Independent market context for different setup branches | Full-history conditional advantage before compatible coverage exists | Calculate/reuse; do not invent missing classifications |
| Section 5 Structure/Phase/Bias | Hierarchical interpretation and conflict/risk context | A substitute for a causal entry/exit rule or a calibrated profit probability | Retain experimental outputs with their coverage and dependency references |
| Observed liquidity/derivatives/sentiment | Additional context where matching observations actually exist | Historical books/news/social data that were never recorded, or direct spot execution measurements from unmatched perpetual data | Preserve scope/freshness; do not make missing external data a universal gate |
| ADCN active decisions, rule state and immutable signal evidence | Alternation, restart continuity, signal history and reproducibility | Proof that the present DI rule is profitable | Retain until the chosen strategy and migration are established |
| Archived Section 6/7 scores and retired interpretation fields in ADCN | Compatibility and older research only where a consumer still needs them | Evidence for the new strategy merely because the column exists | First candidates for a later consumer/dependency audit; no deletion now |

The likely common foundation is location + room/activity + pressure change +
observable price acceptance + execution/risk. Separate pullback, exhaustion and
range hypotheses can use those families in different directions and sequences.
Requiring every correlated measurement simultaneously already excluded most
qualifying historical swings and did not yield a profitable first prototype.

## Establish usefulness before deleting fields

Freeze a causal strategy and its validation window. Compare the full strategy
with one feature family removed at a time, using the same eligible dates,
position rules, costs and missing-data policy. Measure net expectancy, drawdown,
entry delay, turnover and large-swing recall. A feature can remain necessary for
risk, a dependency, chart display or reproducibility even if it does not improve
the BUY trigger's win rate.

Then build a per-field retention manifest with producer, active readers,
dependent calculations, historical versions and a restore path. Fields in a
failed prototype are not automatically useless; fields associated with large
hindsight swings are not automatically useful live inputs.

The current ADCN schema still exposes older columns through broad read contracts.
The active rule writer deliberately sets `final_score` to NULL; it does not
calculate the retired Section 6/7 scoring engines. Removing those columns needs
a reader/schema migration, not just a list of fields to stop calculating.
Retain rule checkpoints and signal evidence independently of retiring scores.

Choose whether to stop new writes, archive old generations, rebuild a compact
table, or remove a derived column only after that audit. Reclaiming SQLite file
space is a separate storage operation with its own disk/time requirements.
This review authorizes no data deletion, database rebuild or VACUUM. The user's
chosen sequence remains strategy first, memory pruning later.

## Why Regime appeared slow

Read-only replay of 2,048 mature BTC 1h Regime input bundles took about
0.084 seconds, approximately 24,400 classifications/second on this machine;
all replayed outputs had VALID input coverage.
That excludes production writes, source setup and scheduler waiting. Reading
the next 200 source projections took about 0.014 seconds in that measurement.
The expensive feature indicators were already reused, not recomputed by Regime.

The observed runner logs instead showed an older `downloads/features` scheduler
stage and repeated zero analytical maintenance. Source/features and intelligence
also used different historical ownership queues, and history previously received
only the live row budget's remainder. A focused historical queue, independent
bounded live/history allowances, dependency-cache invalidation and batch timing
logs address those operational causes without changing the classifier formulas.

Live verification also found the chart alert worker holding the market writer
lock across candle/context reads. The read preparation now uses the reader
guard and revalidates policy and rule revision before its short commit.
After the approved service restarts, live and historical BTC classifications
are advancing. The current 200-row historical batches spend most measured time
in their commits rather than the Regime formula.

Completion of stored history remains distinct from predictive validation and
from full external-source coverage.
