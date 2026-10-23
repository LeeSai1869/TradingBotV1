Run from the repository root with Node 24 (tested) and Python with numpy/pandas installed:

```bash
node --test tests/ui_lifecycle.test.mjs
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Completed indicator displays
---------------------------
Symbol selection supports typing a ticker (or common coin name), keyboard arrows
and Enter. The original selector remains hidden as the shared market identity;
search never starts a load for unmatched free text. Candles have separate Display
and Style tabs for bullish/bearish body, wick and border colors and visibility.
WMA 50 uses its existing stored calculation and now has chart/style controls.
Indicator axes show numbers without name tags; pane headers retain names/values.

Drawing placement uses a transparent HTML input layer over the price pane so it
does not depend on unpainted SVG hit areas. Requests use AbortController timeouts
without requiring AbortSignal.timeout. Load/save failures are visible on the chart;
a failed save retains the drawing in memory and exposes Retry saving drawings.
The browser regression simulates a failed POST and verifies retry/persistence.

The candle header is a compact `O H L C Vol Δ%` strip beneath the symbol.
Chart loading/cache status sits below the chart; the stored-flags panel is removed.
Every feature has Select all/Deselect all controls on its Display and Style tabs.
ADX and DI have independent panes/settings; ADX has a dashed 25 reference line.
VWAP axis labels retain their numeric values/colors without band-name tags.

Compact drawing icons sit at the right of the regular top toolbar. Click a
shape icon, then place anchors on the price chart. Clicking a saved drawing opens
its small style popup: color, width, line style, rectangle fill, position lock and
visible timeframes (or all). Drag unlocked shapes/handles to move/edit them.
Undo reverses edits/deletions; Escape cancels unfinished placement.

Drawings now belong to the authenticated account in
`~/.tradingbot/drawings.sqlite3`, separate from market databases. The API ignores
client-supplied usernames and uses the session identity. Each coin has a revision
counter; concurrent saves from other devices return a conflict instead of
silently overwriting their changes. The UI refreshes account drawings periodically.
Devices must connect to the same backend to share the account memory; separate
localhost installations do not share a database. This change does not expose the
local server to the network. Existing browser drawings are imported on first load
of their coin, then removed from browser storage after a successful server save.

Drawings use absolute candle timestamps and price, allowing projection onto the
chosen timeframes. Defaults restrict a new drawing to its creation timeframe.
The duplicate symbol/timeframe row above candle details is removed. Lower-pane
headers show enabled outputs in their own colors, with two-decimal values following
the crosshair or latest candle.

`test_drawings.py` covers persistence, ownership, revision conflicts, deletion,
validation and access checks. `browser_drawings.py` checks icons, style/lock editing,
timeframe visibility and persistence across clean browser contexts. Geometry
vectors remain in `drawings.test.mjs`.

```sh
PYTHONPATH=. python3 tests/browser_drawings.py /workspace/.cache/package/dist/lightweight-charts.standalone.production.js
```

Feature displays use exactly two decimal places in the HUD (including tooltips),
indicator price labels, candle volume/change details and new alert messages.
Raw OHLC prices retain their numeric precision. This is presentation formatting;
stored values and alert comparisons retain full precision. `value_format.test.mjs`
checks that distinction; browser indicator/HUD checks exercise the rendered values.

RSI, ADX/DMI, ATR, Volume and VWAP can be enabled in Features settings.
RSI, ADX, ATR and Volume use synchronized lower chart panes with collapse,
close and direct settings buttons. Per-output colors, widths and line styles
persist in browser preferences; RSI also has editable reference levels.
EMA and VWAP display matching colored price-axis labels. The candle-details
table follows the crosshair and otherwise shows the latest loaded candle.
All these displays consume the existing combined bar stream without separate
indicator requests. Missing feature values remain blank; live values are shown
only when supplied by the existing provisional feature calculation.

```sh
PYTHONPATH=. python3 tests/browser_indicators.py /workspace/.cache/package/dist/lightweight-charts.standalone.production.js
```

This browser regression uses disposable data and checks pane controls, styles,
RSI levels, live RSI updates, persistence, candle details and request reuse.
It verifies rendering, not numerical parity with TradingView.

The supplied `sections_4&5_Tradingview` reference was populated at commit
`e940218`. Numerical translation is tracked separately from these rendering tests.

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


The live configuration registers `Section_4_Features.processor` followed by
`Section_8_Decision_Engine.processor`. Features include the six Section 5 regime
states; Section 8 persists the closed-candle DI recovery rule in ADCN with its
restart checkpoint in the same transaction. Test decisions use disposable stores.

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
The shared forming-candle worker now forks the runner's committed full-history
formula-v3 checkpoint and calculates the complete provisional feature packet.
It requires the checkpoint to be adjacent to the forming candle; while historical
replay is behind, provisional features remain unavailable. Each tick uses a fresh
fork, without advancing permanent state or writing feature rows. Final closed
packets and checkpoints are stored together by the existing runner. Live alert
field eligibility remains price, EMA and RSI; other alert conditions remain
closed-feature rules. New alert forms take the current chart symbol/timeframe
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

Saved-alert manager and independent editor
-----------------------------------------
Alerts opens the saved-alert list and activity. The + New alert button opens a
separate modal editor; Edit opens that editor for the selected rule. Successful
saves close the editor, release its saving state immediately and refresh the list
independently. New creates clear the editing ID and default to the current chart
pair. Failed saves keep the form and re-enable submission. In-flight saves prevent
closing/replacing the editor; requests have a finite deadline and timeout messages
advise checking saved alerts before retrying an uncertain submission.

Saving uses the same deletion guard as chart snapshots rather than waiting for
runner feature-processing locks. Browser audio resume is attempted independently
and cannot delay the save request. Existing per-account alert storage is retained.

```sh
PYTHONPATH=. python3 tests/browser_alert_editor.py /path/to/lightweight-charts.standalone.production.js
```

This browser regression creates three alerts successively while holding the runner
lock and mocking audio resume to remain pending. It verifies separate list/editor,
edit identity, deletion, and successful retry after an HTTP save failure.

Historical backfill versus wrong prices
--------------------------------------
`check_coin.py ETHUSDT` now prints latest stored closes alongside their dates and
flags history behind current time. A read-only exact-timestamp source comparison
can be requested for selected intervals:

```sh
python3 check_coin.py ETHUSDT --verify 1m 5m 15m 1h 2h 4h
```

This compares one latest stored OHLCV sample per interval to a fresh Binance
request for that same symbol, interval and timestamp. MATCH is sample evidence,
not certification of all history; UNVERIFIED reports a failed/unavailable source
check. It never changes candles or runtime state. The chart labels historical
latest candles explicitly instead of implying their prices are current.

The existing fast ingest audit excludes A3 cross-source verification. Freshness
A5 is separate from historical row validity. Ingest now retains/logs actual audit
summaries and the orchestrator no longer hardcodes audit_pass=True. Full audit
aggregation now includes A3 issues, A4 consistency failures and missing freshness
rows; skipped, disabled and empty source checks are labelled separately. Audit
remains post-ingest/best-effort and does not stop a legitimate historical backfill.

`test_coin_verification.py` checks request identity/time, mismatch detection and
read-only operation. `test_audit_reporting.py` distinguishes stale history, missing
rows, source failures and skipped source verification. The cloud cannot validate
the Mac's saved prices; the command above must run against that local database.

Runner progress and bounded ingest audit
---------------------------------------
The ingest `run_fast` audit now samples at most 1000 recent rows per active pair
(10 requested by the runner), checks continuity within that bounded window, and
checks latest-candle freshness via the indexed latest open time. It does not hash
the entire database, scan complete histories, run cross-interval/source checks or
perform network gap repair inline. Detected recent gaps are reported with
`repair_deferred`; A3/A4 are explicitly skipped, never reported as verified.
`audit_runner.run()` retains full-history checks and optional repairs for a
separate full audit. The fast manifest and metadata retain their bounded scope.
This prevents full-history audit/repair work from monopolizing each ingest cycle;
it does not claim all older rows have been audited by the recent sample.

Runner logs identify download, audit and feature-batch phases. After installing
updates, restart the existing runner with `python3 restart_runner.py`; pulling
source files does not reload a running Python process. Startup feature catch-up
may take time before normal cycles resume. Current wrapper versions register
faulthandler's SIGUSR1 traceback handler for diagnosing a stall without killing the
process; never send that signal to an older runner that has not been restarted.
`test_fast_audit.py` verifies bounded sampling, deferred gap repair and exclusion of
full hashing/scanning/network work from the ingest audit.

Restart process identity
------------------------
Runner discovery checks process state and the actual executable (`ps comm`) in
addition to the exact `-m` module. Launcher shells, `-c` command text, and zombie
processes cannot count as active Python writers. A process disappearing during
inspection is tolerated. If a real writer persists after termination, restart
still refuses a competing start and reports PID/parent/state/command for diagnosis.

One login service
-----------------
The canonical launchd label is the existing `com.tradingindicator.liverunner`.
Restart verifies running processes belong to this checkout, disables/boots out both
that job and the earlier helper's `com.scalp.liverunner`, waits for Python writers
to exit, then enables/starts only the original label. The duplicate plist remains
on disk but disabled across logins. Coin diagnostics recognize both labels and
warn if multiple jobs are loaded. This avoids restarting one identity while the
other supervisor respawns its writer. The regression uses the observed legacy
PID/job mapping to verify both jobs are stopped and the original identity reused.

Volume-profile infinite-loop regression
--------------------------------------
A value-area expansion with POC in the first histogram bin and an empty right
neighbor previously treated an unavailable left neighbor as an available zero
bin. A zero/zero tie decremented the lower index below zero forever. The runner's
Python traceback confirmed it was stuck at this loop during ETH 1m catch-up.
Expansion now selects only available sides, crossing empty bins when necessary;
each iteration adds one valid bin, so expansion is bounded by the histogram size.

`test_volume_profile_progress.py` runs the original sparse left-edge failure in a
subprocess with a deadline, and checks right-edge, single-bin and dense profiles.
The correction does not alter stored candles or require clearing feature memory;
restart the runner to resume catch-up from its last committed feature rows.


Complete feature conversion and replay
--------------------------------------
The supplied Section 4/5 reference is now covered by 28 modules (22 numbered Section 4 sections and six Section 5 modules),
not broad location/momentum implementations. See
`Section_4_Features/TRADINGVIEW_REVIEW.md` and `features/README.md` for the source
map, external parameter defaults, explicit source corrections and parity limits.

`test_complete_conversion.py` checks source statement coverage, all 537 contract
fields, independent EMA/Wilder vectors, checkpoint equivalence, pair isolation,
FVG failure memory, institutional references, live rollback, daily security timing,
daily dependency repair, empty profile bins, all six regimes, bounded replay,
backup and export mismatch detection. Previous source is archived. Migration to
formula version 3 is automatic and bounded; `check_coin.py` distinguishes its
cursor from old feature row counts. The raw candles and downloader are unchanged.

```sh
python3 -m Section_4_Features.conversion.validate_export export.csv --symbol ETHUSDT --interval 15m --fields ema50 rsi adx
```

This read-only comparator requires the same Pine inputs/history and an actual
export fixture. Passing synthetic regression vectors is not TradingView export
certification. No such export was provided with the reference source.


Numbered-section layout and replay isolation
--------------------------------------------
`test_complete_conversion.py` verifies exact 4.2 source boundaries, candle ownership,
the absence of the duplicate individual tree, a pre-refactor packet digest,
healthy-pair progress after an injected calculation error, retry without skipping
failed candles, and intentional disabled-timeframe behavior. The source manifest
is in `Section_4_Features/conversion/`; execution helpers are in `execution/`.
Use `python3 check_coin.py ETHUSDT --logs` as a single read-only diagnostic command.


Large-universe runner scheduling
--------------------------------
The existing runner now rotates through bounded download and event slices rather
than visiting every approved coin/timeframe before yielding. Downloads visit up
to 512 pairs or a two-second soft budget; a running network call retains its timeout.
Events have a separate 12-pair/two-second soft budget, checked between bars, with
chronological watermarks retained across slices. Feature maintenance remains a
separate bounded round-robin pass. No extra downloader or writer is introduced.

`test_runner_scheduling.py` covers rotation across more pairs than one slice,
yielding after a slow download, and event timeouts that resume the next pair
without skipping the interrupted pair's next candle. Diagnostics explicitly
separate old feature row counts from missing new-formula checkpoints and label
logs as cumulative across process starts. Backups announce when they begin.


Nested policy writer locks
--------------------------
`test_policy_lock.py` uses actual `flock` calls in bounded subprocesses. It checks
that nested orchestrator/processor locks finish, competing processes stay excluded
until the outermost scope exits, thread timeouts work, and exceptions release the
lock. A real-storage runner cycle replays 205 candles across the maintenance/event
boundary and commits without mocking the policy lock. The prior test fixtures'
no-op locks could not expose this deadlock.


Symbol dropdown picker
----------------------
`browser_symbol_picker.py` checks a 63-symbol list without truncation, a separate
blank/focused search at the top on every open, ticker/name filtering, keyboard
selection, cancel/outside dismissal, scrollable results with a fixed search field,
and a narrow viewport. Existing history and HUD tests select symbols through the
same dropdown. The underlying select/change event contract is retained.

```sh
PYTHONPATH=. python3 tests/browser_symbol_picker.py /path/to/lightweight-charts.standalone.production.js
```


Zone displays and catch-up performance
-------------------------------------
Settings → Features now includes Support / Resistance (dynamic and institutional)
and FVG (bull/bear). `browser_zones.py` covers combined-stream zone rendering,
style persistence and visibility without extra feature requests. Zone primitives
stay in the price pane behind candles and only draw visible segments. The stored
zone bounds are the selected zone's actual array entries, not an ATR approximation.
Older dynamic S/R rows lacking new bounds can show their stored level as a line.
New bounds populate as chronological replay reaches each bar; no reset is needed.

Profiling identified the VP histogram loop and repeated field-name regex work.
The native histogram retains ordered per-bin additions and the golden reference
packet digest; field names are memoized. A local 1,800-bar engine benchmark measured
192→416 bars/s with the old/new histogram, both using cached field names. This
excludes SQLite/network work and is not a promise about the user's Mac.

Normal chart polling reads two newest closed bars instead of 1,000; each twelfth
poll reconciles the full window for historical feature replay. A discontinuous
new edge reloads its initial window rather than skipping cache rows silently.
The updater scans more eligible pairs per soft time budget and fetches a recent
closed page while history fills. Its persistent `history_progress` cursor is in
klines.db, is deleted with the relevant coin/timeframe, and caps feature replay
so a fresh tail can never make recursive calculations jump an unfinished gap.
Audit summaries keep `pass=false` while active history backfills remain.
`test_complete_conversion.py` exercises fresh-tail insertion, gap exclusion,
forward cursor completion, and continued full feature replay on actual stores.


Closed DI-spread decision rule
-----------------------------
`test_di_decisions.py` covers both strictly qualifying setup candles, the inclusive
+DI/spread crossing, strict +DI rise and −DI decline, invalid inputs, no immediate
repeat, closed-feature checkpoint gating, raw time gaps, initial latest-window
seeding, restart/idempotence, symbol/timeframe isolation, policy epochs, and
atomic row/checkpoint rollback. ADCN's unrelated score fields remain intact.
`test_policy_lock.py` exercises both real processors beneath the real runner lock.
`browser_di_decisions.py` generates a decision from stored DI values and verifies
its score-free BUY marker through the existing combined bar endpoint.

### DI turning-point strategy and symbol priority

`test_di_decisions.py` covers both branches in each direction, strict comparisons,
10,000 generated comparisons against the supplied Pine conditions, closed-candle
memory, gaps, policy cancellation, and transactional restart behavior.
`test_work_priority.py` checks existing-before-new ordering, sticky ownership until
raw and feature work finish, and release after pausing/removal. Scheduling tests
cover current refreshes preceding historical work and yielding after slow requests.
`test_daily_refresh.py` checks persisted daily success and failure retry behavior.
`test_strategy_evaluation.py` verifies next-bar-open entry, explicit costs, horizons,
and exclusion of gaps/unfinished tails. These are correctness tests, not evidence
of profitable historical performance. Run `python3 evaluate_strategy.py` on the
machine holding actual formula-v3 market history for a read-only forward study.

Momentum Indicator coverage: `test_di_decisions.py` checks read-only chart markers
without ADCN records, predecessor lookback at page boundaries, and missing bars.
`momentum_indicator.test.mjs` covers independent styles, forming/old-rule exclusion,
sound preference validation, deduplication, historical suppression, and chart
switches. `browser_di_decisions.py` checks visible markers, settings, persistence,
style changes, visibility, synthesized audio and exactly-once delivery in Chromium.

`test_scheduler_resources.py` verifies deterministic closure with retained
connection references, early returns, SQL errors, and failure opening the second
database. Its isolated subprocess performs 1,000 scheduler checks with garbage
collection disabled and a 64-descriptor soft limit. This reproduces the resource
constraint without touching production databases or the parent process limits.
