# Settings structure

The top-right gear opens one modal with top-level tabs, category navigation on
its left, and the selected category's controls on its right. Escape or Cancel
discards edits; Apply stores chart preferences in this browser. Tabs support
arrow keys, Home and End. The native dialog traps focus and restores it on close.

Connected controls:
- General: stored flags panel and BUY/SELL marker visibility.
- Candles: candle and current-price-line visibility.
- Features > EMA: visibility, periods 7/25/50/100/200/300, independent color, width and
  solid/dotted/dashed style per output. Values come from the existing combined bar stream.

Settings apply through Composer and the existing render coordinator, preserving
market selection, cached history and viewport. Preferences use the versioned
`tradingbot.chart-settings.v1` localStorage key. They do not modify calculations.

Features have Display and Style submenus. `feature_styles.js` declares each
output's identity, default color and presentation (line or histogram). The same
row builder renders each output independently. RSI, ADX (+DI, -DI, spread,
direction), ATR, Volume and VWAP already expose saved style preferences, but
their visibility switches stay disabled until their renderers are connected.
Histogram outputs have color and disable line-only controls. Adding an output
requires a catalog entry and connecting its renderer to `config.featureStyles`.
Existing shared EMA preferences migrate to independent rows without changing
the selected periods or saved styling; styles are retained when hidden.

Inputs and timeframe download switches reserve space for later connections. Download switches are disabled, with no implied runner state.
Coin lists use a read-only `/api/settings/coins` endpoint. Approved here means
approved and in the current top50; Inactive contains other approved entries.
Rule exclusions (meme, stablecoin, unavailable on Binance) appear as Ineligible.
Pending and Staged remain visible; existing registry membership is unchanged.
Coin selection is available to establish the workflow, but movement/deletion
buttons are disabled until backend policies are connected.

Next integration steps, independently reviewable:
1. Central runner policy for enabled timeframes, read by both ingestion and
   processors, with explicit pause/resume status and catch-up behavior.
2. Registry mutations preserving the existing approval/inactivity/reactivation
   rules. Ingestion currently hardcodes BTC/SUI, so UI category changes alone
   cannot reliably stop downloads; connect this before enabling move actions.
3. Separate data deletion endpoint for all three memories, coordinated with
   runner writes, confirmed explicitly, always preserving the registry entry.
4. Other feature renderers and calculation inputs, one group at a time.

The chart status `waiting for stored bar` means a live snapshot is ahead of the
last locally stored closed candle. It does not indicate whether features are
running. The UI server and feature runner are separate processes. From the
project root, inspect `launchctl list | grep com.scalp.liverunner`. If launchd
already runs it, use `bash restart_runner.sh`. Otherwise, start it in another
terminal with `python3 -u -m Section_1_Global_Core.memory_storage.Runner.live_runner`.
Keep that terminal open and inspect processor/catch-up messages. Do not run two
writers. A desktop UI launcher need not start the runner.
