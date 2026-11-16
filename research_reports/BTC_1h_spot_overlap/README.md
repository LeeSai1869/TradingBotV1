# BTC 1h: exact spot upswing overlap audit

Frozen Binance BTCUSDT 1h source: 2017-08-17T09:00:00+05:00 through 2026-11-05T21:00:00+05:00. This is historical research, not a live chart call.

**Definition:** every native pivot LOW paired with the first later native pivot HIGH. A hit requires `100 * (high / low - 1) >= 1%`. No later high is substituted. Raw endpoint prices and first-opposite identities are checked for every pair. Pairs crossing missing, shortened or invalid raw candles are censored.

80,692 candles; 12,946 lows; outcomes: {'HIT': 8290, 'NO_HIT': 4635, 'CENSORED_RAW_GAP': 20, 'CENSORED_SHORT_OR_INVALID_CANDLE': 1}. Resolved exact-pair hit share: 64.14%. These are hindsight swing labels, not trading win rates.

The older touch-based label disagrees with the exact endpoint label in 14 pairs: 8 cross raw gaps. The remaining contiguous disagreements touched +1% somewhere before the next high but that next native high itself was below +1%. All incomplete price paths are excluded from both comparison cohorts.

## What is common?

No tested origin-close predicate is true for every qualifying upswing with full measurement coverage. The tested universe is listed below; this does not prove that no other feature or combination could be universal. Trivial statements such as positive prices are not useful signals.

| Condition at LOW origin close | >=1% pairs: true / evaluable | Smaller pairs: true / evaluable | Missing in >=1% pairs |
|---|---:|---:|---:|
| abs_spread_ge_10 | 4,846/8,282 (58.51%) | 2,074/4,635 (44.75%) | 8 |
| adx_ge_25 | 5,422/8,281 (65.48%) | 2,424/4,635 (52.30%) | 9 |
| atr_pct_ge_1 | 3,923/8,282 (47.37%) | 212/4,635 (4.57%) | 8 |
| close_above_previous_high | 592/8,283 (7.15%) | 227/4,635 (4.90%) | 7 |
| close_below_ema50 | 4,834/8,283 (58.36%) | 2,413/4,635 (52.06%) | 7 |
| close_recovering | 3,445/8,283 (41.59%) | 1,734/4,635 (37.41%) | 7 |
| di_minus_dominant | 5,731/8,282 (69.20%) | 2,745/4,635 (59.22%) | 8 |
| di_plus_rising | 518/8,276 (6.26%) | 233/4,635 (5.03%) | 14 |
| extension_ge_1pct | 4,890/8,283 (59.04%) | 1,241/4,635 (26.77%) | 7 |
| green_candle | 3,461/8,290 (41.75%) | 1,731/4,635 (37.35%) | 0 |
| lower_wick_ge_40pct | 4,532/8,290 (54.67%) | 2,382/4,635 (51.39%) | 0 |
| pressure_declining | 2,887/8,276 (34.88%) | 1,691/4,635 (36.48%) | 14 |
| pressure_peak_now | 1,482/8,274 (17.91%) | 679/4,635 (14.65%) | 16 |
| range_ge_1_atr | 4,709/8,282 (56.86%) | 1,625/4,635 (35.06%) | 8 |
| rsi_below_30 | 1,578/8,283 (19.05%) | 391/4,635 (8.44%) | 7 |
| rsi_rising | 3,444/8,277 (41.61%) | 1,734/4,635 (37.41%) | 13 |
| rvol_ge_1 | 4,371/8,281 (52.78%) | 1,549/4,635 (33.42%) | 9 |
| simultaneous_pressure_spread_peak | 712/8,274 (8.61%) | 217/4,635 (4.68%) | 16 |
| spread_peak_now | 1,765/8,274 (21.33%) | 946/4,635 (20.41%) | 16 |

## Recurring measurements, not entry thresholds

Means below use only the exact contiguous-pair cohorts. `atr_pct` is 100*ATR/close; RVOL is the stored current-inclusive volume ratio; extension is absolute close/EMA50 distance in percent. Missing measurements are excluded per field, with exact counts/ranges in statistics.json.

| Measurement | Prior candle: >=1% / smaller | Origin close: >=1% / smaller |
|---|---:|---:|
| atr_pct | 1.155 / 0.566 | 1.188 / 0.562 |
| relative_volume | 1.114 / 0.913 | 1.293 / 0.933 |
| range_atr | 1.076 / 0.897 | 1.234 / 0.949 |
| ema50_distance_abs_pct | 1.922 / 0.770 | 1.891 / 0.738 |
| abs_di_spread | 13.758 / 10.539 | 14.615 / 10.599 |
| adx | 31.769 / 27.901 | 31.974 / 27.715 |
| rsi | 44.442 / 48.945 | 43.232 / 46.760 |

A fixed 1% target is easier in high volatility. These effects are descriptive, correlated and selected using future pivot membership; they cannot establish signal precision or independent votes.

## Different starting conditions

These are simple prior-close EMA50 position/slope proxies, explicitly separate from Section 5 Regime/Trend. UP requires prior close >= prior EMA50 and positive prior normalized EMA50 slope; DOWN uses close below and negative slope; remaining valid observations are MIXED. They are never substituted for missing independent engine history.

| Prior context | Resolved pairs | >=1% pairs | Share |
|---|---:|---:|---:|
| UP_PROXY | 5,717 | 3,468 | 60.66% |
| DOWN_PROXY | 6,000 | 4,042 | 67.37% |
| MIXED_PROXY | 1,181 | 757 | 64.10% |
| UNAVAILABLE | 27 | 23 | 85.19% |

| Prior ATR as % of close | Resolved pairs | >=1% pairs | Share |
|---|---:|---:|---:|
| <0.5% | 2,796 | 776 | 27.75% |
| 0.5-1% | 6,140 | 3,760 | 61.24% |
| 1-2% | 3,113 | 2,878 | 92.45% |
| >=2% | 862 | 862 | 100.00% |

## Fixed overlap checks

These definitions were fixed in the audit script, without a threshold search. Tighter simultaneous conjunctions discard many qualifying swings. OR conditions cover more swings but also cover more smaller swings. Exact missingness and each context slice remain in statistics.json. All rows are still hindsight-selected native lows, so these percentages are not live-signal precision.

| Origin-close overlap | >=1% pair coverage | Smaller-pair coverage |
|---|---:|---:|
| activity_AND_extension_AND_adx | 2,205/8,282 (26.62%) | 310/4,635 (6.69%) |
| pressure_AND_spread_AND_price_same_close | 585/8,280 (7.07%) | 162/4,635 (3.50%) |
| activity_OR_extension | 6,580/8,282 (79.45%) | 2,416/4,635 (52.13%) |
| pressure_OR_price_recovery | 3,764/8,277 (45.48%) | 1,928/4,635 (41.60%) |

## Timing and spot execution

Among 8,290 exact qualifying pairs, 2,114 (25.50%) already closed >=1% above the low on the origin candle. Another event cannot be assigned to an earlier minute using the final hourly values.

The target touched on a subsequent candle by native-low confirmation in 6,048 (72.96%) qualifying pairs. Median recognition delay is 2.0 hours from low candle OPEN and 2.0 hours from high candle OPEN. The origin close itself is one hour after its open.

Only 5,291/8,290 qualifying pairs still have >=1% gross distance from the next candle OPEN to the eventual immediate high. Even this assumes an ideal exit at that unknown future high; it is not achievable P&L or evidence of a real-time low entry.

SELL evidence is measured at the immediate HIGH ending these same upswings, rather than treating every subsequent 1% drop as a short profit:

| Condition at endpoint HIGH close | True / evaluable in qualifying upswings |
|---|---:|
| di_plus_dominant | 5,002/8,290 (60.34%) |
| pressure_declining | 2,713/8,287 (32.74%) |
| pressure_peak_now | 1,507/8,286 (18.19%) |
| spread_peak_now | 1,773/8,286 (21.40%) |
| rsi_above_70 | 1,647/8,290 (19.87%) |
| red_candle | 3,460/8,290 (41.74%) |
| close_weakening | 3,459/8,290 (41.72%) |
| rvol_ge_1 | 4,267/8,288 (51.48%) |

These are endpoint descriptions, not permission to sell at an unrecognized high. A live SELL needs causal price failure or an executable risk/target rule while holding BTC. A spot system stays in BTC or cash; it does not book short profit.

## Files and reproduction

- `statistics.json`: exact denominators, missingness, example counterexample IDs, contexts, timing and source hash.
- `pairs.csv`: every pair, including failures and raw-gap exclusions, endpoint IDs/times and prices.
- `INDICATOR_SPEC.md`: proposed spot state machine and Section 5 assessment.
- `PROTOTYPE_RESULTS.md`: failed first causal BUY/SELL hypothesis, model costs and replay commands.
- `section5_readiness.json`: separate read-only operational snapshot, if supplied.

```sh
python3 research_reports/BTC_1h_spot_overlap/reproduce.py
```

No native or legacy structure labels become trading gates here. The preserved 2017–2026 export is an older feature generation; current source fixes and pending replay must be checked before transferring findings. Preserved engine history is sparse, so regime-conditioned overlap is not established. No thresholds were optimized, no independent holdout was tested, and no live rules, engine budgets, checkpoints or databases were changed.
