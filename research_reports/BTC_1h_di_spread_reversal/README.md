# BTC 1h: DI-spread first-drop spot hypothesis

**Superseded exit-policy comparison:** the user subsequently confirmed a 0.5%
protective loss limit and regime-dependent trailing, plus 5m intrabar confluence.
See the [corrected stop/trailing replay](../BTC_1h_di_spread_trailing_v2/README.md).
The fixed-target / 24-hour headline below is a historical experiment, not the
user's current strategy specification.

13 November 2026. Research only. The latest example reached its target, but the complete sample does not establish a standalone trading edge. No live BUY/SELL rules, indicator formulas, feature retention or ADCN fields were changed.

## Frozen test definition

- BTCUSDT spot, 80,884 stored hourly candles from 2017-08-17T04:00:00+00:00 through 2026-11-13T15:59:59.999000+00:00. The exported current feature generation is 1. Stored RSI length is **7**, ADX/DI length **10**; this is not a standard RSI(14) substitution.
- Bearish spread = DI− minus DI+. It equals the chart’s absolute DI spread while DI− dominates. A local peak is known after the first subsequent closed decline: spread[t−1] ≥ spread[t−2] and spread[t] < spread[t−1]. Flat-topped peaks count. This never chooses the highest future spread or a retrospective pivot low.
- Primary test requires spread above 40 both at the peak and at confirmation; DI− above 40 / 45 / 50 at confirmation. Each threshold is tested with and without RSI below 20 at confirmation. Peak-time thresholds and peak-only spread are separate sensitivity tests in results.json.
- Enter at the **next hourly open**, after the signal candle is closed. A forming-candle DI drop cannot be replayed accurately from final hourly measurements alone; an intrabar implementation needs a separate lower-timeframe test.
- Sell at the first hourly high touching the precomputed +1% **net** target. Costs retain the earlier research scenario: 4 bps fee and 2 bps slippage **per side**. That requires a 1.1213% reference-price rise. A gross 1% price move instead yields about 0.8789% net in this scenario. A 10 bps fee sensitivity is also saved.
- Commission rates depend on the actual account/symbol; the assumed costs are not an account-rate claim. Binance documents the account commission endpoint in its [commission FAQ](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/commission_faq.md).
- Your proposed policy has no specified stop or timeout. Accordingly, unlimited-hold replays are included. Fixed 6 / 12 / 24 / 48 / 72 / 168-hour windows and stop sensitivities are comparison experiments, not newly adopted production exits.
- Missing or discontinuous candles censor the forward outcome. Incomplete final windows are excluded from fixed-horizon hit rates even when an early target hit is already known. Event outcomes may overlap; separate single-position replays skip overlapping entries.

## How often did the 1% net target arrive within 24 hours?

The average-return column takes +1% at a target hit and marks an unresolved position to market at the 24-hour close. It answers a defined 24-hour experiment, not the profitability of holding indefinitely.

| DI− | RSI | Eligible completed windows | Target hits | Hit rate | Mean net, 24h experiment |
| --- | --- | --- | --- | --- | --- |
| > 40 | No RSI gate | 185 | 107 | 57.84% | -0.48% |
| > 40 | < 20 | 134 | 78 | 58.21% | -0.50% |
| > 45 | No RSI gate | 166 | 98 | 59.04% | -0.41% |
| > 45 | < 20 | 123 | 73 | 59.35% | -0.43% |
| > 50 | No RSI gate | 82 | 46 | 56.10% | -0.38% |
| > 50 | < 20 | 67 | 38 | 56.72% | -0.44% |

RSI below 20 changes these hit rates only slightly and reduces the sample. Raising DI− to 50 does not improve target attainment. The comparison does not justify selecting 45 as a final production threshold.

For DI− >45 and RSI <20:

| Window | Eligible | Target hit rate | Mean net at target / window close |
| --- | --- | --- | --- |
| 6h | 124 | 33.87% | -0.18% |
| 12h | 123 | 46.34% | -0.35% |
| 24h | 123 | 59.35% | -0.43% |
| 48h | 121 | 67.77% | -0.40% |
| 72h | 121 | 73.55% | -0.58% |
| 168h | 119 | 78.99% | -1.42% |

The non-overlapping 24-hour replay has 94 fully observable trades, 58.51% target attainment and -0.42% mean net return. The same negative conclusion survives removing overlapping entries.

## Holding until 1% is not a free exit

Unlimited-hold tests must retain unresolved positions and missing-data censoring; a 100% win rate among only completed target exits is not a valid success rate. For the DI− >45 / RSI <20 single-position replay:

- Entry 2022-05-05T17:00:00+00:00; GAP_CENSORED; observed for 7748 hours (322.8 days); adverse excursion bound -58.21%. Censored entries have no claimed completed-trade return.
- Entry 2026-01-19T02:00:00+00:00; RIGHT_CENSORED; observed for 7166 hours (298.6 days); adverse excursion bound -37.57%. Censored entries have no claimed completed-trade return.
- Entry 2018-11-14T18:00:00+00:00; GAP_CENSORED; observed for 2816 hours (117.3 days); adverse excursion bound -47.18%. Censored entries have no claimed completed-trade return.
- The position entered 2026-01-19T02:00:00+00:00 is still unresolved at the dataset boundary: last-close mark to market **-25.67%**, after 298.6 days. This is an observed open position, not a hypothetical stop loss.

The eventual-hit statistics and compounded completed-trade returns exclude unpriced censored outcomes. They must not be presented as total account returns; results.json explicitly marks unlimited-hold account return as invalid when censored positions exist.

## Bearish trend, regime and additional features

The context uses the existing Section 5 engine functions, replayed sequentially offline: original Section 4 Structure event lineage → Structure → Trend, plus Regime. Source/config hashes are recorded. This supplies the current definitions over the complete research sample without waiting for production history backfill. These are reconstructed close-time classifications, not proof they were published live at those historical times. PARTIAL quality remains labelled; missing context is never converted to bullish/neutral.

For DI− >45 / RSI <20, separating an established bearish *regime* from other known regimes:

| Regime | Eligible 24h windows | Hit rate | Mean net, 24h |
| --- | --- | --- | --- |
| TRENDING_BEARISH | 78 | 62.82% | -0.50% |
| OTHER_KNOWN | 43 | 53.49% | -0.23% |
| UNKNOWN | 2 | 50.00% | -2.13% |

The bearish regime has a worse average outcome in this comparison, even though its target-hit frequency is higher. Trend direction alone is not a sufficient skip rule: sharp selloffs frequently produce confirmed bearish direction as well as oversold measurements. The report keeps confirmed Trend separate from retained direction during pending/conflicted conditions.

Nine additional gates were checked within the bearish Trend-direction subset. All were predetermined simple conditions; no grid search was run. 2017–2023 is discovery, 2024 validation, and 2025–2026 a chronological holdout. Forward windows crossing a split boundary are excluded. Since the hypothesis came from already viewed charts, this holdout is not prospective validation.

| Additional bearish-condition gate | Discovery N | Discovery mean net | 2025–26 N | 2025–26 mean net |
| --- | --- | --- | --- | --- |
| BASELINE | 66 | -0.59% | 17 | 0.24% |
| close_above_previous_high | 0 | — | 0 | — |
| close_in_upper_30pct | 17 | -0.75% | 10 | 0.29% |
| rsi_rising | 37 | -0.92% | 12 | -0.03% |
| di_plus_rising | 2 | 0.57% | 1 | -2.12% |
| relative_volume_ge_1_5 | 30 | -0.39% | 9 | -0.09% |
| natr_ge_1pct | 44 | -0.38% | 5 | -0.12% |
| below_ema50_by_1atr | 66 | -0.59% | 17 | 0.24% |
| bearish_trend_weakening | 0 | — | 0 | — |
| not_trending_bearish_regime | 11 | -0.03% | 3 | 1.00% |

**No additional gate demonstrates a validated fix.** NATR ≥1% improves full-sample target frequency, but discovery expectancy remains negative and the holdout is tiny. Excluding a trending bearish regime has some positive recent subsets but too few observations, with negative discovery expectancy. RSI rising, DI+ rising, upper-range closes, volume, EMA distance and weakening Trend do not establish a consistent advantage here. These features can remain research/risk inputs; this result authorizes no memory pruning.

## Latest example

The 2026-11-13T04:00:00+00:00 signal candle was known at **2026-11-13T10:00:00+05:00 PKT**. DI− 46.97, spread 43.98 after a 48.19 peak, RSI 4.24. The next open was 68,581.08; the net-target reference price was 69,350.06.

Price touched that target in the third hourly candle after entry (12:00–13:00 PKT). This verifies the recent example under the hourly-touch assumptions. DI− had already dropped below 50 at confirmation, so the strict current-value >50 version did not take it. Its full 24-hour observation window had not ended when the source was frozen; it is excluded from the fixed-horizon aggregate denominator.

## Liquidity: what was wrong and what changed

- The recorder is delivering real Binance **USDT perpetual** depth. It is not spot depth. A finite 1,000-level snapshot was covering only a few tenths of a percent below price and less above it; small bands do not mean a full 1% book was observed.
- Sequence recoveries and delayed exchange messages caused real gaps. One earlier 120-sample inspection found a maximum sample interruption of 168 seconds. Stale depth is intentionally hidden; keeping it drawn as current would misrepresent the book.
- The computer clock was within about 0.1 seconds of Binance’s public time endpoints. The recurring “delayed exchange book or local clock skew” message was therefore not evidence that the clock itself was wrong.
- A busy raw archive batch held newly queued current samples behind up to 1,000 raw writes. The writer now returns to current-sample commits after a bounded 50ms raw-work slice, preserving every queued raw record. Only the existing liquidity service was restarted, preserving configuration and data.
- After restart, 67 BTC samples over 403.0 seconds had median sample-to-memory delay **25ms**, versus **1340.5ms** before. The after-window maximum remained 2407ms. This short observation is not proof that transport interruptions are eliminated.
- Current profiles now draw above shaded overlays, with a one-pixel minimum for subpixel price bins. Original prices/notional remain exact; the forming-candle strip stays clear. The heatmap remains below candles and keeps exact observed times. Freshness limits and historical-view restrictions remain enforced.
- Reload the chart to load this display correction. Native app visual inspection was unavailable; the rendering geometry, stale hiding, market restrictions and candle protection are covered by automated checks.
- This feed cannot be added as a universal historical entry gate: matching historical spot/perpetual observations were not recorded for most of this candle archive. No synthetic historical liquidity was added.

## Reproduce and inspect

- `source.json.gz`: frozen measurements, engine definitions/configuration and offline context; SHA-256 of the decompressed source 6e5776ad37f5f51a0e9a670be799ffe155739d740e4960fd99a35e979a5bb90e.
- `results.json`: all six variants, every signal with context/prices, horizons, exact timing sensitivities, non-overlapping replays, costs, stop ambiguity, censored positions and bearish-filter splits.
- `liquidity_verification.json`: before/after timing, coverage, clock check, live status and observation limits.
- Replay the frozen source: `PYTHONPATH=. .venv-build/bin/python3 research_reports/BTC_1h_di_spread_reversal/study.py`.
- A new read-only export can be made with `export_source.py`. It releases source database read snapshots before running the longer offline classifiers. A fresh export changes the frozen observation window.
- Verification: 29 Python tests passed for the liquidity recorder/analytics and replay semantics; 10 JavaScript liquidity-display tests passed. Target touches remain an OHLC fill approximation. Stop and target in the same hourly candle use stop-first ordering, except a gap-up opening already through the target.

Keep this as an exhaustion-watch hypothesis. A usable buy/sell rule still needs a supported entry filter plus a defined loss/time/capital policy; a frequent rebound is not enough to establish positive expectancy.
