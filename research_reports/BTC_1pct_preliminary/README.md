# Preliminary 1% result from the uploaded BTC 15m history

All **103,127** source pivots were evaluated against recorded observed price
extremes until the next opposite pivot:

| Research point | Pivots | Reached 1% | Complete non-hits | Censored |
|---|---:|---:|---:|---:|
| Pivot low / BUY | 51,564 | 15,781 | 35,769 | 14 |
| Pivot high / SELL | 51,563 | 15,453 | 36,099 | 11 |

This is a reclassification of the existing 15m source's **subsequent-candle
maximum favorable movement**, not a fresh candle replay. The source freezes at
2026-11-05 00:00 UTC. It cannot recover the first 1% touch time from the old 2%
first-touch timestamp. It does not evaluate the order of high/low inside the
origin candle, or replace the new study's separate origin-close recovery check.
These are retrospective swings from ideal pivot extremes, not achievable trade
win rates, returns, or evidence that a particular feature sequence identifies
them early. The original report remains unchanged.

The full five-timeframe candle/feature comparison must run against the actual
historical stores on the Mac. `study_btc_pivots.py --push-report` scans every native
pivot on 15m, 30m, 1h, 4h and 1d at 1%, compares all stored numeric measurements
around every origin, and generates portable interactive feature curves. No claim
about what all useful pivots share is established by these counts alone.

Reproduce this summary with `python3 research_reports/BTC_1pct_preliminary/reproduce.py`.
