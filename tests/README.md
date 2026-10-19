Run from the repository root with Node 24 (tested) and Python with numpy/pandas installed:

```bash
node --test tests/ui_lifecycle.test.mjs
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

The cloud Python environment is `/workspace/.venvs/tradingbot/bin/python`.
These tests use disposable SQLite databases and never fetch market data.
They cover count-based paging over gaps/month boundaries, cursor exhaustion,
missing derived rows, unified identity alignment, stale loads, deduplicated
prefetch, readiness notifications, stored refresh, marker lifecycle and serial
local-store polling. The existing range API remains covered for compatibility.

For the real-browser flow check, install Playwright in a development environment
and provide Chromium at `/usr/bin/chromium`. Obtain the pinned chart library
through npm, which verifies package integrity:

```bash
mkdir -p /workspace/.cache
npm pack lightweight-charts@5.2.1 --cache /workspace/.cache/npm --pack-destination /workspace/.cache
tar -xzf /workspace/.cache/lightweight-charts-5.2.1.tgz -C /workspace/.cache package/dist/lightweight-charts.standalone.production.js
PYTHONPATH=. python3 tests/browser_smoke.py /workspace/.cache/package/dist/lightweight-charts.standalone.production.js
```

The browser runs at 2560 x 1440 using 14,000 stored BTCUSDT 15-minute candles,
matching features, periodic decisions, and additional market/timeframe fixtures.
The history deliberately ends in June 2026, independent of today's clock.
It verifies 1,000 initially visible candles, 20 consecutive 500-candle pages
(10,000 candles back), timestamp/pixel continuity, reversal without refetch,
stationary boundary arrival, reversal during prefetch, one marker wrapper,
renderer configuration, rapid selection/reload, and local ingestion/derived-state
updates that follow the newest edge without interrupting historical browsing.
Older requests are delayed
150 ms so readiness/viewport assertions exercise asynchronous rendering.
It asserts there are no Binance or separate candle/EMA/current-flags requests.
Browser time-range endpoints round fractional edge candles; anchor pixel
continuity is checked to 0.1 pixel instead of relying on endpoint rounding.

The chart reads `/api/bars?symbol=BTCUSDT&interval=15m&limit=1000`; older pages
use `limit=500&before=<first open_time in milliseconds>`. Each `bars` item
contains `client`, `features`, and `adcn` under one canonical identity, plus
`time` in seconds for chart rendering. Missing derived state is null.
Visited history is retained for smooth reversals and cleared on explicit
reload or market/timeframe change. It is not silently trimmed to 1,000 rows
while those rows are visible. The active window remains 1,000 candles.

Optional fields in `Section_11_UI_UX/config/ui_config.json`:

```json
{
  "display": {"candles": true, "ema50": true, "markers": true},
  "stored_refresh_ms": 5000,
  "price_precision": {"BTCUSDT": 2, "SUIUSDT": 4}
}
```

Merge these fields with the existing `timeframes` settings. Zero disables stored
refresh. Refreshes query the local combined stores only and pause while browsing
history. Precision otherwise comes from stored prices; it is display formatting,
not an exchange tick-size contract. The ingestion runner is unchanged.
The old `/api/live_candle` endpoint returns 410 and cannot initiate a Binance
request from the chart server.

The uploaded live configuration registers only `Section_4_Features.processor`.
No application caller persists decisions with `db.write_adcn()`. Existing stored
decisions render, but this change does not implement a new decision writer or
change strategy formulas. The tests' decisions are disposable fixtures.

The existing architecture check (`python -m Section_1_Global_Core.tools.check_imports`)
rejects the storage gateway imports already used by the UI and feature processor;
integration fixtures also import stores to isolate their databases. That checker
and the gateway enforce conflicting contracts. This change does not suppress
that check or claim it passes. The additive read-contract version and isolated
validation scope are recorded in Global Core's README; no new market-data audit
certification is claimed.
