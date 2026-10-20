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
It verifies 200 initially visible candles with right margin, then user zoom-out
and 20 consecutive 500-candle pages
(10,000 candles back), timestamp/pixel continuity, reversal without refetch,
stationary boundary arrival, reversal during prefetch, one marker wrapper,
renderer configuration, rapid selection/reload, and local ingestion/derived-state
updates that follow the newest edge without interrupting historical browsing.
Older requests are delayed
150 ms so readiness/viewport assertions exercise asynchronous rendering.
The historical scenario disables live quotes and asserts there are no Binance
or separate candle/EMA/current-flags requests.
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
  "live_candle": true,
  "price_precision": {"BTCUSDT": 2, "SUIUSDT": 4}
}
```

Merge these fields with the existing `timeframes` settings. Zero disables
all automatic refresh. `live_candle` defaults to true: latest-page requests add
`live=1` and the server includes a cached provisional candle in the same response.
The server fetches Binance quotes in a background worker (at most once a second
per market/timeframe), so slow exchange I/O cannot block historical requests.
Automatic refresh uses a one-second cadence while live quotes are enabled and
pauses while browsing history. Set `live_candle` to false for stored-only browsing.
The provisional record has the same client/features/adcn shape, but features and
decisions are null until confirmed; it never enters the permanent bar cache or
databases. The chart updates the forming price using `series.update`, not a full
history/indicator redraw. At rollover, it waits for the stored closed candle
before displaying the next forming interval, avoiding gaps and duplicate bars.
Unavailability is shown in the status text; the last provisional quote may remain
visible without being labelled live. Precision otherwise comes from stored prices; it is display formatting,
not an exchange tick-size contract. The ingestion runner is unchanged.
The old `/api/live_candle` endpoint returns 410; live preview is part of
`/api/bars?live=1`, rather than a separate browser candle request. Older cursor
pages never request a live snapshot.

The dedicated live browser scenario uses a controlled source, without network:

```bash
PYTHONPATH=. python3 tests/browser_live.py /workspace/.cache/package/dist/lightweight-charts.standalone.production.js
```

It verifies incremental price ticks without `setData` or permanent writes,
paused history browsing, rollover, replacement by audited state, and source
failure status. Python tests also cover nonblocking/deduplicated requests and
snapshot expiry. Live Binance access from the cloud machine returned HTTP 451
on verification; source connectivity is not claimed from these simulated tests.
The desktop chart server needs access to api.binance.com for live preview.


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

Settings navigation and chart preferences (isolated databases, real chart):

```bash
PYTHONPATH=. python3 tests/browser_settings.py /path/to/lightweight-charts.standalone.production.js
```

Covers Apply/Cancel, EMA period/style, viewport preservation, browser persistence,
coin registry categories, signed-out policy restrictions, keyboard close/focus and mobile
layout. `test_settings_catalog.py` verifies read-only registry grouping and failure
handling. Settings do not enable runner-policy changes or deletion yet.

Independent output styles and migration of shared EMA preferences:

```bash
node --test tests/feature_styles.test.mjs tests/ui_lifecycle.test.mjs
```

The settings browser scenario also checks separate EMA colors/widths/styles,
feature submenus and saved RSI/ADX output preferences.

Administrator workflow (isolated databases and temporary accounts):

```bash
PYTHONPATH=. python3 tests/browser_admin.py /path/to/lightweight-charts.standalone.production.js
```

Tests actual HTTP sessions, normal-user permission denials, immediate timeframe
policy, typed administrator deletion, cache invalidation, scoped coin deletion
and reapproval. `test_data_admin.py` covers three-store rollback, eligibility,
reactivation bootstrap with actual feature computation, epoch invalidation,
policy changes during in-flight downloads/calculation, and failed-bar retries.
Exchange requests use fixtures; this does not establish Binance connectivity.

Authentication now gates chart startup. Browser fixtures provision temporary
accounts and sign in through the actual startup form. The administrator scenario
also covers stale-backend recovery, first-time setup guidance, wrong passwords,
normal-user tab hiding and GET/POST denials, sign-out and expired sessions.
`test_restart_ui.py` checks safe process selection and launchd/manual restart
branches with mocked process controls (never stopping a real process).

Live/stored alerts, sound/notification delivery, Remember Me and category selection:

```bash
PYTHONPATH=. python3 tests/browser_alerts.py /path/to/lightweight-charts.standalone.production.js
```

Uses isolated market/alert/session databases, controlled live snapshots and browser
audio/notification mocks. It verifies stored RSI waits for features, a live price
crossing on an unviewed coin, deduplication, account isolation, delivery while
browsing history, Select All/Deselect All, remembered login after in-memory session
reset, and logout revocation. `test_alerts.py` covers field comparisons, signed
thresholds, readiness, edit revisions, dataset epochs, historical bootstrap,
bounded readers, token hashing and password-change invalidation. These tests do
not establish Binance connectivity or native Mac notification support.

Live EMA/RSI and runner recovery
-------------------------------
The shared forming-candle worker calculates provisional EMA and RSI using the
same pure Section 4 formulas and 500-bar window as permanent processing. It
requires contiguous stored history through the prior candle. Each tick replaces
the forming input, without mutating processor state or writing features. The
runner still calculates and stores final features after downloading the closed
candle. Other indicators remain closed-candle only. Live alerts support EMA and
RSI as well as price. New alert forms take the current chart symbol/timeframe
on every opening.

On macOS, from the checkout, using the Python environment with pipeline dependencies:

```sh
python3 restart_runner.py
python3 check_coin.py ETHUSDT
```

The installer recreates the user launchd plist with this checkout and interpreter,
enables the service even if it was disabled, and starts it on future logins.
It verifies the working folder of an existing runner before replacing it. It
stops a verified project runner and its dedicated launchd job, preserving general
Terminal/VS Code applications. An unknown checkout or respawning writer prevents
a competing start. Logs are created before recovery, even if recovery fails.
The runner performs an initial download pass before feature catch-up; catch-up
can still delay subsequent cycles.
Check both logs for progress or exchange/network failures:

```sh
tail -n 60 "$HOME/Library/Logs/TradingBotV1/runner.log"
tail -n 60 "$HOME/Library/Logs/TradingBotV1/runner-error.log"
```

`tests/test_live_features.py` checks provisional formula parity, tick replacement,
gapped history, and launchd configuration/installation with mocked macOS commands.


Comparison HUD / analysis workspace
----------------------------------
The toolbar's **Analysis** button opens a collapsible right panel, with Best
opportunity pinned above a separately scrollable analysis/chat region. The
independent **HUD** toggle shows a transparent comparison table on the chart. AI ranking,
chart analysis and chat are labelled placeholders; no provider or predictions are
connected. Settings → HUD chooses a pinned reference coin or follows the chart,
1–8 timeframe columns in selection order, and 1–20 reorderable feature rows.
Preferences, HUD visibility and its chart corner (top/bottom left/right) persist
in the browser, independently of analysis-panel visibility. Values come from one
combined latest bar per timeframe (shared provisional live snapshot when available,
otherwise stored closed), with candle UTC timestamps, stale and
inactive labels, and missing values shown as an em dash. This view does not infer
trade direction from numeric indicators. The HUD polls every five seconds while visible,
pauses while hidden, and never requests Binance or full chart history. The chart
resizes with the desktop panel; small screens use a drawer.

```sh
PYTHONPATH=. python3 tests/browser_workspace.py /path/to/lightweight-charts.standalone.production.js
```

`test_hud.py` checks joined snapshots, absent/stale/inactive values, request limits
and bounded reads. `test_restart_runner.py` checks exact process matching, verified
checkout replacement and preservation of unrelated applications. macOS launchd
operations are mocked here; actual download progress must be checked on the Mac.


UI request availability under runner load
----------------------------------------
The UI uses a threaded HTTP server so an idle browser socket or waiting HUD
request cannot monopolize chart/static/account requests. Chart/HUD deletion-guard
waits are capped at one second; temporary lock/SQLite contention returns JSON
HTTP 503 (Retry-After: 1), while unexpected API errors are logged with a traceback
and return JSON HTTP 500 instead of dropping the connection. Stored-bar requests
retry HTTP 503 up to twice. Chart and HUD fetches have finite deadlines; failed
HUD catalog requests clear their shared promise so Retry can work. HUD failure
never gates initial chart loading.

```sh
PYTHONPATH=. python3 tests/browser_hud_failure.py /path/to/lightweight-charts.standalone.production.js
node --test tests/hud_requests.test.mjs tests/ui_lifecycle.test.mjs
```

`test_ui_availability.py` verifies idle sockets, concurrent blocked HUD requests,
bounded real policy-lock waits and structured error responses. Browser fixtures
use the production threaded server. `browser_hud_failure.py` forces HUD and
catalog failures while confirming the chart loads and settings retry recovers.
These checks reproduce failure modes in isolation; they cannot identify a Mac
network/process failure without that machine's server response or logs.


Shared chart/HUD reads without runner contention
-----------------------------------------------
Chart `/api/bars` and other-pair HUD columns use Core's `db.read_state_page`.
That reader opens SQLite in `mode=ro`, avoiding schema initialization during reads.
Neither endpoint acquires the runner's calculation/write policy lock. They instead
hold a shared deletion guard; administrator deletion holds that guard exclusively
through its epoch change and three-store transaction. Ordinary ingestion/features
keep their existing writer coordination and do not block these readers while
calculating. SQLite still protects committed reads during actual database writes.

A HUD column matching the current chart pair uses `DataCache.latestBar` or its
available live `formingBar`, without a HUD data request. Chart events project tick
changes directly into the table. Only other pairs (or a chart browsing history)
need a bounded latest-bar snapshot. Their live values use the existing shared
forming-candle cache, never a separate feature calculator. HUD requests wait for
initial chart loading to finish. Missing provisional features remain missing.

The existing Section 3 `MTF Data.py` describes a timeframe-only in-memory contract
and explicitly leaves its provider unconnected. Section 2 contains input settings;
neither is currently a populated, symbol-aware source for the UI.

```sh
PYTHONPATH=. python3 tests/browser_hud_reuse.py /path/to/lightweight-charts.standalone.production.js
node --test tests/hud_chart_column.test.mjs
```

The browser regression holds the real runner policy lock during initial chart
loading and verifies live/closed HUD projection with zero HUD data requests.
Gateway tests hold an uncommitted feature write and verify that reads see the last
committed value without opening schema-initializing store connections. Separate
checks preserve deletion exclusion and epoch invalidation.

HUD appearance and compact toolbar
----------------------------------
HUD reference choices are restricted to Follow current chart and BTCUSDT; old
other-coin preferences migrate to Follow current chart. Settings → HUD controls
font family/size/color/weight, border color/width/style, cell spacing and optional
candle dates (hidden by default). Status labels remain visible. A keyboard-accessible
corner handle resizes the overlay relative to its selected anchor; dimensions are
saved alongside existing preferences and constrained to chart bounds. Reset HUD
size restores content-based dimensions. The toolbar wraps into available width;
favorite timeframe buttons and status text wrap too, preserving access to controls.

`browser_workspace.py` verifies the two reference options, style/date application,
corner dragging, reload persistence and narrow-window toolbar button bounds.

The HUD table paints beneath the chart's transparent canvas so candles, grid,
and indicators remain above its text and borders. The chart container supplies
the dark background. Only HUD settings/resize controls remain above the canvas;
the table's scroll region remains keyboard-focusable. The workspace browser
regression checks layer order and continues to exercise settings and resizing.
