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
