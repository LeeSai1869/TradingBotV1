# DI50 three-candle reversal — 15-minute spot study

The requested entry uses bearish same-timeframe Trend, a DI− peak and absolute DI-spread peak above 50, and the reverse DI+ trough. No RSI filter and no pivot labels select entries.

For closed candles 2 (two ago), 1 (previous), and 0 (confirmation):

```text
DI−[2] < DI−[1] and DI−[0] < DI−[1]
Spread[2] < Spread[1] and Spread[0] < Spread[1]
DI+[2] > DI+[1] and DI+[0] > DI+[1]
```

The primary threshold is DI−[1] >50 AND spread[1] >50. A separate version requires both values still above 50 on candle 0. The literal DI+[0] >= DI+[1] version is also separate; it happens to select the same BTC/SUI entries on these snapshots. No thresholds were optimized.

## Execution

BUY at the next contiguous 15m open. One position per coin. Net loss budget 0.5% from entry, including assumed costs. At each execution bar use only the latest closed 15m Regime and DI+: bearish Regime takes a fixed +1% net target; bullish Regime requires profit >=1% AND DI+ >50 to arm a permanent 0.5% trail below the highest raw price since entry. Neutral/unknown entry Regime is excluded and counted. While holding, unknown Regime cannot arm a new profit exit; hard/armed stops stay active. No fixed time exit.

Costs are assumed 4 bps fee plus 2 bps slippage per side. Prefer recorded complete 1m bars whose aggregate agrees with the stored 15m OHLC, otherwise 5m, otherwise explicitly labeled 15m. Low-first and high-first are different OHLC ordering assumptions, not guaranteed tick-path bounds. Actual adverse opening gaps are retained.

## Complete stored BTC/SUI research snapshots

These are stored measurements with complete historical Trend/Regime reconstructed previously by the current Section 5 definitions. This experiment did not rerun those classifiers. Feature generation/config and classifier source hashes were checked. This is not original live publication history. The partial live-memory pass is reported separately below.

| Coin / rule | Trades | Win rate: low / high first | Mean net/trade: low / high first | PF: low / high first |
|---|---:|---:|---:|---:|
| BTCUSDT · Peak >50 + DI+ trough | 38 | 34.21% / 39.47% | 0.085% / 0.164% | 1.26 / 1.54 |
| BTCUSDT · Still >50 + DI+ trough | 3 | 33.33% / 66.67% | 0.000% / 0.500% | 1.00 / 4.00 |
| BTCUSDT · Peak >50, no DI+ turn filter | 267 | 16.85% / 18.35% | -0.235% / -0.212% | 0.44 / 0.48 |
| SUIUSDT · Peak >50 + DI+ trough | 11 | 45.45% / 45.45% | 0.182% / 0.182% | 1.67 / 1.67 |
| SUIUSDT · Still >50 + DI+ trough | 4 | 50.00% / 50.00% | 0.250% / 0.250% | 2.00 / 2.00 |
| SUIUSDT · Peak >50, no DI+ turn filter | 111 | 24.32% / 26.13% | -0.135% / -0.108% | 0.64 / 0.71 |

Adding the DI+ reversal improves this sample substantially, but the primary rule has only 38 BTC and 11 SUI completed trades. Most BTC trades still lose under the low-first assumption. This does not support an “always good buy” claim or a validated deployment.

The threshold-at-confirmation version is much rarer: 3 BTC and 4 SUI completed trades. A current-only >50 filter should not be confused with buying after a >50 peak has already turned down.

Strict-rule median holding times under low-first: BTC 29 minutes; SUI 9 minutes. Maximums were 819 and 174 minutes respectively. These are exit-duration results, not imposed timeouts. Both source periods end at 14 November 2026, 18:15 PKT; BTC starts 17 August 2017 and SUI 3 May 2023.

A separate bearish-trailing sensitivity is retained in each result JSON; it does not replace the agreed bearish fixed target.

## Current stored-memory pass

Read 51 stored 15m coin scopes (8,951,941 candles). Current feature formula is ready on 36 scopes; 5,259,483 candles have valid prices/current DI measurements. Usable Trend on those valid feature candles: 210,918 (2.36% of raw coverage). Missing Trend or unreplayed features are excluded, never treated as bearish or zero. Broad all-coin profitability is therefore not established by this incomplete pass.

| Coin | Candles | Usable Trend candles | Strict peak-threshold entries | Closed | Win rate | Mean net/trade |
|---|---:|---:|---:|---:|---:|---:|
| AAVEUSDT | 213,176 | 0 | 0 | 0 | —% | —% |
| ADAUSDT | 300,429 | 159 | 0 | 0 | —% | —% |
| AEROUSDT | 9,324 | 0 | 0 | 0 | —% | —% |
| ALGOUSDT | 259,256 | 0 | 0 | 0 | —% | —% |
| APTUSDT | 142,809 | 1,057 | 1 | 1 | 100.00% | 1.000% |
| ARBUSDT | 127,873 | 998 | 0 | 0 | —% | —% |
| ASTERUSDT | 38,802 | 1,137 | 0 | 0 | —% | —% |
| ATOMUSDT | 264,380 | 0 | 0 | 0 | —% | —% |
| AVAXUSDT | 215,371 | 0 | 0 | 0 | —% | —% |
| BCHUSDT | 244,002 | 0 | 0 | 0 | —% | —% |
| BNBUSDT | 315,834 | 1,128 | 0 | 0 | —% | —% |
| BTCUSDT | 323,582 | 178,198 | 21 | 21 | 42.86% | 0.175% |
| CAKEUSDT | 201,001 | 129 | 0 | 0 | —% | —% |
| DASHUSDT | 213,215 | 49 | 0 | 0 | —% | —% |
| DOTUSDT | 218,665 | 0 | 0 | 0 | —% | —% |
| ENAUSDT | 91,811 | 1,142 | 0 | 0 | —% | —% |
| ETCUSDT | 295,060 | 0 | 0 | 0 | —% | —% |
| ETHFIUSDT | 93,235 | 1,195 | 0 | 0 | —% | —% |
| ETHUSDT | 323,582 | 1,038 | 0 | 0 | —% | —% |
| FILUSDT | 213,121 | 0 | 0 | 0 | —% | —% |
| GRAMUSDT | 12,995 | 1,154 | 0 | 0 | —% | —% |
| HBARUSDT | 249,769 | 0 | 0 | 0 | —% | —% |
| HYPEUSDT | 4,919 | 1,223 | 1 | 1 | 100.00% | 1.000% |
| ICPUSDT | 193,280 | 949 | 0 | 0 | —% | —% |
| INJUSDT | 212,597 | 0 | 0 | 0 | —% | —% |
| JSTUSDT | 219,405 | 0 | 0 | 0 | —% | —% |
| JUPUSDT | 97,731 | 1,158 | 0 | 0 | —% | —% |
| LINKUSDT | 274,221 | 1,028 | 1 | 1 | 100.00% | 1.000% |
| LTCUSDT | 312,285 | 0 | 0 | 0 | —% | —% |
| MORPHOUSDT | 39,079 | 1,156 | 0 | 0 | —% | —% |
| NEARUSDT | 213,265 | 1,089 | 0 | 0 | —% | —% |
| NEXOUSDT | 159,366 | 963 | 0 | 0 | —% | —% |
| NIGHTUSDT | 23,813 | 1,108 | 0 | 0 | —% | —% |
| ONDOUSDT | 55,883 | 1,149 | 0 | 0 | —% | —% |
| POLUSDT | 76,059 | 1,211 | 0 | 0 | —% | —% |
| PYTHUSDT | 97,555 | 130 | 0 | 0 | —% | —% |
| QNTUSDT | 185,676 | 1,021 | 0 | 0 | —% | —% |
| RENDERUSDT | 80,771 | 1,174 | 0 | 0 | —% | —% |
| SKYUSDT | 40,643 | 1,155 | 0 | 0 | —% | —% |
| SOLUSDT | 219,405 | 1,026 | 1 | 1 | 100.00% | 1.000% |
| STXUSDT | 247,273 | 0 | 0 | 0 | —% | —% |
| SUIUSDT | 123,955 | 1,093 | 1 | 1 | 100.00% | 1.000% |
| TAOUSDT | 90,931 | 1,127 | 2 | 2 | 50.00% | 0.250% |
| TRXUSDT | 295,120 | 246 | 0 | 0 | —% | —% |
| UNIUSDT | 215,865 | 0 | 0 | 0 | —% | —% |
| WLDUSDT | 116,095 | 1,155 | 0 | 0 | —% | —% |
| WLFIUSDT | 42,159 | 1,176 | 0 | 0 | —% | —% |
| XLMUSDT | 296,184 | 0 | 0 | 0 | —% | —% |
| XRPUSDT | 298,782 | 1,022 | 0 | 0 | —% | —% |
| ZECUSDT | 268,125 | 1,029 | 1 | 1 | 0.00% | -0.500% |
| ZROUSDT | 84,207 | 1,146 | 0 | 0 | —% | —% |

The reader timing bug was fixed: a runner refresh of a historical binding after candle reading began must not hide that already committed compatible prefix. The reader now observes the current binding while retaining the frozen market cutoff on the actual candle results. No stored indicators or pivots were changed.

## Previous DI values and workspace use

Memory contains `prev_di_plus` and `prev_di_minus`; labels are now **Previous DI+** and **Previous DI−**. They matched every checked preceding canonical measurement in the frozen cohorts. Previous absolute spread is `di.abs_spread` with candle=1; two-ago is candle=2. The editor now spells out **0=current, 1=previous, 2=two ago** for both comparison operands.

Six reviewable configurations are in `configs/`. The two strict-trough versions are also installed as workspace presets after validation. They use the new **Take profit** SELL action for the bearish 1% exit, and **Trailing SELL** for the bullish exit. Refresh the workspace, select the preset under **Start from**, then **Load strategy**. These presets reproduce the entry/exit conditions; the workspace currently uses selected-timeframe OHLC for execution, whereas this report uses finer stored 1m/5m prices. Their fills and returns can differ. No strategy was enabled for live trading.

## Evidence

- `protocol.json`: hypotheses, timing, exit policy and cost assumptions.
- `frozen_*_results.json.gz`: complete snapshot results, cases, both price-order paths and trailing sensitivity.
- `memory_summary.json` / `memory_coverage.csv`: partial all-coin coverage and results.
- `*_execution.json.gz`: frozen lower-timeframe prices used by this run.
- `independent_execution_audit.json`: independent fill arithmetic and price-bar checks.
- `strict_peak_trades.csv`: every primary strict-rule trade, including dates, returns and execution frame.

67 targeted unit/integration checks passed. The direct predicates matched the workspace expression evaluator at 4,980 checked BTC/SUI snapshot points, with zero mismatches. Independent arithmetic and stored-price-bar verification covered 1,516 closed execution checks with zero mismatches. Historical results remain exploratory; the recent-period samples are too small to establish reliability.
