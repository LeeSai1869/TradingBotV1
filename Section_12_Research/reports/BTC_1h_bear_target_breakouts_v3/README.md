# BTC: bearish +1% target, unchanged bullish trail, breakout/crash execution audit

13 November 2026 (Asia/Karachi). Offline research on the same frozen BTCUSDT spot archive: 80,884 hourly candles and 970,429 recorded five-minute candles, ending 13 November 2026 at 20:59:59.999 PKT. There were no production strategy, feature, chart or service changes, no memory pruning and no orders.

The stored chart settings remain RSI(7) and DI/ADX length 10. Hourly closed values and terminal forming-hour previews were previously reproduced exactly, and sampled stored 5m DI/RSI values also matched exactly.

## User policy now tested

- **Bearish Regime:** exit directly at the +1% profit target. This replaces bearish trailing activation.
- **Bullish Regime:** keep the existing logic: profit ≥1% AND known DI+ >50 activates the 0.5% highest-since-BUY trailing stop. Once armed, keep it armed.
- Protection remains active from entry on every trade. The main scenario targets a **0.5% net-loss budget**, with a literal **0.5% price-stop** comparison. No 24-hour exit, averaging down, pyramiding or price-low hindsight fill is used.
- Main target is **+1% net** under the retained scenario of 4 bps fee and 2 bps slippage per side. A separate **+1% price target for bearish exits only** is tested; that sensitivity preserves the bullish net-profit activation rule.
- Regime is the latest closed 1h Section5 REGIME direction. Entry-frozen Regime is also compared. Bullish DI+ comes from the most recent completed-5m preview of the forming hourly indicator. The prior exact kernel/parity checks remain applicable.
- Entry baseline: first decline from the forming-hour bearish spread peak above 40, with a known 5m DI-spread peak/drop at the same close or within the prior 10 minutes; enter next 5m open. DI− thresholds 40, 45 and 50 and optional RSI <20 are kept separate.
- Stops/targets are replayed on recorded 1m prices where available, with whole-trade 5m fallback. Low-first and high-first OHLC paths are reported as sensitivity scenarios, not tick-level certainty. Gap fills are retained rather than clipped to a loss cap.

## Independent audit of the unexpectedly low winning ratio

A separate first-barrier search checked **328** unambiguous entry-frozen bearish trades. It independently calculated the hard-stop and target prices and searched for the first recorded minute/five-minute candle touching either. It found **0 mismatches** with the replay. One bar touching both levels was excluded from this agreement count.

This validates the tested barrier ordering; it does not prove the entry definition captures every visually attractive dip. The core failure is buying before the downward move finishes: a later recovery does not undo an earlier protective stop. Diagnostic future labels were kept completely separate from the entry filters:

| Baseline | Stopped trades, full 6h observation | Target touched in a later 5m bar | Share |
| --- | --- | --- | --- |
| DI− >40 | 252 | 68 | 26.98% |
| DI− >45 | 227 | 62 | 27.31% |
| DI− >50 | 114 | 25 | 21.93% |

These remain losing trades. Target touches in later bars are diagnostic labels, not instructions to remove or widen the stop.

## Does the new bearish target fix it?

Strict forming-1h + 5m DI-peak confluence, no optional RSI gate, non-overlapping positions, net-loss-budget stop:

| DI− | Closed trades | Winning ratio | Mean net, new target | Mean net, old trail¹ | Median holding¹ |
| --- | --- | --- | --- | --- | --- |
| > 40 | 336 | 25.00% | -0.125% to -0.121% | -0.11% | 24.0 min |
| > 45 | 301 | 24.58% | -0.131% to -0.131% | -0.11% | 24.0 min |
| > 50 | 147 | 22.45% | -0.163% to -0.163% | -0.13% | 20.0 min |

¹ Low-first scenario. The new target changes payout after reaching profit, but cannot rescue entries that hit the stop first. For the pure bearish +1% / −0.5% net payoff, the simple break-even win rate is 33.33% before gap effects. The baselines remain below it.

Cost/target-basis comparisons for the DI− >45 baseline:

| Scenario | Closed | Winning ratio | Mean net/trade | Worst modeled net |
| --- | --- | --- | --- | --- |
| New exit, 0.5% net-loss budget | 301 | 24.58% | -0.13% | -0.50% |
| New exit, literal 0.5% price stop | 297 | 28.28% | -0.15% | -0.60% |
| Bearish +1% price target; bullish unchanged | 302 | 27.15% | -0.12% | -0.50% |
| Exit policy fixed to entry Regime | 301 | 24.58% | -0.13% | -0.50% |

A literal 0.5% price stop loses about 0.60% net under the stated costs. The cost-adjusted stop is about 0.40045% below the paid entry fill; gap execution can still breach the intended budget. No loss is silently capped for presentation.

## Causal breakout and crash observations

These are recognition rules available at the close of the current 5m candle. They do not predict an unseen crash or declare a final swing extreme. All reference levels and denominators exclude the current candle:

| Observation | Exact rule |
| --- | --- |
| Volume breakout | Close above the previous 12-bar high; bullish close in upper 30%; true range ≥1.2 × previous ATR(14); volume ≥1.5 × mean previous 20 bars. |
| Volume breakdown | Close below previous 12-bar low; bearish close in lower 30%; true range ≥1.5 × previous ATR; volume ≥1.5 × prior mean. |
| Rapid-breakdown / crash flag | Volume breakdown plus a decline ≥0.5% over 5m or ≥1% over 15m. This identifies an observed expansion, not a guaranteed future crash. |
| Micro-high reclaim | Bullish close above the high of the previous three 5m bars, closing in the upper 40% of the current range. |
| Range-low reclaim | Low breaks the previous 12-bar low, then the candle closes back above that known level, in the upper 35%, with relative volume ≥1.2. |
| Breakout retest held | Within six bars after a volume breakout, low reaches or trades through the recorded level (a near-touch up to 0.05% above also qualifies), then closes above it in the upper 40%, with no fresh crash flag. The anchor never moves to a later range high. |

The raw spot database stores base-asset volume; it is compared only with prior BTC base volumes. OHLCV comes from the existing Binance spot kline archive, following the [Binance kline contract](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market#klinecandlestick-data). Matching historical order-book liquidity was not invented.

The source contains the following **flagged candles**, not that many independent market crashes or breakouts:

| Flag | Five-minute candles | Fresh starts after >15m without same flag |
| --- | --- | --- |
| breakout_up | 17246 | 13262 |
| breakdown | 14134 | 11502 |
| crash | 4996 | 4104 |
| breakout_retest | 5181 | 4799 |

`market_events.json.gz` retains every observed event with known time, prior range, relative volume and range/ATR. `event_review.json` groups repeated flags for review and lists the latest 50 starts; this grouping changes no entry or exit result.

Examples known within the frozen observation window (chart links open the local app at that 5m candle):

| Observed flag | Known at, PKT | Relative volume | TR / prior ATR | Review |
| --- | --- | --- | --- | --- |
| breakout_retest | 2026-11-11T22:45:00+05:00 | 0.54 | 1.01 | [BTC 5m](http://localhost:8000/?symbol=BTCUSDT&interval=5m&at=1794418800000) |
| breakdown, crash | 2026-11-12T18:10:00+05:00 | 5.93 | 4.93 | [BTC 5m](http://localhost:8000/?symbol=BTCUSDT&interval=5m&at=1794488700000) |
| breakdown, crash | 2026-11-12T19:45:00+05:00 | 1.53 | 2.97 | [BTC 5m](http://localhost:8000/?symbol=BTCUSDT&interval=5m&at=1794494400000) |
| breakout_up | 2026-11-12T21:10:00+05:00 | 1.73 | 1.43 | [BTC 5m](http://localhost:8000/?symbol=BTCUSDT&interval=5m&at=1794499500000) |
| breakout_retest | 2026-11-12T21:30:00+05:00 | 0.22 | 0.85 | [BTC 5m](http://localhost:8000/?symbol=BTCUSDT&interval=5m&at=1794500700000) |
| breakout_up | 2026-11-13T18:35:00+05:00 | 14.59 | 9.03 | [BTC 5m](http://localhost:8000/?symbol=BTCUSDT&interval=5m&at=1794576600000) |

## Did the execution filters help?

The following rules were frozen in protocol.json before evaluation. Pending DI setups can wait at most six additional 5m candles (30 minutes) for price confirmation; a fresh crash cancels a pending entry. The confirmation price is the following open, not the earlier DI setup price.

For DI− >45, strict confluence, no RSI gate:

| Entry rule | Trades | Winning ratio | Mean net | PF | 2017–23 N | 2017–23 mean | 2025–26 N | 2025–26 mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Enter immediately | 301 | 24.58% | -0.13% | 0.65 | 203 | -0.17% | 71 | -0.10% |
| Veto crash now / previous 15m | 248 | 26.21% | -0.11% | 0.71 | 162 | -0.15% | 63 | -0.10% |
| Veto unrecovered crash within 1h | 194 | 22.16% | -0.17% | 0.57 | 120 | -0.20% | 54 | -0.19% |
| Wait for micro-high reclaim | 178 | 27.53% | -0.09% | 0.75 | 122 | -0.14% | 38 | 0.01% |
| Wait for range-low reclaim | 29 | 27.59% | -0.09% | 0.76 | 17 | 0.03% | 8 | -0.31% |
| Wait for volume breakout | 7 | 42.86% | 0.14% | 1.50 | 6 | 0.25% | 1 | -0.50% |

Crash avoidance helps the strict setup modestly. It worsens the earlier/aggressive 5m entry family in this experiment, because high-volume selloffs include both continuing crashes and genuine exhaustion bounces. A generic “never buy after a crash flag” is not a demonstrated universal solution.

The micro-high reclaim improves the DI− >45 baseline from about −0.131% to −0.090% per trade, but it remains negative. The volume-breakout subset is positive in only **seven trades**; it has six discovery trades, no 2024 validation trades, and its single 2025–26 trade loses. It is not a validated exception. No candidate meets the predefined discovery screen of ≥50 trades with positive expectancy and profit factor >1.

Adding RSI <20 and comparing DI− >40 / >45 / >50 is included in results.json; it does not produce a supported, general-use profitable entry gate here.

## Separate bullish breakout branch

Breakouts are also tested as their own bullish entry family, without forcing an oversold DI− entry condition onto momentum entries. Both direct volume breakout and confirmed retest use the unchanged bullish profit-plus-DI+ trailing gate. A historical execution gap censors the full continuous account run; it is not silently closed to free capital. Later periods are therefore also tested separately, each explicitly starting flat:

| Entry branch | Separate flat-start period | Closed | Unresolved | Winning ratio | Mean closed-trade net | PF |
| --- | --- | --- | --- | --- | --- | --- |
| breakout_up | 2017_2023 | 647 | 1 | 9.27% | -0.16% | 0.65 |
| breakout_up | 2024 | 292 | 0 | 13.70% | -0.17% | 0.61 |
| breakout_up | 2025_2026 | 499 | 0 | 13.63% | -0.19% | 0.57 |
| breakout_retest | 2017_2023 | 348 | 1 | 8.33% | -0.13% | 0.72 |
| breakout_retest | 2024 | 173 | 0 | 15.03% | -0.11% | 0.73 |
| breakout_retest | 2025_2026 | 284 | 0 | 16.55% | -0.13% | 0.69 |

These are period-specific replays, not one combined compounded account return. Earlier source gaps remain censored. The later complete periods also have negative expectancy under the retained bullish exit gate, so the breakout label by itself is not sufficient to generate executable profitable buys.

## What is usable now?

- DI/spread exhaustion is a **watch condition** in this study. Price acceptance should be evaluated separately from pressure peaking.
- Volume-backed range breaks and rapid-breakdown flags are reproducible, causal **market-context observations**. They are useful for explaining and reviewing execution risk, but have not earned standalone BUY status.
- A micro-high reclaim is a testable entry-timing candidate; its modest improvement still falls short of positive expectancy.
- Keep the 0.5% protective budget and the declared regime-dependent exit policy. Do not manufacture a higher win rate by ignoring stops, retaining positions through unknown data, selecting the final low, or clipping losses.
- No feature or ADCN field is removed, and no live strategy is promoted. These results support further entry research rather than a deployable indicator.

## Reproduction and integrity

- `protocol.json`: predefined exit, phase-observation and validation rules; no parameter grid search.
- `results.json`: all 72 DI/RSI/entry-gate combinations, target/cost/Regime sensitivities, two OHLC orderings, three chronological periods, full execution traces and independent barrier audit.
- `five_minute_volumes.json.gz`: aligned frozen volume observations. Price source remains the same frozen 1h/5m archive used in v2. `execution_blocks.json.gz` freezes the minute/fallback blocks used for this replay.
- Run `PYTHONPATH=. .venv-build/bin/python3 Section_12_Research/reports/BTC_1h_bear_target_breakouts_v3/study.py`, then `.../write_report.py`.
- The 2025–26 window has already been viewed in earlier hypothesis work. It is a chronological check, not prospective validation. All positive tiny subsets and negative larger results remain reported.
- Verification: 28 targeted Section_13_Development/tests pass for exit-policy changes, bullish-gate preservation, stop priority, target basis, feature timing, prior-volume/range baselines, crash recovery, fixed retest anchors, missing data, delayed confirmation, intrabar reconstruction and original trailing behavior. The independent audit separately checked 328 unambiguous bearish first-barrier outcomes.
