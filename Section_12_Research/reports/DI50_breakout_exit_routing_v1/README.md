# DI50: ordinary rebounds versus breakout trailing exits

**Cost assumption superseded:** this historical run used approximately 0.12% total costs. The user specifies **0.2% total round-trip costs**, so +0.5% gross gives +0.3% net. Use the [corrected cost comparison](../DI50_breakout_exit_routing_cost20bps/README.md) for current results. The tables below retain the original run for auditability.

The same 38 BTC and 11 SUI strict bearish-Trend 15m entries are retained. This is an exit experiment, not a new entry strategy. The eight rows in the earlier partial-memory table were eight coins, not the lifetime trade count. The strict simultaneous DI peaks/DI+ trough are rare; these counts do not count every market pivot or 1% move.

## What changed and what the evidence supports

Ordinary exits are now explicitly **+0.5% or +1% gross chart-price gain** from the raw next-open entry. Under the assumed 4 bps fee and 2 bps slippage per side, they net **+0.37947%** and **+0.87887%**. The prior +1% target was net; its equivalent raw price rise is about 1.1213%. Every entry retains the initial 0.5% net-loss stop. No fixed holding timeout, stop removal, discarded loss or future-known classification is used.

The +0.5% gross exit raises BTC win rate to 50.0% under low-first, but its average net return is **−0.0603%**. Its break-even win rate is about **56.85%**, assuming every loss is exactly −0.5%. More wins alone do not make it profitable. SUI rises to 54.55% and also remains slightly negative under that path. The +1% gross control yields BTC 36.84% wins and +0.0080% mean net; SUI 45.45% and +0.1268%.

The main predefined breakout gate requires a closed **5m candle above the prior 12 highs**, bullish, closing in its top 30%, **relative volume ≥1.5** and **range/ATR ≥1.2**; the next execution open must hold the broken level. If known before the ordinary target exits, it switches permanently to a trail: +1% gross arms a stop 0.5% below the highest price since entry. No extra Regime/DI+ activation restriction is used for this new experimental branch. The old regime-dependent policy is retained separately as a reference.

For BTC with a +1% ordinary target, that gate selects 5/38 trades: **2 extended moves, 1 ordinary rebound, 2 immediate failures**. Two trail winners return +1.678% and +3.000% net; three selections stop at −0.5%. Mean net across all 38 is +0.0849% / +0.1147% for low/high first, compared with +0.0851% / +0.1640% under the old policy. It is a candidate for further observation, with no demonstrated advantage over the old policy. It misses 5 of the 7 extended BTC moves and selects no SUI trade. It is not a general breakout classifier.

At a +0.5% ordinary target, BTC switches only 3 trades: the +3.000% runner and two losses. The +0.5% target often fills **before** the later 5m breakout confirmation is available. Its tiny positive mean (+0.0087% low-first) is driven by one runner. Removing that one runner's incremental benefit leaves the plain quick-exit result negative.

The weaker 5m prior-three-high reclaim catches more moves, but also 11 of BTC's 19 failures before +0.5%. It is too broad as a stand-alone quality filter. On SUI it helps this 11-trade sample, which is insufficient to establish reliability. The 15m entry expansion filter also selects both runners and failures; higher entry volume/range alone does not separate them. BTC extended moves have stronger median entry volume and DI recovery than ordinary rebounds, but failed entries are also high-volume/high-range. SUI does not reproduce BTC's volume separation. These descriptive medians are exploratory, not fitted thresholds.

## Why the old BTC win rate was only 34.21–39.47%

In low-first, 25/38 BTC entries hit the initial stop. **Only 6 of those 25 reached +0.5% gross beforehand**; taking +0.5% saves those six, but the other 19 still stop first. Of the 25 stopped trades, 7 later reach entry +1% within four hours. That later recovery does not change the actual stopped trade. Two trades contain both stop and target within a recorded **1m bar**; changing assumed within-minute order changes 13 wins to 15 and explains the 34.21% versus 39.47% range. The dates and both paths are retained in diagnostics.json.

The original low-first BTC wins average about +1.21% net while losses are −0.5%, so a low hit rate can still produce positive historical expectancy. That does not establish future profitability. A strict “no losing exit” rule is incompatible with retaining these same entries and the mandatory initial stop. Entry timing/selection must improve to reduce the 19 failures that never first earn +0.5%. Waiting indefinitely for recovery would silently abandon the loss limit.

The net-breakeven sensitivity only raises protection **after an observed +0.5% gross crossing** on a selected breakout trade. It changes no outcomes for the volume gate here: its false positives stop before earning that protection. Breakevens are counted separately from wins; adverse gaps would remain real losses.

## Timing, source quality and limitations

Entry predicates, source hashes and historical context are exactly the previous frozen study. Stored 15m measurements use the already reconstructed Section 5 context, not original live publication history. This experiment does not rerun indicators or change Trend/Regime. Only the requested stored 5m measurements are additionally read; no ADCN/features are pruned. The all-coin live-memory pass remains incomplete and is not pooled into this complete-cohort comparison.

Routing uses only a last-closed 5m observation known at the **execution bar open**, never the close of the minute containing a target/stop. A future breakout cannot retroactively cancel a filled quick exit. All 49 entries have usable 5m measurements at entry; warm-up/unavailable observation rows do not fire gates. Missing observations fall back to the ordinary target. Gate observations, memory provenance, execution candles and every losing trade are frozen in this folder.

Each entry uses a common execution frame across every compared policy, chosen for continuous matching prices, not favorable returns: 47 entries use 1m and 2 use 5m. Low-first and high-first are explicit OHLC assumptions, **not guaranteed bounds**; trailing results can be better under low-first than high-first. There is no tick-level execution, queue model or proof of fills at real order size. Costs are assumptions.

Predefined gates and all variants are shown below. Chronological sensitivities are in diagnostics.json, not an untouched holdout. BTC's main +1% volume hybrid is positive in both through-2022 and 2023+ slices (+0.1290% on 21 trades and +0.0303% on 17), but SUI's +1% control is negative through 2025 and positive in its four 2026 trades. There are only 49 total entries and 11 extended-move labels. No universal classifier or deployment claim follows.

Research only: no live trading rules, chart settings, runner services or orders changed. Keep the volume-backed gate as a BTC research candidate, retain the DI+ turn for the present entry hypothesis, and do not remove features from Memory based on this sample.

## BTCUSDT — 38 identical entries

Period: 2017-08-17T09:00:00+05:00 to 2026-11-14T18:15:00+05:00. Execution: {'1m': 37, '5m': 1}.

| Exit policy | Wins low-first · win% low / high | Mean net/trade low / high | PF low / high | Routed low |
|---|---:|---:|---:|---:|
| old_regime_reference | 13/38 · 34.21% / 39.47% | +0.085% / +0.164% | 1.26 / 1.54 | 0 |
| fixed_1_net | 13/38 · 34.21% / 39.47% | +0.013% / +0.092% | 1.04 / 1.30 | 0 |
| fixed_1_gross | 14/38 · 36.84% / 39.47% | +0.008% / +0.044% | 1.03 / 1.15 | 0 |
| fixed_0_5_gross | 19/38 · 50.00% / 52.63% | -0.060% / -0.037% | 0.76 / 0.84 | 0 |
| trail_all | 14/38 · 36.84% / 39.47% | +0.114% / +0.065% | 1.36 / 1.21 | 38 |
| hybrid_0_5_entry_expansion | 19/38 · 50.00% / 52.63% | +0.016% / +0.033% | 1.06 / 1.14 | 11 |
| hybrid_1_entry_expansion | 14/38 · 36.84% / 39.47% | +0.006% / +0.035% | 1.02 / 1.12 | 11 |
| hybrid_0_5_micro_reclaim | 17/38 · 44.74% / 47.37% | +0.001% / +0.009% | 1.00 / 1.03 | 19 |
| hybrid_1_micro_reclaim | 14/38 · 36.84% / 39.47% | +0.052% / +0.067% | 1.17 / 1.22 | 24 |
| hybrid_0_5_volume_breakout | 19/38 · 50.00% / 52.63% | +0.009% / +0.032% | 1.03 / 1.13 | 3 |
| hybrid_1_volume_breakout | 14/38 · 36.84% / 39.47% | +0.085% / +0.115% | 1.27 / 1.38 | 5 |
| hybrid_0_5_volume_protected | 19/38 · 50.00% / 52.63% | +0.009% / +0.032% | 1.03 / 1.13 | 3 |

Original hard stops: 25. Of those, 6 reached +0.5% gross before the stop, and 1 reached +1% gross. A later recovery does not reverse the filled stop.

| After the original stop | Complete observations | Reached entry +0.5% | Reached entry +1% |
|---|---:|---:|---:|
| 15 minutes | 25 | 4 | 3 |
| 30 minutes | 25 | 6 | 3 |
| 60 minutes | 25 | 8 | 5 |
| 240 minutes | 25 | 9 | 7 |

| Entry feature median | Extended ≥2% | Ordinary rebound | Failed before +0.5% |
|---|---:|---:|---:|
| relative_volume | 2.954 | 1.374 | 2.101 |
| natr_pct | 0.654 | 0.539 | 0.529 |
| candle_range_atr | 2.056 | 1.120 | 1.940 |
| close_position | 0.770 | 0.784 | 0.759 |
| lower_wick_fraction | 0.203 | 0.322 | 0.143 |
| plus_rise | 4.445 | 2.129 | 3.878 |
| minus_drop | 12.909 | 6.231 | 11.006 |
| close_to_ema50_pct | -1.790 | -2.357 | -1.532 |

Class counts: {'EXTENDED_2PCT': 7, 'FAILED_BEFORE_0_5': 19, 'ORDINARY_REBOUND': 12}. These are future diagnostic labels, not inputs to the router. Class definitions use the original initial stop, no artificial time exit.
All 38/38 entries have compatible closed 5m measurements. The strict crash diagnostic flagged 0 at entry; this supplies no evidence that it can remove these losses.

## SUIUSDT — 11 identical entries

Period: 2023-05-03T17:00:00+05:00 to 2026-11-14T18:15:00+05:00. Execution: {'1m': 10, '5m': 1}.

| Exit policy | Wins low-first · win% low / high | Mean net/trade low / high | PF low / high | Routed low |
|---|---:|---:|---:|---:|
| old_regime_reference | 5/11 · 45.45% / 45.45% | +0.182% / +0.182% | 1.67 / 1.67 | 0 |
| fixed_1_net | 5/11 · 45.45% / 45.45% | +0.182% / +0.182% | 1.67 / 1.67 | 0 |
| fixed_1_gross | 5/11 · 45.45% / 45.45% | +0.127% / +0.127% | 1.46 / 1.46 | 0 |
| fixed_0_5_gross | 6/11 · 54.55% / 63.64% | -0.020% / +0.060% | 0.91 / 1.33 | 0 |
| trail_all | 5/11 · 45.45% / 45.45% | +0.264% / +0.122% | 1.97 / 1.45 | 11 |
| hybrid_0_5_entry_expansion | 6/11 · 54.55% / 63.64% | -0.020% / +0.060% | 0.91 / 1.33 | 0 |
| hybrid_1_entry_expansion | 5/11 · 45.45% / 45.45% | +0.127% / +0.127% | 1.46 / 1.46 | 0 |
| hybrid_0_5_micro_reclaim | 6/11 · 54.55% / 63.64% | +0.116% / +0.196% | 1.51 / 2.08 | 4 |
| hybrid_1_micro_reclaim | 5/11 · 45.45% / 45.45% | +0.197% / +0.138% | 1.72 / 1.51 | 5 |
| hybrid_0_5_volume_breakout | 6/11 · 54.55% / 63.64% | -0.020% / +0.060% | 0.91 / 1.33 | 0 |
| hybrid_1_volume_breakout | 5/11 · 45.45% / 45.45% | +0.127% / +0.127% | 1.46 / 1.46 | 0 |
| hybrid_0_5_volume_protected | 6/11 · 54.55% / 63.64% | -0.020% / +0.060% | 0.91 / 1.33 | 0 |

Original hard stops: 6. Of those, 1 reached +0.5% gross before the stop, and 0 reached +1% gross. A later recovery does not reverse the filled stop.

| After the original stop | Complete observations | Reached entry +0.5% | Reached entry +1% |
|---|---:|---:|---:|
| 15 minutes | 6 | 2 | 1 |
| 30 minutes | 6 | 2 | 2 |
| 60 minutes | 6 | 3 | 2 |
| 240 minutes | 6 | 3 | 2 |

| Entry feature median | Extended ≥2% | Ordinary rebound | Failed before +0.5% |
|---|---:|---:|---:|
| relative_volume | 1.161 | 1.604 | 1.242 |
| natr_pct | 1.019 | 2.607 | 0.793 |
| candle_range_atr | 0.915 | 1.201 | 0.871 |
| close_position | 0.731 | 0.689 | 0.696 |
| lower_wick_fraction | 0.188 | 0.045 | 0.174 |
| plus_rise | 6.521 | 1.550 | 4.696 |
| minus_drop | 5.844 | 7.857 | 4.908 |
| close_to_ema50_pct | -3.217 | -11.590 | -3.090 |

Class counts: {'ORDINARY_REBOUND': 2, 'FAILED_BEFORE_0_5': 5, 'EXTENDED_2PCT': 4}. These are future diagnostic labels, not inputs to the router. Class definitions use the original initial stop, no artificial time exit.
All 11/11 entries have compatible closed 5m measurements. The strict crash diagnostic flagged 0 at entry; this supplies no evidence that it can remove these losses.
## Reproduce and inspect

- `protocol.json`: definitions frozen before outcome inspection.
- `summary.json`: all policies and both paths.
- `diagnostics.json`: routing errors, class feature distributions, post-stop recoveries, periods and ambiguity.
- `case_diagnostics.csv`: all 49 opportunities and diagnostic labels.
- `all_exit_trades.csv`: all 1,176 policy/path trades, fees included, no omitted losses.
- `*_5m_observations.json.gz` and `*_execution.json.gz`: frozen gate evidence and price bars.
- `independent_execution_audit.json`: 1,078 new exit replays through a separate segment engine plus 98 unchanged original trades, zero mismatches. Gate observations are frozen inputs, not an independently recalculated indicator audit.

29 targeted tests passed, including gross/net conversion, closed-bar timing, future-signal rejection, same-bar protection order, unchanged initial stops, retained adverse gaps and missing post-stop coverage.

```sh
PYTHONPATH=/tmp/btc-section5-test-deps:. .venv-build/bin/python3 -m research_reports.DI50_breakout_exit_routing_v1.study
PYTHONPATH=/tmp/btc-section5-test-deps:. .venv-build/bin/python3 -m research_reports.DI50_breakout_exit_routing_v1.audit_results
PYTHONPATH=/tmp/btc-section5-test-deps:. .venv-build/bin/python3 -m research_reports.DI50_breakout_exit_routing_v1.write_report
```

Re-running the study reads current stored 5m memory; that memory generation may later differ. Auditing/reporting the frozen artifacts does not read new market values.
