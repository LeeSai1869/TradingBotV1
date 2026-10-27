# Observed perpetual liquidity

This is live Binance **USDT-margined perpetual** order-book data, separate from
spot candles and from the existing Pine candle-derived liquidity levels. It
starts collecting now; it does not create synthetic book history or change
feature formula signatures/checkpoints. Existing inferred indicators remain
internal compatibility inputs, not order-book observations.

## Start on macOS

```sh
python3 -m pip install -r requirements-liquidity.txt
python3 restart_liquidity.py
python3 restart_ui.py
```

The independent `com.tradingindicator.liquidity` LaunchAgent runs at login,
including when the UI is closed. Its own process/file lock prevents duplicate
writers in one checkout. It stops collecting during sleep, shutdown, network
outages or a symbol pause. Candle downloads/replays use their existing runner.
On other platforms, run `python3 -m Section_1_Global_Core.liquidity.runner`.
An optional `--symbols BTCUSDT ETHUSDT` limits collection to those enabled coins.
Default collection covers up to 50 enabled symbols that exchange discovery
confirms as trading USDT perpetuals. It never aliases a spot symbol to a different
contract, or includes dated/coin-margined futures under the same identity.

Enable **Settings → Features → Liquidity → Select all**. Bids, asks and history
have separate visibility/opacity controls. The chart shows current side bars,
a recent heatmap and hover amounts/time, without a separate book panel. Values
are quote **USDT**, not USD conversions. The badge explicitly identifies the
perpetual feed and the existing spot candles. A missing or stale book is hidden;
known historical samples can remain at their actual observation times. Current
bands are not projected onto an unrelated historical chart viewport.

Check `python3 liquidity_status.py BTCUSDT`. Logs are
`~/Library/Logs/TradingBotV1/liquidity.log` and `liquidity-error.log`.
Disabling a display does not stop recording; pause its coin in the existing
policy, or unload this separate LaunchAgent to stop the recorder altogether.
No API key or third-party liquidity service is used.

## Source and integrity

The adapter uses the public USD-M endpoints:

- REST `https://fapi.binance.com/fapi/v1/exchangeInfo`, `/fapi/v1/depth?limit=1000`,
  and `/fapi/v1/openInterest`.
- Combined stream `wss://fstream.binance.com/stream?streams=...` with per-symbol
  `depth@100ms`, `aggTrade`, `forceOrder`, and `markPrice@1s` subscriptions.
- Protocol reference: [local book synchronization](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/How-to-manage-a-local-order-book-correctly).

Connect and buffer depth **before** fetching the snapshot. Discard updates with
`u < lastUpdateId`; bridge using `U <= lastUpdateId <= u`; subsequent events must
have `pu == previous u`. Quantities replace prior quantities; zero removes a
level. Sequence gaps, missing bridges, crossed/empty books, stale or delayed
exchange updates and queue overflow end that session and require a new snapshot.
Buffered old data is not made live merely by receiving it after a laptop wakes.
Reconnection gaps are recorded, not forward-filled.

A snapshot is limited to 1,000 levels per side. Only prices within its initial
outer boundaries are trusted; isolated updates outside them cannot establish
complete coverage. Cumulative depth at a distance is null when that distance
exceeds known coverage. A stable logarithmic 10-bps grid groups observed orders
within 100 bps of mid. Orders can be withdrawn; displayed depth is not guaranteed
execution or hidden liquidity.

The implementation and recovery tests use local protocol fixtures. This build
environment's proxy blocked Binance documentation and public API access (HTTP
403 tunnel failure), so **production REST/WebSocket connectivity has not been
validated here**. Startup reports real discovery/connection failures explicitly;
it does not fall back to candle estimates. Exchange access/protocol compatibility
must be confirmed using the recorder status on the deployment machine.

## Stored features and training

Every healthy publication (about five seconds) contains:

- Best bid/ask, mid, spread and transport delay.
- Bid/ask USDT depth and imbalance at 5/10/25/50/100 bps; missing coverage is null.
- Estimated market-buy/sell slippage for 1k/10k/100k USDT relative to mid, including
  spread and excluding fees. Insufficient known depth yields null.
- Displayed notional additions/removals since synchronization. **Removals are not
  identified as cancellations**: fills can remove displayed quantity too.
- Sampled band persistence and changes in near-mid depth. Persistence means
  presence at consecutive publications, not proof that the same orders stayed.
- Aggressive buy/sell aggregate-trade notional over the publication window,
  with sequence continuity/partial coverage. Buyer-is-maker means aggressive sell.
- Reported last-filled liquidation notional: SELL is long liquidation, BUY is
  short liquidation. The force-order stream is sampled and **not an exhaustive
  liquidation total or a map of open positions/liquidation prices**.
- Latest mark/index price, funding rate/next funding time, and open interest.
  OI is polled about once per minute and nulled after two minutes without a
  refresh; mark/funding context is nulled after ten seconds. Source/receipt times
  accompany it. Open interest is in the exchange's instrument units, not USD.

A new closed-minute summary is committed when the next healthy minute is
observed. Means and sampled trade-flow sums include coverage; no missing minute
is fabricated. An outage can delay finalization and leaves incomplete coverage.
This summary is a separate liquidity record, not a retroactive spot feature.

Read through the public Core gateway:

```python
from Section_1_Global_Core.global_packet import read_liquidity, read_liquidity_candle
sample = read_liquidity('BTCUSDT', decision_time_ms)
minute = read_liquidity_candle('BTCUSDT', minute_open_ms, decision_time_ms)
```

Reads require `available_ms <= decision_time_ms`; stale samples and samples
crossed by a recorded gap are rejected. Exchange event, receipt, sampling and
storage-ingestion timestamps are distinct. Venue/market/symbol identity is
always explicit. Do not use later-arriving samples or partial-coverage minutes
as if they were known at the candle open. These are observations, not direction
probabilities; no prediction model or leverage/liquidation-position estimates
are invented from the order book.

## Resource boundaries

Separate SQLite WAL memory lives in
`memory_storage/Storage/liquidity/liquidity.db`. Five-second samples retain six
hours; the UI requests at most 240 (roughly the latest 20 minutes). Minute
summaries retain 90 days and gap records seven days. Compression keeps packet
storage bounded; ordinary retention deletes rows, not old candle/feature data.

Raw stream events, snapshots and OI responses are compressed JSONL (not Parquet),
partitioned by venue/market/symbol/UTC date and rotated in approximately 10-MiB
chunks. Closed owned chunks are trimmed after seven days or around a 2-GiB
budget, whichever applies first. Open chunks can temporarily exceed that budget.
Only this recorder's `.jsonl.gz` files are pruned. Raw retention can be much
shorter on busy markets. Export records before retention if training needs them.

The writer has bounded queues (20k raw events, 1k control/publication items),
at most 64 archive handles, two snapshot workers and two context workers. Raw
queue overflow forces resynchronization and an explicit coverage gap. A storage
failure stops collection rather than silently claiming complete data. REST
requests share a one-per-second start limit, honor 418/429 cooldowns, and do not
block WebSocket reads. None of these workers runs in the UI request path or
shares the candle runner's writer lock. Validate CPU/disk/network usage before
assuming 50 busy instruments can be retained without gaps on a laptop.

Current depth bars remain visible at the latest chart edge through the next
forming interval even when that provisional candle is disabled or unavailable.
This projection does not extend historical heatmap cells or permit a stale book.
Historical viewports and prices outside the visible scale have explicit display
notices; cached packets expire to a stale label even if polling has stopped.

Current depth is a VP-style profile drawn behind candles directly on the chart,
with no separate gutter, background panel, divider or centre axis. Each price
band has one stacked bar: green bid notional followed immediately by red ask
notional at the same height. Combined width is proportional to total notional;
each colour's width represents its share. An absent side remains empty rather
than fabricating opposite liquidity. The shared Profile bar length control
sets the maximum width as a percentage of chart width.

Historical heatmap cells keep their true fractional-pixel time width, rather than
stacking many five-second samples into forced one-pixel strips on higher frames.
The provisional candle's own pixel interval stays clear of heatmap shading.

### Rolling observations (analytics version 1)

Each synchronized worker now adds a bounded causal `analytics` object to its
existing five-second sample. No feature DB migration, candle history replay,
additional REST request, or order-book geometry change is required. Existing
stored packets lacking this optional object remain readable.

- Continuous 60/300-second aggressive buy/sell totals, delta and flow imbalance.
  Incomplete windows return null totals with measured coverage. Totals include
  the entire boundary sample (no fabricated prorated trades); `observed_window_ms`
  reports the actual duration, usually slightly over 60/300 seconds. CVD starts from
  the latest continuous segment and resets after gaps, reconnects or clock reversal.
- Mean 10-bps book imbalance is unknown if any observation lacks depth coverage.
- Sampled close-to-close price response, realized 60-second volatility and a
  heuristic microstructure regime (quiet/directional/two-way). These complement
  the existing candle-based Section 5 regimes; they do not replace them.
- Buy/sell absorption *evidence* requires >=60% directional flow imbalance and
  <=2-bps absolute sampled price change in a complete minute. This is a heuristic,
  not proof of absorption, hidden orders, or a buy/sell recommendation.
- Bid/ask notional shares in bands continuously present in successive samples
  for >=30 seconds. Presence is sampled, not proof that individual orders stayed.
  Window additions/removals describe displayed book changes, not cancellation
  identities or proof of replenishment at an individual order level.
- Mark/index basis and five-minute OI percentage change, only with fresh context
  and a recorded baseline. Funding retains the exchange rate and funding time;
  no arbitrary historical funding percentile is invented during warmup.

A `health` object describes source age, trade continuity, context availability
and finite book coverage. Display > Liquidity > **Show feed health and rolling
flow** controls the extra chart text independently of the bars. Hovering a band
also shows sampled presence. Closed-minute summaries retain the final analytics
and health objects alongside their existing coverage and volume fields.

`global_packet.read_liquidity_market_context(symbol, decision_ms)` optionally
reads BTC/ETH five-minute relative returns and return correlations from one
read-only SQLite snapshot. It requires 61 consecutive aligned five-second bins,
fresh observations, and no recorded gap within the interval. Missing benchmark
recordings stay unavailable; it never subscribes to symbols implicitly or mixes
spot candles into perpetual returns. This explicit read is outside the polling
and recording hot paths. All joins filter availability before the decision time.

Scope: this remains observed Binance USDT perpetual liquidity. Additional venues,
spot/perpetual comparisons and calibrated predictive models require separate
market identities and validation; they are not fabricated from the current book.
Snapshot coverage and archive/heatmap retention limits remain as documented above.

Settings > Features > Liquidity now has **Display**, **Style**, and **Data** tabs.
Data exposes the latest stored source observation: coverage, spread, OI/funding,
basis, OI change, CVD, rolling delta/coverage, persistence and absorption evidence.
Stale/synchronizing feeds have no current readings. The refresh button reuses the
combined chart poll; it does not establish another exchange connection. Enable
at least one liquidity layer and apply first so that chart polling requests the
optional packet. This tab does not alter the joined bid/ask profile geometry.
