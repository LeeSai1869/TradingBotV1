# Compare desktop WebKit and browser chart performance

The Tauri desktop shell loads `http://localhost:8000` through macOS WebKit. The
browser can use a different engine, scale, settings storage, session and origin.
Even Safari and Tauri have separate WebKit processes and local storage. Fast
browser behavior with a slow app does not establish a database or runner cause.
Existing `ChartRenderTimings` measure synchronous overlay updates; they do not
include all subsequent canvas paint/compositing, JSON parsing or native work.

Use the same BTCUSDT 5m, viewport size, visible candle count and enabled overlays
in both clients. Record `capture_chart_runtime.js` through DevTools in each,
panning/zooming for its ten-second sample. The script reads state and observes
frames/requests, makes no settings writes and sends nothing externally. Request
URLs are stripped of query strings. Transfer sizes may be zero for cached entries.
Background/minimized windows throttle animation frames, so keep the sampled
window visible. Record `desktop_process_snapshot.py` during the lag as well.

Interpret together: high response duration in both clients implicates server/
network; fast responses with high main-thread render work implicate overlays;
fast update timings with slow frames specifically in the app implicate later
painting/compositing/native resource pressure. Large WebKit RSS is evidence to
investigate, not a reason to delete market history. Do not reset preferences or
compact the database as part of this comparison.

`python3 Section_13_Development/diagnostics/check_coin.py BTCUSDT --logs` already
reports active/inactive policy, raw/feature progress, runner PID/checkout and log
age. It does not activate 1m or any other timeframe. Run it on the Mac; cloud
fixtures cannot report the health of a local launchd service.

Version 2 captures new `updateAll`, `updateLive` and `updateLiquidity` calls during
its sample and restores those methods afterward. It observes new resource entries
instead of relying on the page's possibly full shared resource buffer. Historical
entries in the old ten-item render ring are not evidence of a stall during the
sample; lifetime zone build counts likewise do not measure builds per second.
The report explicitly states whether long-task observation is supported and lists
visible feature keys to help compare client configurations.
