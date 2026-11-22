# Chart viewport

New symbol/timeframe datasets and Reload show up to 200 recent candles plus a
seven-slot right margin. Narrow plots reduce the count to keep candle bodies
readable (roughly six pixels per slot, with a 30-candle minimum). The status bar
reports candles in view separately from active/cached history.

Dataset changes reset price autoscaling and indicator-pane autoscaling. Manual
zoom and historical scrolling remain intact during ordinary refresh/prefetch.
Hidden series must clear their plotted data: Lightweight Charts includes their
timestamps in the shared time axis even when they are invisible. Cached source
bars remain available when an indicator is shown again.

Superseded browser requests are aborted on a dataset switch. Late responses and
errors cannot replace the newly selected timeframe. Full feature pages batch
ATR reconstruction in the same SQLite snapshot rather than querying each cell.
Storage retirement and its saved progress are unchanged.

Live prices use `/api/chart_live` on an independent one-second poll; stored
features/overlays retain the configured refresh period (five seconds by default).
A blocked stored request cannot block live polling. Live requests are deduplicated,
abort on dataset switches, and never enable an inactive timeframe or jump across
missing stored closes. The server publishes fetched OHLCV before provisional
checkpoint/indicator work, then replaces that immutable snapshot with its computed
features. No market-data writes occur on this path. Initial history and stored
refreshes still use Core's canonical stored-bar stream.

The chart-load profile on the user's BTC 5m database measured about 1.62 s in
opportunity projection versus 0.3 s in feature reads, with a 33.746 MiB JSON page
under cProfile. Core now owns one working lifecycle during a page/reference
projection, copying contexts at retained historical snapshots rather than every
WAIT candle. The public immutable `advance` API retains its copy isolation.
All formulas, levels, progression states, frozen evidence and historical results
remain the same. Large HTTP JSON replies negotiate gzip (level 1); clients that
decline it receive ordinary JSON. The profiler also reports compressed size and
compression cost separately; timings require another run on the user's database.

Browser zone projection indexes institutional promotions by identity and searches
only the candles inside each zone's lifetime when classifying its display role.
Hidden SR/OB overlays skip event decoding entirely. This removes all-history
pairwise scans without changing stored zone scores, bounds or lifecycle events.
`window.ChartRenderTimings` retains the last ten synchronous visual/panel timings
in milliseconds for diagnosing remaining client stalls; it sends no telemetry.

Closed zone projections are cached by their exact relevant candle/feature inputs,
source snapshot identities, settings, timeframe and timeline endpoint. Live-price
changes reuse the closed projection and only extend known active endpoints.
History prepends, replay changes, revised OHLC/zone fields, source snapshots and
settings invalidate it. Unchanged stored polls retain snapshot and row identities
instead of replacing them during unrelated progress/liquidity updates. Cache
results never replace engine calculations or stored feature history.

Fresh zone builds run in a module Worker using only the required chart fields;
closed-zone cache hits stay local. Pending requests coalesce to the latest inputs,
and stale worker results cannot replace another dataset. Candles/controls remain
interactive while the worker reconstructs zone geometry; zones appear when ready.
Unsupported/failed workers retain the synchronous fallback. `getProjectionStats()`
reports worker availability and pending status. Stored metadata refreshes skip
unchanged candle/EMA/indicator/marker datasets; live ticks queued behind another
render keep their incremental path. Real stored-row changes and settings still
refresh the complete relevant series.

The current-price ray falls back to the latest plotted candle when an independent
quote is ahead of the stored time axis. If that anchor is unavailable/offscreen,
a dotted horizontal reference remains visible. The numeric price stays current,
extra price-line text remains blank, and no provisional candle is invented across
a storage gap. Drawing uses the retained last-plotted timestamp without copying
series history on each paint.

Stored/live response admission checks the requested symbol/timeframe, each bar's
client identity, matching timestamps, chronological order, finite candle values,
and any supplied feature/decision identity. A mismatched response is rejected with
an explicit chart warning. The render scheduler always releases after exceptions;
failed critical candle/indicator renders clear stale series and force a full retry.
Incremental live updates also require the last rendered market to match. Pending
settings updates retain priority over metadata refreshes, so series-skip logic
cannot swallow a display/style change. The signed-in market regression covers a
BTC/ETH switch, injected viewport failure, volume-average styles during concurrent
refresh, wrong-market candle rejection and a subsequent valid reload.

Liquidity-only notifications retain their incremental path even when they arrive
between a render and its animation-frame release. They cannot replace queued
history, settings, market resets or live-candle work. The composer also avoids
rebuilding unchanged candle, indicator and zone series for a liquidity-only
render. Actual bar/version changes and viewport resets still run the full path;
this changes scheduling, not chart settings, data retention or visual styles.

The drawing SVG is retained during crosshair-only pointer motion. Its viewport key
includes the market/timeframe, pane dimensions, logical time range and two price
coordinates, so horizontal/vertical panning and scaling invalidate the geometry.
Drawing edits, selection/dragging, settings and data notifications still request
a content redraw. This avoids repeatedly clearing/recreating SVG nodes when their
coordinates are unchanged; it does not hide or simplify any drawing.

Liquidity heatmap/depth and filled volume-profile layers retain a transparent
Retina-resolution bitmap for an unchanged viewport. Their original paint commands
run again on data/style changes, pan, price-scale changes, resize, DPR changes or
liquidity expiry. The cache is capped at 16 MiB per layer; unsupported transforms,
allocation failures and oversized viewports use the original direct renderer.
Hidden/detached layers release their bitmaps. No samples, prices, styles or hover
boxes are discarded. Heatmap timestamp-to-candle assignment is prepared on data
updates, and observations share one viewport-coordinate lookup per candle during
panning, with exact gap rejection retained. `getPaintStats()` reports cache use
for diagnostic checks, without changing saved settings.
Drawing geometry updates during pan/zoom also retain compatible SVG groups,
lines, text and handles, updating only changed attributes and removing surplus
nodes. This avoids allocating/replacing the drawing tree on every drag frame;
selection, hit targets, saved geometry and cross-timeframe filtering are retained.
